from typing import List, Dict, Annotated
from pydantic import BaseModel, Field, PositiveInt
from enum import Enum


# Enums for fixed string choices
class ClientType(str, Enum):
    scheduler = "scheduler"
    dashboard = "dashboard"


class RequestType(str, Enum):
    check_cup = "check_cup"
    update_inventory = "update_inventory"


class DrinkName(str, Enum):
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
    amount: PositiveInt  # positive integer only


# One drink item
class DrinkItem(BaseModel):
    drink_name: DrinkName
    size: str
    cup_id: CupID
    temperature: Temperature
    ingredients: Dict[str, IngredientDetail]


# Payload wrapper
class Payload(BaseModel):
    items: List[DrinkItem]


# Full request model
class UpdateInventoryRequest(BaseModel):
    request_id: str
    client_type: ClientType
    request_type: RequestType
    payload: Payload
