from typing import Literal, Optional
from pydantic import BaseModel, ValidationError, HTTPException
import logging
import threading
from queue import Queue

from inventory_manager import InventoryManager
from pydantic_req_structure import InventoryStatusRequest
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
    def process_inventory_status_request(self, request: InventoryStatusRequest):
        pass



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
