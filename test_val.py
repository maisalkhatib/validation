"""
Simple test client for the new async validation service
"""

import asyncio
import json
from datetime import datetime
from shared.rabbitmq_client import RabbitMQClient
import uuid

async def test_validation_service():
    """Test all validation service actions"""
    
    # Create client
    client = RabbitMQClient("scheduler")
    
    try:
        # Connect to RabbitMQ
        await client.connect()
        print("✅ Connected to RabbitMQ")
        
        # # Test 1: Health Check
        # print("\n🔍 Testing Health Check...")
        # health_response = await client.send_request(
        #     target_service="validation",
        #     action="health",
        #     data={}
        # )
        # print(f"Health Status: {health_response.get('status')}")
        # print(f"Capabilities: {health_response.get('capabilities')}")
        
        request_id = str(uuid.uuid4())
        message = {
                "items": [
                    {
                        "drink_name": "cappuccino",
                        "size": "medium",
                        "cup_id": "H9",
                        "temperature": "hot",
                        "ingredients": {
                            "espresso": {
                                "type": "regular",
                                "amount": 2
                            },
                            "milk": {
                                "type": "whole",
                                "amount": 150
                            }
                        }
                    },
                    {
                        "drink_name": "americano",
                        "size": "large",
                        "cup_id": "H9",
                        "temperature": "hot",
                        "ingredients": {
                            "espresso": {
                                "type": "regular",
                                "amount": 3
                            }
                        }
                    }
                ]
            }

        # Test 2: Pre-Check
        print("\n🔍 Testing Pre-Check...")
        precheck_response = await client.send_request(
            target_service="validation",
            action="pre_check",
            data=message
        )

        print(f"Pre-check Result: {precheck_response.get('passed')}")
        if 'details' in precheck_response:
            print(f"Details: {json.dumps(precheck_response, indent=2)}")
        
        # # Test 3: Ingredient Status
        # print("\n🔍 Testing Ingredient Status...")
        # status_response = await client.send_request(
        #     target_service="validation",
        #     action="ingredient_status",
        #     data={}
        # )
        # print(f"Status Retrieved: {'details' in status_response}")
        # if 'details' in status_response:
        #     # Show just coffee_beans status as example
        #     coffee_status = status_response['details'].get('details', {}).get('coffee_beans')
        #     if coffee_status:
        #         print(f"Coffee Beans Status: {json.dumps(coffee_status, indent=2)}")
        
        # # Test 4: Update Inventory
        # print("\n🔍 Testing Update Inventory...")
        # update_response = await client.send_request(
        #     target_service="validation",
        #     action="update_inventory",
        #     data={
        #         "ingredients": [
        #             {"espresso": {"type": "regular", "amount": 1}},
        #             {"milk": {"type": "whole", "amount": 100}},
        #             {"cup": {"type": "H9", "amount": 1}}
        #         ]
        #     }
        # )
        # print(f"Update Result: {update_response.get('passed')}")
        # if 'details' in update_response:
        #     print(f"Update Details: {json.dumps(update_response['details'], indent=2)}")
        
        # # Test 5: Refill Inventory
        # print("\n🔍 Testing Refill Inventory...")
        # refill_response = await client.send_request(
        #     target_service="validation",
        #     action="refill_inventory",
        #     data={
        #         "ingredients": [
        #             {"ingredient_type": "coffee_beans", "subtype": "regular"},
        #             {"ingredient_type": "milk", "subtype": "whole"}
        #         ]
        #     }
        # )
        # print(f"Refill Result: {refill_response.get('passed')}")
        # if 'details' in refill_response:
        #     print(f"Refill Details: {json.dumps(refill_response['details'], indent=2)}")
        
        # # Test 6: Computer Vision (Placeholder)
        # print("\n🔍 Testing Computer Vision...")
        # cv_response = await client.send_request(
        #     target_service="validation",
        #     action="check_cup_placed",
        #     data={"cup_position": "center"}
        # )
        # print(f"CV Result: {cv_response.get('passed')}")
        # print(f"CV Message: {cv_response.get('details', {}).get('message')}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    finally:
        # Disconnect
        await client.disconnect()
        print("\n🔌 Disconnected from RabbitMQ")

async def test_single_action():
    """Test a single action quickly"""
    
    client = RabbitMQClient("quick_test")
    
    try:
        await client.connect()
        print("✅ Quick Test Connected")
        
        # Quick health check
        response = await client.send_request(
            target_service="validation",
            action="health",
            data={}
        )
        
        print(f"Service Status: {response.get('status')}")
        print(f"Service Time: {response.get('timestamp')}")
        
    except Exception as e:
        print(f"❌ Quick test failed: {e}")
    
    finally:
        await client.disconnect()

async def test_scheduler_flow():
    """Test typical scheduler flow: pre-check then update"""
    
    client = RabbitMQClient("scheduler_test")
    
    try:
        await client.connect()
        print("✅ Scheduler Test Connected")
        
        # Step 1: Pre-check ingredients
        print("\n📋 Step 1: Pre-checking ingredients...")
        precheck = await client.send_request(
            target_service="validation",
            action="pre_check",
            data={
                "items": [{
                    "drink_name": "americano",
                    "cup_id": "H9",
                    "ingredients": {
                        "espresso": {"type": "regular", "amount": 2}
                    }
                }]
            }
        )
        
        if precheck.get('passed'):
            print("✅ Ingredients available - proceeding with order")
            
            # Step 2: Update inventory after making coffee
            print("\n☕ Step 2: Making coffee and updating inventory...")
            update = await client.send_request(
                target_service="validation",
                action="update_inventory",
                data={
                    "ingredients": [
                        {"espresso": {"type": "regular", "amount": 2}},
                        {"cup": {"type": "H9", "amount": 1}}
                    ]
                }
            )
            
            if update.get('passed'):
                print("✅ Inventory updated successfully")
            else:
                print(f"❌ Inventory update failed: {update.get('error')}")
        else:
            print(f"❌ Pre-check failed: {precheck.get('error')}")
            print("🚫 Cannot proceed with order")
        
    except Exception as e:
        print(f"❌ Scheduler test failed: {e}")
    
    finally:
        await client.disconnect()

async def test_inventory_status():
    """Test inventory status retrieval"""
    client = RabbitMQClient("dashboard")
    
    try:
        await client.connect()
        print("✅ Inventory Test Connected")
        
        # Test 1: Ingredient Status
        print("\n🔍 Testing Ingredient Status...")
        status_response = await client.send_request(
            target_service="validation",
            action="ingredient_status",
            data={}
        )
    
        print(f"Status Retrieved: {json.dumps(status_response, indent=2)}")
    
    except Exception as e:
        print(f"❌ Inventory test failed: {e}")
    
    finally:
        await client.disconnect()

async def test_cup_pick_validation():
    """Test cup pick validation"""
    client = RabbitMQClient("scheduler")
    
    try:
        await client.connect()
        print("✅ Cup Pick Test Connected")
        
        # Test 1: Cup Pick Validation
        print("\n🔍 Testing Cup Pick Validation...")    
        cup_pick_response = await client.send_request(
            target_service="validation",
            action="check_cup_picked",
            data={
                "arm_id": "arm1",
                "cup_temperature": "hot",
            }
        )
        
        print(f"Cup Pick Result: {cup_pick_response.get('passed')}")
        
    except Exception as e:
        print(f"❌ Cup pick test failed: {e}")
    
    finally:
        await client.disconnect()

async def test_update_inventory():
    """Test update inventory"""
    client = RabbitMQClient("scheduler")
    
    try:
        await client.connect()
        print("✅ Update Inventory Test Connected")
        
        # Test 1: Update Inventory
        print("\n🔍 Testing Update Inventory...")
        update_response = await client.send_request(
            target_service="validation",
            action="update_inventory",
            data={
                "ingredients": [
                    {"espresso": {"type": "regular", "amount": 2}},
                    {"cup": {"type": "H9", "amount": 1}},
                    {"milk": {"type": "whole", "amount": 150}},
                    # {"espresso": {"type": "decaf", "amount": 1}},
                    # {"espresso": {"type": "regular", "amount": 1}},
                ]
            }
        )   
        
        print(f"Update Result: {update_response.get('passed')}")

        # update_response2 = await client.send_request(
        #     target_service="validation",
        #     action="update_inventory",
        #     data={
        #         "ingredients": [
        #             {"espresso": {"type": "regular", "amount": 2}},
        #             {"cup": {"type": "H7", "amount": 1}}
        #         ]
        #     }
        # )
        
        # print(f"Update Result: {update_response2.get('passed')}")
        
    except Exception as e:
        print(f"❌ Update inventory test failed: {e}")
    
    finally:
        await client.disconnect()
def main():
    """Main test runner"""
    print("🧪 Validation Service Test Client")
    print("=" * 50)
    
    print("\nChoose test:")
    print("1. Full Test Suite")
    print("2. Quick Health Check")
    print("3. Scheduler Flow Test")
    print("4. Inventory Status Test")
    print("5. Cup Pick Validation Test")
    print("6. Update Inventory Test")
    
    choice = input("\nEnter choice (1-6): ").strip()
    
    if choice == "1":
        asyncio.run(test_validation_service())
    elif choice == "2":
        asyncio.run(test_single_action())
    elif choice == "3":
        asyncio.run(test_scheduler_flow())
    elif choice == "4":
        asyncio.run(test_inventory_status())
    elif choice == "5":
        asyncio.run(test_cup_pick_validation())
    elif choice == "6":
        asyncio.run(test_update_inventory())
    else:
        print("Invalid choice, running quick test...")
        asyncio.run(test_single_action())

if __name__ == "__main__":
    main()