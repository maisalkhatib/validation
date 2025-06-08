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
        # the main queue where we will receive the requests
        
        self._request_queue = Queue()
        # the response queue
        self._response_queue = Queue()

        # the workers
        self._request_worker = threading.Thread(target=self.request_worker, daemon=True)
        self._response_worker = threading.Thread(target=self.response_worker, daemon=True)

        # initialize the logging
        logging.basicConfig(level=logging.INFO)



    def post_request(self, request):
        try:
            # check if it is a valid request using pydantic !! ALWAYS VALID THOUGH !!
            if not request or not request.payload or not request.payload.items:
                # raise a validation error
                raise HTTPException(status_code=422, detail="Invalid request")
            # log the request
            logging.info(f"received request: {request} with request_id: {request.request_id}")
            # if the request is valid, add it to the queue
            self._request_queue.put(request)
        except Exception as e:
            print(e) 
            print("failed to add request to queue")
            # log the error
            logging.error(f"failed to add request to queue: {e}")
            # return False
    def process_inventory_status_request(self, payload):
        """
        Used to get the inventory status for the entire inventory OR a specific item in the inventory


        payload looks like this:
                {
            "request_id": "275ceafa-59e7-4639-b35f-61234f2ec634",
            "client_type": "scheduler",
            "function_name": "pre_check",
            "payload": {
                "items": [{
                    "drink_name": "cappuccino",
                    "size": "small",
                    "cup_id": "H9",
                    "temperature": "hot",
                    "ingredients": {
                    "espresso": {
                        "type": "regular",
                        "amount": 1
                    },
                    "milk": {
                        "type": "whole",
                        "amount": 150
                    }
                }
            },
            {
                "drink_name": "americano",
                "size": "small",
                "cup_id": "H9", 
                "temperature": "hot",
                "ingredients": {
                    "espresso": {
                        "type": "regular",
                        "amount": 2
                    }
                }
            }]
            }
        }
        """
        if payload["client_type"] == "dashboard	":
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
                        "final_res": final_res
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
            
            return result
        else:
            # invalid client type
            inventory_status = {"final_res": False, "details": "Invalid client type"}
        final_result = { "request_id": payload["request_id"],
            "client_type": payload["client_type"], "result": inventory_status} 
        self._response_queue.put(final_result)
        return final_result



    def process_request(self):
        # process the request
        pass
    
    def send_response(self):
        # send the response
        pass

    def request_worker(self):
        # process the request
        pass

    def response_worker(self):
        # send the response
        pass
