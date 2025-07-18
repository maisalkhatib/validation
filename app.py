from pydantic_req_structure import UpdateInventoryRequest, PreCheckRequest, CheckCupPlacedRequest, CheckCupPickedRequest, InventoryStatusRequest
from fastapi import FastAPI, HTTPException
import uvicorn

from main_validation import MainValidation


app = FastAPI(title="Inventory Manager", description="Inventory Manager API", docs_url="/")

# the main validation object
main_validation = MainValidation()


@app.post("/update_inventory")
async def update_inventory(request: UpdateInventoryRequest):
    # used by Dashboard to manually update the inventory
    # used by OMS/Scheduler to update the inventory after a robotic step is complete
    # convert the request to a json object
    request_json = request.model_dump()
    # send the request to the main validation object
    main_validation.post_request(request_json)




@app.post("/check_cup_placed")
async def check_cup_placed(request: CheckCupPlacedRequest):
    """Run a validation function by name with given parameters."""
    # func_name = request.function
    # if func_name not in VALIDATORS:
    #     return {"error": f"No such validation function '{func_name}'", "passed": False}
    
    result = {"passed": True, "details": {}}
    return result

@app.post("/check_cup_picked")
async def check_cup_picked(request: CheckCupPickedRequest):
    """Run a validation function by name with given parameters."""
    # func_name = request.function
    # if func_name not in VALIDATORS:
    #     return {"error": f"No such validation function '{func_name}'", "passed": False}

    result = {"passed": True, "details": {}}
    return result

@app.post("/pre_check") 
async def pre_check(request: PreCheckRequest):
    """Run a validation function by name with given parameters."""
    # convert the request to a json object
    request_json = request.model_dump()
    # send the request to the main validation object
    main_validation.post_request(request_json)

    # NOTE: Completed in process_inventory_status_request(payload) diff result for diff client_type
    result = {"passed": True, "details": {}}
    return result


@app.post("/inventory_status")
async def inventory_status(request: InventoryStatusRequest):
    """Run a validation function by name with given parameters."""
    # func_name = request.function
    # if func_name not in VALIDATORS:
    #     return {"error": f"No such validation function '{func_name}'", "passed": False}

    # NOTE: Completed in process_inventory_status_request(payload) diff result for diff client_type
    result = {"passed": True, "details": {}}
    return result


# NOTE: Check Cup: Inventory response structure {"passed": true/false, "details": {<all results>}}
# NOTE: Update Inventory: {"passed": true/false, "details": {<all results>}} 
# NOTE: get the current inventory{High, med, low} for all ingredients


# DONE: update the inventory from dashboard and OMS always subtracts from the inventory(cups, syrups, milk from the dashboard OMS everything)
# NOTE: refill from the dashboard + Have a worker to update the status on inventory level change



if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8069)