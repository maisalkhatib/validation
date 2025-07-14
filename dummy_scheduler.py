"""
Simple test client for the new async validation service
"""

import asyncio
import json
import signal
import sys
from datetime import datetime
from typing import Any, Dict
from shared.rabbitmq_client import RabbitMQClient
import uuid


class ValidationTester:
    """Class-based validation service tester"""
    
    def __init__(self, client_type="scheduler"):
        """Initialize the tester with a specific client type"""
        self.client_type = client_type
        self.client = RabbitMQClient(self.client_type)
        self.connected = False
        self.is_running = False
    
    async def connect(self):
        """Connect to RabbitMQ"""
        try:
            await self.client.connect()
            self.connected = True
            # System handlers
            self.client.register_handler("health", self.handle_health)
            print(f"🔍 Registered health handler")
            print(f"✅ Connected to RabbitMQ as {self.client_type}")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            raise
    
    async def start_service(self):
        """Start the scheduler service and keep it running"""
        try:
            await self.connect()
            self.is_running = True
            print(f"🚀 Scheduler service started and listening for requests...")
            
            # Keep the service running
            while self.is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("🛑 Received interrupt signal, stopping service...")
            await self.stop()
        except Exception as e:
            print(f"❌ Service error: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """Stop the service gracefully"""
        self.is_running = False
        await self.disconnect()
    
    async def disconnect(self):
        """Disconnect from RabbitMQ"""
        if self.client and self.connected:
            await self.client.disconnect()
            self.connected = False
            print("🔌 Disconnected from RabbitMQ")
    
    def _ensure_connected(self):
        """Ensure we're connected before operations"""
        if not self.connected:
            raise Exception("Not connected to RabbitMQ. Call connect() first.")

    async def handle_health(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle health check requests"""
        print("🔍 Health check requested")
        return {
            "status": "healthy",
            "service": "scheduler", 
            "timestamp": datetime.now().isoformat(),
            "capabilities": [
                "dummy_scheduler"
            ]
        }
    
    async def test_validation_service(self):
        """Test all validation service actions"""
        
        try:
            self._ensure_connected()
            
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
            precheck_response = await self.client.send_request(
                target_service="validation",
                action="pre_check",
                data=message
            )

            print(f"Pre-check Result: {precheck_response.get('passed')}")
            if 'details' in precheck_response:
                print(f"Details: {json.dumps(precheck_response, indent=2)}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")

    async def test_single_action(self):
        """Test a single action quickly"""
        
        try:
            self._ensure_connected()
            
            # Quick health check
            response = await self.client.send_request(
                target_service="validation",
                action="health",
                data={}
            )
            
            print(f"Service Status: {response.get('status')}")
            print(f"Service Time: {response.get('timestamp')}")
            
        except Exception as e:
            print(f"❌ Quick test failed: {e}")

    async def test_scheduler_flow(self):
        """Test typical scheduler flow: pre-check then update"""
        
        try:
            self._ensure_connected()
            
            # Step 1: Pre-check ingredients
            print("\n📋 Step 1: Pre-checking ingredients...")
            precheck = await self.client.send_request(
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
                update = await self.client.send_request(
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

    async def test_inventory_status(self):
        """Test inventory status retrieval"""
        
        try:
            self._ensure_connected()
            
            # Test 1: Ingredient Status
            print("\n🔍 Testing Ingredient Status...")
            status_response = await self.client.send_request(
                target_service="validation",
                action="ingredient_status",
                data={}
            )
        
            print(f"Status Retrieved: {json.dumps(status_response, indent=2)}")
        
        except Exception as e:
            print(f"❌ Inventory test failed: {e}")

    async def test_cup_pick_validation(self):
        """Test cup pick validation"""
        
        try:
            self._ensure_connected()
            
            # Test 1: Cup Pick Validation
            print("\n🔍 Testing Cup Pick Validation...")    
            cup_pick_response = await self.client.send_request(
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

    async def test_update_inventory(self):
        """Test update inventory"""
        
        try:
            self._ensure_connected()
            
            # Test 1: Update Inventory
            print("\n🔍 Testing Update Inventory...")
            update_response = await self.client.send_request(
                target_service="validation",
                action="update_inventory",
                data={
                    "ingredients": [
                        {"coffee_beans": {"type": "regular", "amount": 2}},
                        {"milk": {"type": "whole_fat", "amount": 150}},
                        {"cups": {"type": "H9", "amount": 1}},
                        {"syrups": {"type": "vanilla", "amount": 150}},
                        {"sauces": {"type": "white_chocolate", "amount": 150}},
                        {"premixes": {"type": "mocha_frappe", "amount": 150}},
                    ]
                }
            )   
            
            print(f"Update Result: {update_response.get('passed')}")
            
        except Exception as e:
            print(f"❌ Update inventory test failed: {e}")

    async def test_precheck_inventory(self):
        """Test precheck inventory"""
        
        try:
            self._ensure_connected()
            
            # Test 1: Precheck Inventory
            print("\n🔍 Testing precheck Inventory...")
            precheck_response = await self.client.send_request(
                target_service="validation",
                action="pre_check",
                data={
                    "items": [
                        {
                            "drink_name": "americano",
                            "size": "large",
                            "cup_id": "H9",
                            "temperature": "hot",
                            "ingredients": {
                                "coffee_beans": {"type": "regular", "amount": 2}
                            }
                        }
                    ]
                }
            )   
            
            print(f"precheck Result: {precheck_response.get('passed')}")
            
        except Exception as e:
            print(f"❌ precheck inventory test failed: {e}")

    def run_test_menu(self):
        """Run interactive test menu"""
        print("🧪 Validation Service Test Client")
        print("=" * 50)
        
        print("\nChoose test:")
        print("1. Full Test Suite")
        print("2. Quick Health Check")
        print("3. Scheduler Flow Test")
        print("4. Inventory Status Test")
        print("5. Cup Pick Validation Test")
        print("6. Update Inventory Test")
        print("7. Precheck Inventory Test")
        print("8. Start Service (Keep Running)")
        
        choice = input("\nEnter choice (1-8): ").strip()
        
        if choice == "1":
            asyncio.run(self.test_validation_service())
        elif choice == "2":
            asyncio.run(self.test_single_action())
        elif choice == "3":
            asyncio.run(self.test_scheduler_flow())
        elif choice == "4":
            asyncio.run(self.test_inventory_status())
        elif choice == "5":
            asyncio.run(self.test_cup_pick_validation())
        elif choice == "6":
            asyncio.run(self.test_update_inventory())
        elif choice == "7":
            asyncio.run(self.test_precheck_inventory())
        elif choice == "8":
            asyncio.run(self.start_service())
        else:
            print("Invalid choice, starting service...")
            asyncio.run(self.start_service())


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n🛑 Received signal {signum}, shutting down...")
    sys.exit(0)


async def main():
    """Main entry point for the validation tester - same pattern as validation_app2.py"""
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create tester instance
    tester = ValidationTester(client_type="scheduler")
    
    try:
        # Start the service and keep it running (like validation_app2.py)
        await tester.start_service()
        
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
    finally:
        # Clean up connection
        try:
            await tester.stop()
        except Exception as e:
            print(f"⚠️ Warning: Could not disconnect cleanly: {e}")


if __name__ == "__main__":
    print("🧪 Starting Validation Test Client")
    print("🔧 Using the same connection pattern as validation_app2.py")
    
    # Same pattern as validation_app2.py - start as a service
    asyncio.run(main())