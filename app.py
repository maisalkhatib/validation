from pydantic_req_structure import UpdateInventoryRequest

app = FastAPI(title="Inventory Manager", description="Inventory Manager API", docs_url="/")

@app.post("/update-inventory")
def update_inventory(request: UpdateInventoryRequest):
    # FastAPI already validated the input!
    first_item = request.payload.items[0]
    return {
        "request_id": request.request_id,
        "drink": first_item.drink_name,
        "cup_id": first_item.cup_id,
        "ingredients": list(first_item.ingredients.keys())
    }

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8069)