from typing import Literal, Optional
from pydantic import BaseModel

from inventory_manager import InventoryManager




class MainValidation:
    def __init__(self):


        # the inventory manager
        self._inventory = InventoryManager()
        # the main queue where we will receive the requests
        self._queue = []

    def post_request(self, request):
        # check if it is a valid request using pydantic
        pass
