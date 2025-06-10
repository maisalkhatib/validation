from typing import Literal, Optional
from pydantic import BaseModel, ValidationError
from fastapi import HTTPException
import logging
import threading
from queue import Queue

from inventory_manager import InventoryManager
from pydantic_req_structure import InventoryStatusRequest, ClientType
from db_client import DatabaseClient


class MainValidation:
    def __init__(self):
        self._db_client = DatabaseClient(
        "dbname=barns_inventory user=postgres password=QSS2030QSS host=localhost port=5432"
    )


        # the inventory manager
        self._inventory_client = InventoryManager(self._db_client)

        # Queues to receive requests and process responses
        self._request_queue = Queue()
        self._response_queue = Queue()

        # the workers
        self._request_worker = threading.Thread(target=self.request_worker, daemon=True)
        self._response_worker = threading.Thread(target=self.response_worker, daemon=True)


        # event flag to raise when a request is added to the queue
        self._request_event = threading.Event()
        # event flag to raise when a response is added to the queue
        self._response_event = threading.Event()

        # initialize the logging
        logging.basicConfig(level=logging.INFO)



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
            # return False

    def process_update_inventory_request(self, payload):
        """
        Process update inventory request by updating each ingredient in the inventory. 
        Used by Scheduler/OMS to subtract inventory after use
        Used by Dashboard to add or subtract inventory after use
        """
        try:
            # Initialize result tracking
            result = {"passed": True, "details": {}}
            
            # Process each item's ingredients
            for item in payload["payload"]["ingredients"]:
                for ingredient, details in item.items():
                    # Convert espresso to coffee_beans
                    ingredient_type = "coffee_beans" if ingredient == "espresso" else ingredient
                    if ingredient == "cup":
                        ingredient_type = "cups"

                    subtype = details["type"]
                    amount = details["amount"]
                    
                    # Convert shots to grams for coffee_beans
                    if ingredient_type == "coffee_beans":
                        amount = self._inventory_client.convert_shots_to_grams(amount)
                    # if the client type is scheduler, then we need to subtract the amount from the inventory
                    if payload["client_type"] == "scheduler":
                        amount = -amount

                    # Update inventory
                    success, warning = self._inventory_client.update_inventory(
                        ingredient_type=ingredient_type,
                        subtype=subtype,
                        amount=amount  # Negative amount to subtract from inventory
                    )
                    
                    if not success:
                        result["passed"] = False
                        result["details"][f"{ingredient_type}:{subtype}"] = {
                            "updated_amount": 0,
                            "status": "failed",
                            "message": "Failed to update inventory"
                        }
                    elif warning in ["warning", "critical"]:
                        # if key already exists, then append the amount
                        if f"{ingredient_type}:{subtype}" in result["details"]:
                            result["details"][f"{ingredient_type}:{subtype}"]["updated_amount"] += amount
                        else:
                            result["details"][f"{ingredient_type}:{subtype}"] = {
                                "updated_amount": amount,
                                "status": warning,
                                "message": f"Inventory {warning} level reached"
                            }
            
            # Add request metadata to result
            result["request_id"] = payload["request_id"]
            result["client_type"] = payload["client_type"]
            
            # Put result in response queue
            self._response_queue.put(result)
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



    def process_inventory_status_request(self, payload):
        # @Uzair verify this works properly
        """ !!!!!!! NOTE: @Uzair refactor this function to be more efficient and readable
        Used to get the inventory status for the entire inventory OR a specific item in the inventory
        """
        try:
            if payload["client_type"] == "dashboard":
                inventory_status = {}
                
                for ingredient_type, subtypes in self._inventory_client.inventory_cache.items():
                    inventory_status[ingredient_type] = {}

                    for subtype, data in subtypes.items():
                        current_amount = data["current_amount"]
                        warning_threshold = data["warning_threshold"]
                        critical_threshold = data["critical_threshold"]

                        status = "full"
                        final_res = True
                        if current_amount < critical_threshold:
                            status = "empty"
                            final_res = False
                        elif current_amount < warning_threshold:
                            status = "low"

                        inventory_status[ingredient_type][subtype] = {
                            "status": status,
                            "current_amount": current_amount,
                            "warning_threshold": warning_threshold,
                            "critical_threshold": critical_threshold,
                            "final_res": final_res #final_res is False if the inventory is empty when the amount is less than the critical threshold
                        }
            elif payload["client_type"] == "scheduler":
                result = {"passed": True, "details": {}}
                
                for item in payload["payload"]["items"]:
                    item_details = {}
                    
                    # Check cup inventory
                    cup_id = item["cup_id"]
                    if cup_id in self._inventory_client.inventory_cache["cups"]:
                        current_amount = self._inventory_client.inventory_cache["cups"][cup_id]["current_amount"]
                        critical_threshold = self._inventory_client.inventory_cache["cups"][cup_id]["critical_threshold"]
                        if current_amount - 1 < critical_threshold:
                            result["passed"] = False
                        item_details["cup"] = {
                            "current": current_amount,
                            "needed": 1,
                            "critical_threshold": critical_threshold,
                            "status": False if current_amount - 1 < critical_threshold else True
                        }
                    
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
                                amount = self._inventory_client.convert_shots_to_grams(item["ingredients"]["espresso"]["amount"])
                            
                            if subtype in self._inventory_client.inventory_cache[ingredient_type]:
                                current_amount = self._inventory_client.inventory_cache[ingredient_type][subtype]["current_amount"]
                                critical_threshold = self._inventory_client.inventory_cache[ingredient_type][subtype]["critical_threshold"]
                                
                                if current_amount - amount < critical_threshold:
                                    result["passed"] = False
                                    
                                item_details[ingredient] = {
                                    "current": current_amount,
                                    "needed": amount,
                                    "critical_threshold": critical_threshold,
                                    "status": False if current_amount - amount < critical_threshold else True
                                }
                    
                    result["details"][item["drink_name"]] = item_details
                # NOTE: @ UZAIR fix this to make sure the result is sent to the response queue
                return result
            else:
                # invalid client type
                inventory_status = {"final_res": False, "details": "Invalid client type"}
            final_result = { "request_id": payload["request_id"],
                "client_type": payload["client_type"], "result": inventory_status}
            self._response_queue.put(final_result)
            return final_result

        except Exception as e:
            logging.error(f"Error processing inventory status request: {e}")
            error_result = {
                "request_id": payload["request_id"],
                "client_type": payload["client_type"],
                "result": {
                    "final_res": False,
                    "details": f"Error processing request: {str(e)}"
                }
            }
            self._response_queue.put(error_result)
            
            return error_result



    def request_worker(self):
        while True:
            self._request_event.wait()
            request = self._request_queue.get()
            self._request_event.clear()  # Clear the event flag
            
            if request["function_name"] == "update_inventory":
                self.process_update_inventory_request(request)
            elif request["function_name"] == "ingredient_status":
                self.process_inventory_status_request(request)
            elif request["function_name"] == "pre_check":
                self.process_pre_check_request(request)
    
    def send_response(self):
        # send the response
        pass

    def response_worker(self):
        # send the response
        pass
