# test file to simulate the request to the main_validation.py
import os
import json

from main_validation import MainValidation

main_validation = MainValidation()

# with os get the current directory
current_dir = os.getcwd()
print(f"Current directory: {current_dir}")

# get the path to the sample_request_structures folder
sample_request_structures_path = os.path.join(current_dir, "sample_request_structures")


def test_update_inventory_request():

    with open("sample_request_structures/sample_update_inventory_request_2.json", "r") as f:
    # with open("sample_request_structures/sample_update_inventory_request_2.json", "r") as f:
        payload = json.load(f)

    main_validation.process_update_inventory_request(payload)
    print("Inventory updated successfully")

def test_ingredient_status_request():
    # USED BY DASHBOARD
    with open(os.path.join(sample_request_structures_path, "sample_dashboard_ingredient_status_request.json"), "r") as f:
    # with open("sample_request_structures/sample_dashboard_ingredient_status_request.json", "r") as f:
        payload = json.load(f)

    main_validation.process_inventory_status_request(payload)
    print("Inventory status request processed successfully")


def test_pre_check_request():
    # # with os get the current directory
    # current_dir = os.getcwd()
    # print(f"Current directory: {current_dir}")

    # # get the path to the sample_request_structures folder
    # sample_request_structures_path = os.path.join(current_dir, "sample_request_structures")
    print(f"Sample request structures path: {sample_request_structures_path}")


    with open(os.path.join(sample_request_structures_path, "sample_pre_check_request.json"), "r") as f:

        payload = json.load(f)

    main_validation.process_inventory_status_request(payload)
    print("Pre check request processed successfully")

if __name__ == "__main__":
    # test_update_inventory_request()
    # test_ingredient_status_request()
    test_pre_check_request()