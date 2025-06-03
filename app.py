from pydantic_req_structure import UpdateInventoryRequest
from fastapi import FastAPI, HTTPException
import uvicorn

from main_validation import MainValidation


app = FastAPI(title="Inventory Manager", description="Inventory Manager API", docs_url="/")

# the main validation object
main_validation = MainValidation()

@app.post("/pre_check")
async def pre_check(request):
    """
    used to check if all the required ingredients are available for the drink
    """
    # used by Scheduler to check the cup before making a drink
    result = {"passed": False, "details": {}}
    return result


@app.post("/update_inventory")
async def update_inventory(request: UpdateInventoryRequest):
    # used by Dashboard to manually update the inventory
    # used by OMS/Scheduler to update the inventory after a robotic step is complete

    # FastAPI already validated the input!
    first_item = request.payload.items[0]
    print(first_item)

    # if update inventory fails send a 400 error
    if not main_validation.post_request(request):
        raise HTTPException(status_code=400, detail="Validation failed")
    
    # if update inventory succeeds send a 200 response
    return {
        "message": "Inventory updated successfully"
    }

@app.post("/check_cup_placed")
async def check_cup_placed(request: ValidationRequest):
    """Run a validation function by name with given parameters."""
    # func_name = request.function
    # if func_name not in VALIDATORS:
    #     return {"error": f"No such validation function '{func_name}'", "passed": False}
    
    result = {"passed": True, "details": {}}
    return result

@app.post("/check_cup_picked")
async def check_cup_picked(request: ValidationRequest):
    """Run a validation function by name with given parameters."""
    # func_name = request.function
    # if func_name not in VALIDATORS:
    #     return {"error": f"No such validation function '{func_name}'", "passed": False}

    result = {"passed": True, "details": {}}
    return result

@app.post("/pre_check") 
async def pre_check(request: ValidationRequest):
    """Run a validation function by name with given parameters."""
    # func_name = request.function
    # if func_name not in VALIDATORS:
    #     return {"error": f"No such validation function '{func_name}'", "passed": False}
    
    result = {"passed": True, "details": {}}
    return result


# NOTE: Check Cup: Inventory response structure {"passed": true/false, "details": {<all results>}}
# NOTE: Update Inventory: {"passed": true/false, "details": {<all results>}} 
# NOTE: get the current inventory{High, med, low} for all ingredients


# NOTE: update the inventory from dashboard and OMS always subtracts from the inventory(cups, syrups, milk from the dashboard OMS everything)
# NOTE: refill from the dashboard + Have a worker to update the status on inventory level change



if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8069)