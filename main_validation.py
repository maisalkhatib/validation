import asyncio
import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ValidationError
from fastapi import HTTPException
import logging
import threading
from queue import Queue
import json
from concurrent.futures import ThreadPoolExecutor

from inventory_manager import InventoryManager
from pydantic_req_structure import InventoryStatusRequest, ClientType
from db_client import DatabaseClient
from coffee_beans_detector import CoffeeBeansDetector


class MainValidation:
    def __init__(self):
        self._db_client = DatabaseClient(
        "dbname=barns_inventory user=postgres password=QSS2030QSS host=localhost port=5432"
    )

        # the inventory manager
        self._inventory_client = InventoryManager(self._db_client)
        self._coffee_beans_detector = CoffeeBeansDetector()

        # Queues to receive requests and process responses
        self._request_queue = Queue()
        self._response_queue = Queue()

        # the workers
        self._request_worker = threading.Thread(target=self.request_worker, daemon=True)
        self._response_worker = threading.Thread(target=self.response_worker, daemon=True)

        # event flags for adding request and response
        self._request_event = threading.Event()
        self._response_event = threading.Event()

        # Thread pool for blocking operations
        self._thread_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="detection_worker")
        # Detection task control
        self._detection_task = None
        self._detection_running = False

        # initialize the logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)


    def post_request(self, request):
        try:
            # # check if it is a valid request using pydantic !! ALWAYS VALID THOUGH !!
            # if not request or not request.payload or not request.payload.items:
            #     # raise a validation error
            #     raise HTTPException(status_code=422, detail="Invalid request")
            # # log the request
            logging.info(f"received request: {request} with request_id: {request.request_id}")
            # if the request is valid, add it to the queue
            self._request_queue.put(request)
            # raise the event flag
            self._request_event.set()
        except Exception as e:
            print(e) 
            print("failed to add request to queue")
            # log the error
            logging.error(f"failed to add request to queue: {e}")


    def process_update_inventory_request(self, payload):
        """
        Process update inventory request by updating each ingredient in the inventory. 
        Used by Scheduler/OMS to subtract inventory after use
        Used by Dashboard to add or subtract inventory after use
        """
        try:
            # Initialize result tracking
            result = {"passed": True, "details": {}}

            # Add request metadata to result
            result["request_id"] = payload["request_id"]
            result["client_type"] = payload["client_type"]
            
            # Process each item's ingredients
            for item in payload["payload"]["ingredients"]:
                for ingredient, details in item.items():
                    # Convert espresso to coffee_beans
                    ingredient_type = "coffee_beans" if ingredient == "espresso" else ingredient
                    # changes_by_mais: why to not use one: cup or cups
                    if ingredient == "cup":
                        ingredient_type = "cups"

                    subtype = details["type"]
                    amount = details["amount"]

                    # if the client type is scheduler, then we need to subtract the amount from the inventory
                    if payload["client_type"] == "scheduler":
                        amount = -amount

                    # Update inventory
                    success, warning = self._inventory_client.update_inventory(
                        ingredient_type=ingredient_type,
                        subtype=subtype,
                        amount=amount  # Negative amount to subtract from inventory
                    )
                    print(f"success: {success}, warning: {warning}")
                    # to be discussed: why the type and subtype in this format: "coffee_beans:regular"
                    if not success:
                        result["passed"] = False
                        result["details"][ingredient_type] = {
                            "type": subtype,
                            "updated_amount": 0,
                            "status": "failed",
                            "message": "Failed to update inventory"
                        }
                    elif warning in ["no_warning", "warning", "critical"]:
                        if ingredient_type in result["details"] and subtype in result["details"][ingredient_type].values():
                            result["details"][ingredient_type]["updated_amount"] += amount
                        else:
                            result["details"][ingredient_type] = {
                                "type": subtype,
                                "updated_amount": amount, # changes_by_mais: should it be the absolute value? or the inventory value?
                                "status": warning,
                                "message": f"Inventory {warning} level reached"
                            }

            # Put result in response queue
            self._response_queue.put(result)
            print("result after update inventory request")
            print(result)
            return result
            
        except Exception as e:
            logging.error(f"Error processing update inventory request: {e}")
            error_result = {
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "passed": False,
                "details": {"error": str(e)}
            }
            self._response_queue.put(error_result)
            return error_result



    # def process_ingredient_status_request(self, payload):
    #     # @Uzair verify this works properly
    #     # i believe the structure of the request should be without any item in the payload
    #     """ !!!!!!! NOTE: @Uzair refactor this function to be more efficient and readable
    #     Used to get the inventory status for the entire inventory OR a specific item in the inventory
    #     """
    #     try:
    #         inventory_status = {}
    #         if payload["client_type"] == "dashboard" or payload["client_type"] == "api_bridge":
                
    #             for ingredient_type, subtypes in self._inventory_client.inventory_cache.items():
    #                 inventory_status[ingredient_type] = {}

    #                 for subtype, data in subtypes.items():
    #                     current_amount = data["current_amount"]
    #                     warning_threshold = data["warning_threshold"]
    #                     critical_threshold = data["critical_threshold"]

    #                     status = "full"
    #                     final_res = True
    #                     if current_amount < critical_threshold:
    #                         status = "empty"
    #                         final_res = False
    #                     elif current_amount < warning_threshold:
    #                         status = "low"

    #                     inventory_status[ingredient_type][subtype] = {
    #                         "status": status,
    #                         "current_amount": current_amount,
    #                         "warning_threshold": warning_threshold,
    #                         "critical_threshold": critical_threshold,
    #                         "final_res": final_res #final_res is False if the inventory is empty when the amount is less than the critical threshold
    #                     }
                        
    #                     # another suggestion for response structure:
    #                     # inventory_status[ingredient_type][subtype] = {
    #                     #     "status": status, # better to be high, medium, low
    #                     #     "current_amount": current_amount,
    #                     # }
            
    #         else:
    #             # invalid client type
    #             inventory_status = {"final_res": False, "details": "Invalid client type"}
    #         final_result = { "passed": True, "request_id": payload["request_id"],
    #             "client_type": payload["client_type"], "details": inventory_status}
    #         self._response_queue.put(final_result)
    #         self._response_event.set()
    #         return final_result

    #     except Exception as e:
    #         logging.error(f"Error processing inventory status request: {e}")
    #         error_result = {
    #             "passed": False,
    #             "request_id": payload["request_id"],
    #             "client_type": payload["client_type"],
    #             "result": {
    #                 "final_res": False,
    #                 "details": f"Error processing request: {str(e)}"
    #             }
    #         }
    #         self._response_queue.put(error_result)
    #         # NOTE: @ UZAIR fix this to make sure the result is sent to the response queue
    #         self._response_event.set()
    #         return error_result

    
    def process_pre_check_request(self, payload):
        # NOTE: THIS IS PRE-CHECK REQUEST
        try: 
            result = {"passed": True, "details": {}}
            # Add request metadata to result
            result["request_id"] = payload["request_id"]
            result["client_type"] = payload["client_type"]


            if payload["client_type"] == "scheduler":
                # get the invenoty cache
                current_inventory_cache = self._inventory_client.inventory_cache.copy()
                
                for item in payload["payload"]["items"]:
                    item_details = {}
                    # set the status for the item to true
                    item_details["status"] = True
                    
                    # Check cup inventory
                    cup_id = item["cup_id"]
                    if cup_id in current_inventory_cache["cups"]:
                        current_amount = current_inventory_cache["cups"][cup_id]["current_amount"]
                        critical_threshold = current_inventory_cache["cups"][cup_id]["critical_threshold"]
                        if current_amount - 1 < critical_threshold:
                            result["passed"] = False
                            item_details["status"] = False
                        item_details["cup"] = {
                            "type": cup_id,
                            "current": current_amount,
                            "needed": 1,
                            "critical_threshold": critical_threshold,
                            "status": False if current_amount - 1 < critical_threshold else True
                        }
                        if item_details["cup"]["status"] == True:
                            # update the inventory cache
                            current_inventory_cache["cups"][cup_id]["current_amount"] = current_amount - 1

                    # Check other ingredients
                    for ingredient, details in item["ingredients"].items():
                        if ingredient == "espresso":
                            ingredient_type = "coffee_beans"
                        else:
                            ingredient_type = ingredient
                            
                        if ingredient_type in self._inventory_client.inventory_cache:
                            subtype = details["type"]
                            amount = details["amount"]
                            if ingredient_type == "coffee_beans":
                                # get the amount against the shot using the self._inventory_client.convert_shots_to_grams(amount)
                                amount = self._inventory_client.convert_shots_to_grams(item["ingredients"]["coffee_beans"]["amount"])
                            
                            if subtype in current_inventory_cache[ingredient_type]:
                                current_amount = current_inventory_cache[ingredient_type][subtype]["current_amount"]
                                critical_threshold = current_inventory_cache[ingredient_type][subtype]["critical_threshold"]
                                
                                if current_amount - amount < critical_threshold:
                                    result["passed"] = False
                                    item_details["status"] = False
                                    
                                item_details[ingredient] = {
                                    "type": subtype,
                                    "current": current_amount,
                                    "needed": amount,
                                    "critical_threshold": critical_threshold,
                                    "status": False if current_amount - amount < critical_threshold else True
                                }
                                if item_details[ingredient]["status"] == True:
                                # update the inventory cache
                                    current_inventory_cache[ingredient_type][subtype]["current_amount"] = current_amount - amount
                    

                    result["details"][item["drink_name"]] = item_details
                print(result)

            else:
                # invalid client type
                result = {"request_id": result['request_id'], 
                          "client_type": result['client_type'], 
                          "passed": False, 
                          "details": "Invalid client type"}
                
            self._response_queue.put(result)
            self._response_event.set()
            return result

        except Exception as e:
            logging.error(f"Error processing pre-check request: {e}")
            error_result = {
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "passed": False,
                "details": f"Error processing request: {str(e)}"
            }
            self._response_queue.put(error_result)
            # NOTE: @ UZAIR fix this to make sure the result is sent to the response queue
            self._response_event.set()
            return error_result

    # def process_refill_ingredient_request(self, payload):
    #     try:
    #         result = {"passed": True, "details": {}}
    #         result["request_id"] = payload["request_id"]
    #         result["client_type"] = payload["client_type"]

    #         for ingredient in payload["payload"]["ingredients"]:
    #             ingredient_type = ingredient["ingredient_type"]
    #             subtype = ingredient["subtype"]

    #             if ingredient_type == "espresso":
    #                 ingredient_type = "coffee_beans"
    #             elif ingredient_type == "cup":
    #                 ingredient_type = "cups"

    #             is_refilled = self._inventory_client.refill_inventory(ingredient_type, subtype)
                
    #             if not is_refilled:
    #                 result["passed"] = False
    #                 result["details"][f"{ingredient_type}"] = {
    #                     "type": subtype,
    #                     "status": "failed",
    #                     "message": "Failed to refill inventory"
    #                 }
                
    #             else:
    #                 result["details"][f"{ingredient_type}"] = {
    #                     "type": subtype,
    #                     "status": "success",
    #                     "message": "Inventory refilled successfully"
    #                 }
            
    #         self._response_queue.put(result)
    #         self._response_event.set()
    #         return result
            
    #     except Exception as e:
    #         logging.error(f"Error processing refill ingredient request: {e}")
    #         error_result = {
    #             "request_id": payload["request_id"],
    #             "client_type": payload["client_type"],
    #             "passed": False,
    #             "details": f"Error processing request: {str(e)}"
    #         }
    #         self._response_queue.put(error_result)
    #         return error_result
    
    
    def process_refill_ingredient_request(self, payload):
        try:
            # Extract parameters from payload
            ingredient_type = payload.get("payload", {}).get("ingredient_type", None)
            subtype = payload.get("payload", {}).get("subtype", None)
            print(f"inside process_refill_ingredient_request: ingredient_type: {ingredient_type}, subtype: {subtype}")

            result = {"passed": True, "details": {}}
            result["request_id"] = payload["request_id"]
            result["client_type"] = payload["client_type"]

            # Check if we need coffee beans detection for regular coffee
            needs_coffee_detection = (
                (ingredient_type == "coffee_beans" and subtype == "regular") or 
                (ingredient_type == "coffee_beans" and subtype is None) or 
                (ingredient_type is None and subtype is None)  # Full refill
            )
            print(f"needs_coffee_detection: {needs_coffee_detection}")

            coffee_detection_success = True
            
            # Handle coffee beans regular detection if needed
            if needs_coffee_detection:
                detection_result = self._run_coffee_beans_detection(function_name="inventory_refill")
                
                if detection_result["success"] and detection_result.get("updated"):
                    result["details"]["coffee_beans_message"] = f"Coffee beans regular refilled successfully with {detection_result['percentage']}% detected"
                    result["details"]["coffee_beans_percentage"] = detection_result["percentage"]
                    coffee_detection_success = True
                elif detection_result["success"] and not detection_result.get("updated"):
                    # Detection successful but percentage <= 0
                    result["passed"] = False
                    result["details"]["error"] = detection_result["message"]
                    result["details"]["alert_type"] = detection_result.get("alert_type", "visibility_issue")
                    coffee_detection_success = False
                else:
                    # Detection failed - camera issue
                    result["passed"] = False
                    result["details"]["error"] = detection_result["message"]
                    result["details"]["alert_type"] = detection_result.get("alert_type", "camera_reconnect")
                    coffee_detection_success = False

            # Handle normal refill for other ingredients (skip coffee regular if detection was used)
            normal_refill_success = True
            
            if coffee_detection_success:  # Only proceed if coffee detection succeeded (or wasn't needed)
                if ingredient_type == "coffee_beans" and subtype == "regular":
                    # Coffee beans regular only - already handled by detection, no normal refill needed
                    pass
                else:
                    # All other cases: use normal refill with skip_coffee_regular flag when needed
                    skip_coffee_regular = needs_coffee_detection  # Skip if we already handled it with detection
                    
                    normal_refill_success = self._inventory_client.refill_inventory(
                        ingredient_type=ingredient_type,
                        subtype=subtype,
                        skip_coffee_regular=skip_coffee_regular
                    )
                    
                    if not normal_refill_success:
                        result["passed"] = False
                        if "error" not in result["details"]:  # Don't override coffee detection errors
                            result["details"]["error"] = f"Failed to refill {ingredient_type}:{subtype}"
                    else:
                        if "coffee_beans_message" not in result["details"]:
                            result["details"]["message"] = f"Successfully refilled {ingredient_type}:{subtype}"

            # Final result
            result["passed"] = coffee_detection_success and normal_refill_success

            self.logger.info(f"Refill ingredient request result: {json.dumps(result, indent=2)}")
            self._response_queue.put(result)
            self._response_event.set()
            return result
            
        except Exception as e:
            logging.error(f"Error processing refill ingredient request: {e}")
            error_result = {
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "passed": False,
                "details": {"error": f"Error processing request: {str(e)}"}
            }
            self._response_queue.put(error_result)
            self._response_event.set()
            return error_result
        
    def process_ingredient_status_request(self, payload):
        """
        Process ingredient status request with flexible filtering
        """
        try:
            # Extract parameters from payload
            ingredient_type = payload.get("payload", {}).get("ingredient_type", None)
            print(f"****ingredient_status_request: {json.dumps(payload, indent=2)}")
            subtype = payload.get("payload", {}).get("subtype", None)
            print("###################################")
            print(ingredient_type, subtype)
            print("###################################")
            print(payload)
            # Get status from inventory manager
            inventory_status = self._inventory_client.get_inventory_status(
                ingredient_type=ingredient_type,
                subtype=subtype
            )
            print(f"inventory_status: {json.dumps(inventory_status, indent=2)}")
            
            final_result = {
                "passed": True,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": inventory_status
            }
            
            self._response_queue.put(final_result)
            self._response_event.set()
            return final_result
            
        except Exception as e:
            logging.error(f"Error processing inventory status request: {e}")
            error_result = {
                "passed": False,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": {"error": f"Error processing request: {str(e)}"}
            }
            self._response_queue.put(error_result)
            self._response_event.set()
            return error_result
    
    def process_category_info_request(self, payload):
        """Process category info request"""
        try:
            category_info = self._inventory_client.get_inventory_category_info()
            final_result = {
                "passed": True,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": category_info
            }
            # self._response_queue.put(final_result)
            # self._response_event.set()
            return final_result
        
        except Exception as e:
            logging.error(f"Error processing category info request: {e}")
            error_result = {
                "passed": False,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": {"error": f"Error processing request: {str(e)}"}
            }
            self._response_queue.put(error_result)
            self._response_event.set()
            return error_result
        

    def process_category_summary_request(self, payload):
        """Process category summary request"""
        try:
            print("###################################")
            print("process_category_summary_request")
            print(f"payload: {json.dumps(payload, indent=2)}")
            category_summary = self._inventory_client.get_category_summary()
            
            final_result = {
                "passed": True,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": category_summary
            }
            print(f"final_result: {json.dumps(final_result, indent=2)}")
            
            self._response_queue.put(final_result)
            self._response_event.set()
            return final_result
            
        except Exception as e:
            logging.error(f"Error processing category summary request: {e}")
            error_result = {
                "passed": False,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": {"error": f"Error processing request: {str(e)}"}
            }
            self._response_queue.put(error_result)
            self._response_event.set()
            return error_result

    def process_category_count_request(self, payload):
        """Process category count request"""
        try:
            category_count = self._inventory_client.get_category_count()
            
            final_result = {
                "passed": True,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": category_count
            }
            
            self._response_queue.put(final_result)
            self._response_event.set()
            return final_result
        
        except Exception as e:
            logging.error(f"Error processing category count request: {e}")
            error_result = {
                "passed": False,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": {"error": f"Error processing request: {str(e)}"}
            }
            self._response_queue.put(error_result)
            self._response_event.set()
            return error_result
        

    def process_stock_level_request(self, payload):
        """Process inventory stock level statistics request"""
        try:
            stock_level = self._inventory_client.get_inventory_stock_level_stats()
            
            final_result = {
                "passed": True,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": stock_level
            }
            
            self._response_queue.put(final_result)
            self._response_event.set()
            return final_result
            
        except Exception as e:
            logging.error(f"Error processing inventory severity request: {e}")
            error_result = {
                "passed": False,
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "details": {"error": f"Error processing request: {str(e)}"}
            }
            self._response_queue.put(error_result)
            self._response_event.set()
            return error_result
        

            
    
    def request_worker(self):
        while True:
            try:
                self._request_event.wait()
                request = self._request_queue.get()
                self._request_event.clear()  # Clear the event flag
                
                if request["function_name"] == "update_inventory":
                    self.process_update_inventory_request(request)
                elif request["function_name"] == "ingredient_status" or request["function_name"] == "pre_check":
                    self.process_ingredient_status_request(request)
                else:
                    logging.error(f"Invalid function name: {request['function_name']}")
            except Exception as e:
                logging.error(f"Error processing request: {e}")


    def response_worker(self):
        while True:
            try:
                self._response_event.wait()
                response = self._response_queue.get()
                ####################
                # @NOTE: @Uzair @Mais work with sending the response to the client here
                ## Ideally have a separate object to handle this
                print(response)
            #####################
                self._response_event.clear()
            except Exception as e:
                logging.error(f"Error processing response: {e}")


    async def start_periodic_detection(self):
        """Start the periodic coffee beans detection task"""
        if self._detection_task is None or self._detection_task.done():
            self._detection_running = True
            self._detection_task = asyncio.create_task(self._periodic_detection_loop())
            self.logger.info("Started periodic coffee beans detection (every 10 minutes)")

    async def stop_periodic_detection(self):
        """Stop the periodic coffee beans detection task"""
        self._detection_running = False
        if self._detection_task and not self._detection_task.done():
            self._detection_task.cancel()
            try:
                await self._detection_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Stopped periodic coffee beans detection")

    async def _periodic_detection_loop(self):
        """Main loop for periodic coffee beans detection"""
        while self._detection_running:
            try:
                self.logger.info("Starting coffee beans detection...")
                
                # Run the blocking detection in thread pool
                loop = asyncio.get_event_loop()
                detection_result = await loop.run_in_executor(
                    self._thread_pool, 
                    self._run_coffee_beans_detection
                )
                
                # Log the result
                if detection_result.get("updated"):
                    self.logger.info(f"Periodic detection updated inventory: {detection_result['percentage']}%")
                else:
                    self.logger.info(f"Periodic detection completed without update: {detection_result['message']}")
                
            except asyncio.CancelledError:
                self.logger.info("Coffee beans detection task cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in coffee beans detection: {e}")
            
            # Wait for 10 minutes before next detection
            try:
                await asyncio.sleep(600)  # 10 minutes = 600 seconds
            except asyncio.CancelledError:
                break

    def _run_coffee_beans_detection(self, function_name: str = "periodic_detection"):
        """Wrapper method to run detection in thread pool (this runs in a separate thread)"""
        try:
            # This is the blocking operation that runs in the thread pool
            cv_result = self._coffee_beans_detector.detect_coffee_beans()
            print(f"cv_result: {cv_result}")
            if function_name == "periodic_detection":
                # Case 1: Periodic detection every 10 minutes
                if cv_result.get("percentage", -1) > 0:
                    # Update inventory based on detected percentage
                    success = self._inventory_client.update_inventory_from_detection(cv_result["percentage"])
                    return {
                        "success": True,
                        "updated": True,
                        "percentage": cv_result["percentage"],
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": f"Periodic detection successful, inventory updated with {cv_result['percentage']}% detected"
                    }
                else:
                    # Percentage <= 0, don't update inventory
                    return {
                        "success": True,
                        "updated": False,
                        "percentage": cv_result.get("percentage", 0),
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": "Periodic detection completed, no inventory update (percentage <= 0)"
                    }
                    
            if function_name == "inventory_refill":
                # Case 4: Refill operation
                if cv_result.get("percentage", -1) > 0:
                    # Update inventory based on detected percentage
                    success = self._inventory_client.update_inventory_from_detection(cv_result["percentage"])
                    return {
                        "success": True,
                        "updated": True,
                        "percentage": cv_result["percentage"],
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": f"Refill detection successful, inventory updated with {cv_result['percentage']}% detected"
                    }
                else:
                    # Percentage <= 0, send alert about visibility issue
                    return {
                        "success": True,
                        "updated": False,
                        "percentage": cv_result.get("percentage", 0),
                        "timestamp": datetime.datetime.now().isoformat(),
                        "message": "Refill detection failed - coffee beans should be above the unseen area",
                        "alert_type": "visibility_issue"
                    }
            else:
                # Default case - just return detection result
                return {
                    "success": True,
                    "result": cv_result,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "message": "Coffee beans detection completed successfully"
                }
                
        except Exception as e:
            self.logger.error(f"Coffee beans detection failed: {e}")
            
            if function_name == "inventory_refill":
                # Case 4: Detection failed during refill - alert to reconnect camera
                return {
                    "success": False,
                    "updated": False,
                    "error": str(e),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "message": "Detection failed during refill operation",
                    "alert_type": "camera_reconnect"
                }
            else:
                # Case 1: Detection failed during periodic - keep current amount
                return {
                    "success": False,
                    "updated": False,
                    "error": str(e),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "message": "Detection failed, keeping current inventory amount"
                }

    async def cleanup(self):
        """Cleanup resources when shutting down"""
        await self.stop_periodic_detection()
        
        # Shutdown the thread pool
        self._thread_pool.shutdown(wait=True)
        self.logger.info("MainValidation cleanup completed")