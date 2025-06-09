# test file to simulate the request to the main_validation.py
import json

from main_validation import MainValidation

main_validation = MainValidation()


def test_update_inventory_request():
    with open("sample_request_structures/sample_update_inventory_request_2.json", "r") as f:
        payload = json.load(f)

    main_validation.process_update_inventory_request(payload)
    print("Inventory updated successfully")

def test_ingredient_status_request():
    # USED BY DASHBOARD
    with open("sample_request_structures/sample_dashboard_ingredient_status_request.json", "r") as f:
        payload = json.load(f)

    main_validation.process_inventory_status_request(payload)
    print("Inventory status request processed successfully")


def test_pre_check_request():
    with open("sample_request_structures/sample_pre_check_request.json", "r") as f:
        payload = json.load(f)

    main_validation.process_inventory_status_request(payload)
    print("Pre check request processed successfully")

if __name__ == "__main__":
    # test_update_inventory_request()
    test_ingredient_status_request()
    pass