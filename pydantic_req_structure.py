from typing import List, Dict, Annotated, Optional
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

class RobotArm(str, Enum):
    # NOTE: One or Two needs to be mapped to Left/Right or Cold/Hot
    hot = "hot"
    cold = "cold"

class CupPosition(int, Enum):
    # NOTE: 1 or 2 needs to be mapped to Left/Right or Cold/Hot
    one = 1
    two = 2

# Ingredient detail
class IngredientDetail(BaseModel):
    type: str   
    # integer only but never 0
    amount: float

# One drink item
class DrinkItem(BaseModel):
    drink_name: DrinkName
    size: str
    cup_id: CupID
    temperature: Temperature
    ingredients: Dict[str, IngredientDetail]

class CheckCupPickedPayload(BaseModel):
    item: DrinkItem
    robot_arm: RobotArm

# Payload wrapper
class PreCheckPayload(BaseModel):
    items: List[DrinkItem]

class UpdateInventoryPayload(BaseModel):
    items: List[DrinkItem]
    ingredients: List[IngredientDetail]

class CheckCupPlacePayload(BaseModel):
    items: List[DrinkItem]
    # robot_arm: RobotArm
    cup_position: CupPosition

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

class CheckCupPlacedRequest(BaseModel):
    request_id: str
    client_type: ClientType
    request_type: RequestType
    payload: CheckCupPlacePayload

class CheckCupPickedRequest(BaseModel):
    request_id: str
    client_type: ClientType
    request_type: RequestType
    payload: CheckCupPickedPayload

class InventoryStatusRequest(BaseModel):
    request_id: str
    client_type: ClientType
    request_type: RequestType
    # here payload is optional
    payload: Optional[PreCheckPayload] = None