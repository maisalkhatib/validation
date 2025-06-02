from typing import Literal, Optional
from pydantic import BaseModel, ValidationError, HTTPException
import logging


from inventory_manager import InventoryManager




class MainValidation:
    def __init__(self):


        # the inventory manager
        # self._inventory_client = InventoryManager()
        # the main queue where we will receive the requests
        self._request_queue = []
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
            self._request_queue.append(request)
        except Exception as e:
            print(e)
            print("failed to add request to queue")
            # log the error
            logging.error(f"failed to add request to queue: {e}")
            return False
