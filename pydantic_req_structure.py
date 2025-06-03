from typing import List, Dict, Annotated
from pydantic import BaseModel, Field, PositiveInt
from enum import Enum


# Enums for fixed string choices
class ClientType(str, Enum):
    # TODO: add all the client types
    scheduler = "scheduler"
    dashboard = "dashboard"


class RequestType(str, Enum):
    pre_check = "pre_check"
    update_inventory = "update_inventory"
    inventory_status = "inventory_status"
    check_cup_placed = "check_cup_placed"
    check_cup_picked = "check_cup_picked"


class DrinkName(str, Enum):
    # TODO: add all the drink names
    cappuccino = "cappuccino"
    espresso = "espresso"
    americano = "americano"


class CupID(str, Enum):
    H9 = "H9"
    H6 = "H6"


class Temperature(str, Enum):
    hot = "hot"
    cold = "cold"


# Ingredient detail
class IngredientDetail(BaseModel):
    type: str   
    # integer only but never 0
    amount: int

# One drink item
class DrinkItem(BaseModel):
    drink_name: DrinkName
    size: str
    cup_id: CupID
    temperature: Temperature
    ingredients: Dict[str, IngredientDetail]


# Payload wrapper
class PreCheckPayload(BaseModel):
    items: List[DrinkItem]

class UpdateInventoryPayload(BaseModel):
    items: List[DrinkItem]
    ingredients: List[IngredientDetail]


# Full request model
class PreCheckRequest(BaseModel):
    request_id: str
    client_type: ClientType
    request_type: RequestType
    payload: PreCheckPayload

class UpdateInventoryRequest(BaseModel):
    request_id: str
    client_type: ClientType
    request_type: RequestType
    payload: UpdateInventoryPayload