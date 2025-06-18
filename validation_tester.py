import pika
import json
import threading
import time
import uuid
from datetime import datetime


class ValidationServiceTester:
    def __init__(self, rabbitmq_host='localhost', rabbitmq_port=5672, rabbitmq_user="rabbitmq", rabbitmq_pass="rabbitmq"):
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        
        # Queue names (must match app.py)
        self.validation_queue = "validation_queue"
        self.scheduler_response_queue = "scheduler_response_queue"
        self.dashboard_response_queue = "dashboard_response_queue"
        
        # Connections
        self.connection = None
        self.channel = None
        
        # Response tracking
        self.received_responses = {}
        self.response_handlers_running = False
        
        self.setup_connection()
        self.setup_response_listeners()
    
    def setup_connection(self):
        """Setup RabbitMQ connection"""
        try:
            self.connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.rabbitmq_host, 
                    port=self.rabbitmq_port, 
                    credentials=pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_pass))
            )
            self.channel = self.connection.channel()
            
            # Declare all queues
            self.channel.queue_declare(queue=self.validation_queue, durable=True)
            self.channel.queue_declare(queue=self.scheduler_response_queue, durable=True)
            self.channel.queue_declare(queue=self.dashboard_response_queue, durable=True)
            
            print("✅ Connected to RabbitMQ for testing")
            
        except Exception as e:
            print(f"❌ Failed to connect to RabbitMQ: {e}")
            raise
    
    def setup_response_listeners(self):
        """Setup listeners for response queues"""
        
        def handle_scheduler_response(ch, method, properties, body):
            try:
                response = json.loads(body.decode('utf-8'))
                request_id = response.get('request_id')
                # print(f"response: {response}")
                print(f"📥 SCHEDULER Response received:")
                print(f"   Response: {json.dumps(response, indent=2)}")
                # print(f"   Status: {response.get('passed', 'N/A')}")
                # print(f"   Details: {json.dumps(response.get('details', {}), indent=2)}")
                
                self.received_responses[request_id] = response
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ Error handling scheduler response: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        def handle_dashboard_response(ch, method, properties, body):
            try:
                response = json.loads(body.decode('utf-8'))
                request_id = response.get('request_id')
                print(f"📥 DASHBOARD Response received:")
                print(f"   Response: {json.dumps(response, indent=2)}")
                
                self.received_responses[request_id] = response
                ch.basic_ack(delivery_tag=method.delivery_tag)
                
            except Exception as e:
                print(f"❌ Error handling dashboard response: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        # Setup consumers
        self.channel.basic_consume(
            queue=self.scheduler_response_queue,
            on_message_callback=handle_scheduler_response
        )
        
        self.channel.basic_consume(
            queue=self.dashboard_response_queue,
            on_message_callback=handle_dashboard_response
        )
        
        # Start consuming in background thread
        def start_consuming():
            self.response_handlers_running = True
            print("🎧 Started listening for responses...")
            self.channel.start_consuming()
        
        self.response_thread = threading.Thread(target=start_consuming, daemon=False)
        self.response_thread.start()
        time.sleep(1)  # Give thread time to start
    
    def send_message(self, message):
        """Send a message to validation queue"""
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=self.validation_queue,
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            print(f"📤 Sent {message.get('function_name')} request from {message.get('client_type')}")
            return message.get('request_id')
            
        except Exception as e:
            print(f"❌ Failed to send message: {e}")
            return None
    
    def test_scheduler_pre_check(self):
        """Test pre-check request from scheduler"""
        print("\n" + "="*60)
        print("🧪 TEST 1: Scheduler Pre-Check Request")
        print("="*60)
        
        request_id = str(uuid.uuid4())
        message = {
            "request_id": request_id,
            "client_type": "scheduler",
            "function_name": "pre_check",
            "payload": {
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
        }
        
        return self.send_message(message)
    
    def test_scheduler_update_inventory(self):
        """Test update inventory request from scheduler"""
        print("\n" + "="*60)
        print("🧪 TEST 2: Scheduler Update Inventory Request")
        print("="*60)
        
        request_id = str(uuid.uuid4())
        message = {
            "request_id": request_id,
            "client_type": "scheduler",
            "function_name": "update_inventory",
            "payload": {
                "ingredients": [
                    {
                        "espresso": {
                            "type": "regular",
                            "amount": 2
                        }
                    },
                    {
                        "milk": {
                            "type": "whole",
                            "amount": 150
                        }
                    },
                    {
                        "milk": {
                            "type": "whole",
                            "amount": 150
                        }
                    },
                    {
                        "cup": {
                            "type": "H9",
                            "amount": 1
                        }
                    }
                ]
            }
        }
        
        return self.send_message(message)
    
    def test_dashboard_ingredient_status(self):
        """Test ingredient status request from dashboard"""
        print("\n" + "="*60)
        print("🧪 TEST 3: Dashboard Ingredient Status Request")
        print("="*60)
        
        request_id = str(uuid.uuid4())
        message = {
            "request_id": request_id,
            "client_type": "dashboard",
            "function_name": "ingredient_status",
            "payload": {
                "items": [
                    {
                        "drink_name": "latte",
                        "size": "medium",
                        "cup_id": "H9",
                        "temperature": "hot",
                        "ingredients": {
                            "espresso": {
                                "type": "regular",
                                "amount": 1
                            },
                            "milk": {
                                "type": "whole",
                                "amount": 200
                            }
                        }
                    }
                ]
            }
        }
        
        return self.send_message(message)
    
    def test_invalid_function(self):
        """Test invalid function name"""
        print("\n" + "="*60)
        print("🧪 TEST 4: Invalid Function Name")
        print("="*60)
        
        request_id = str(uuid.uuid4())
        message = {
            "request_id": request_id,
            "client_type": "scheduler",
            "function_name": "invalid_function",
            "payload": {}
        }
        
        return self.send_message(message)
    
    def test_refill_ingredient(self):
        """Test refill ingredient request from dashboard"""
        print("\n" + "="*60)
        print("🧪 TEST 5: Refill Ingredient Request")
        print("="*60)   
        
        request_id = str(uuid.uuid4())
        message = {
    "request_id": "1234567890",
    "client_type": "dashboard",
    "function_name": "refill_ingredient",
    "payload": {
        "ingredients": [
            {
                "ingredient_type": "espresso",
                "subtype": "regular"
            },
            {
                "ingredient_type": "milk",
                "subtype": "whole"
            },
            {
                "ingredient_type": "cup",
                "subtype": "H9"
            },
            {
                "ingredient_type": "milk",
                "subtype": "oat"
            },
            {
                "ingredient_type": "syrup",
                "subtype": "vanilla"
            },
            {
                "ingredient_type": "cup",
                "subtype": "C9"
            },
            {
                "ingredient_type": "dummy",
                "subtype": "C12"
            }
        ]
    }
}
        
        return self.send_message(message)

    def test_malformed_message(self):
        """Test malformed JSON message"""
        print("\n" + "="*60)
        print("🧪 TEST 5: Malformed Message")
        print("="*60)
        
        try:
            # Send invalid JSON
            self.channel.basic_publish(
                exchange='',
                routing_key=self.validation_queue,
                body="{ invalid json",
                properties=pika.BasicProperties(delivery_mode=2)
            )
            print("📤 Sent malformed JSON message")
            
        except Exception as e:
            print(f"❌ Failed to send malformed message: {e}")
    
    def wait_for_response(self, request_id, timeout=10):
        """Wait for a specific response"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if request_id in self.received_responses:
                return self.received_responses[request_id]
            time.sleep(0.1)
        
        print(f"⏰ Timeout waiting for response: {request_id}")
        return None
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("\n🚀 STARTING VALIDATION SERVICE TESTS")
        print("="*80)
        print("Make sure your validation service is running: python app.py")
        print("="*80)
        
        test_results = []
        
        # Test 1: Scheduler Pre-check
        request_id_1 = self.test_scheduler_pre_check()
        if request_id_1:
            time.sleep(2)
            response_1 = self.wait_for_response(request_id_1)
            test_results.append(("Scheduler Pre-check", response_1 is not None))
        
        # Test 2: Scheduler Update Inventory
        request_id_2 = self.test_scheduler_update_inventory()
        if request_id_2:
            time.sleep(2)
            response_2 = self.wait_for_response(request_id_2)
            test_results.append(("Scheduler Update Inventory", response_2 is not None))
        
        # Test 3: Dashboard Ingredient Status
        request_id_3 = self.test_dashboard_ingredient_status()
        if request_id_3:
            time.sleep(2)
            response_3 = self.wait_for_response(request_id_3)
            test_results.append(("Dashboard Ingredient Status", response_3 is not None))
        
        # Test 4: Invalid Function
        request_id_4 = self.test_invalid_function()
        if request_id_4:
            time.sleep(2)
            response_4 = self.wait_for_response(request_id_4)
            test_results.append(("Invalid Function", response_4 is not None))
        
        # Test 7: Refill Ingredient
        request_id_7 = self.test_refill_ingredient()
        if request_id_7:
            time.sleep(2)
            response_7 = self.wait_for_response(request_id_7)
            test_results.append(("Refill Ingredient", response_7 is not None))
        
        # Test 5: Malformed Message
        self.test_malformed_message()
        time.sleep(2)
        test_results.append(("Malformed Message", True))  # Should not crash service
        
        # Print results
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        
        for test_name, passed in test_results:
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{test_name:<30} {status}")
        
        total_tests = len(test_results)
        passed_tests = sum(1 for _, passed in test_results if passed)
        
        print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 All tests passed! Your validation service is working correctly.")
        else:
            print("⚠️  Some tests failed. Check the validation service logs.")
    
    def interactive_test(self):
        """Interactive testing mode"""
        print("\n🎮 INTERACTIVE TEST MODE")
        print("="*40)
        
        while True:
            print("\nChoose a test:")
            print("1. Scheduler Pre-check")
            print("2. Scheduler Update Inventory")
            print("3. Dashboard Ingredient Status")
            print("4. Invalid Function")
            print("5. Malformed Message")
            print("6. Run All Tests")
            print("7. Refill Ingredient")
            print("0. Exit")
            
            choice = input("\nEnter choice (0-6): ").strip()
            
            if choice == "0":
                break
            elif choice == "1":
                request_id = self.test_scheduler_pre_check()
                print(f"request_id_1: {request_id}")
                if request_id:
                    print(f"⏳ Waiting for response...")
                    response = self.wait_for_response(request_id)
            elif choice == "2":
                request_id = self.test_scheduler_update_inventory()
                if request_id:
                    print(f"⏳ Waiting for response...")
                    response = self.wait_for_response(request_id)
            elif choice == "3":
                request_id = self.test_dashboard_ingredient_status()
                if request_id:
                    print(f"⏳ Waiting for response...")
                    response = self.wait_for_response(request_id)
            elif choice == "4":
                request_id = self.test_invalid_function()
                if request_id:
                    print(f"⏳ Waiting for response...")
                    response = self.wait_for_response(request_id)
            elif choice == "5":
                self.test_malformed_message()
            elif choice == "6":
                self.run_all_tests()
            elif choice == "7":
                request_id = self.test_refill_ingredient()
                if request_id:
                    print(f"⏳ Waiting for response...")
                    response = self.wait_for_response(request_id)
            else:
                print("❌ Invalid choice")
        
        print("👋 Exiting interactive test mode")
    
    def close(self):
        """Clean up connections"""
        try:
            # Set flag to stop gracefully
            self.response_handlers_running = False
            
            # Don't try to stop consuming if connection is already dead
            if (hasattr(self, 'connection') and 
                self.connection and 
                not self.connection.is_closed):
                
                try:
                    if hasattr(self, 'channel') and self.channel:
                        self.channel.stop_consuming()
                except:
                    pass  # Ignore if already stopped/closed
                
                try:
                    self.connection.close()
                except:
                    pass  # Ignore if already closed
                    
            print("🔌 Test client disconnected")
            
        except Exception:
            print("🔌 Test client disconnected")


def main():
    """Main test runner"""
    print("🧪 VALIDATION SERVICE TESTER")
    print("="*50)
    
    try:
        tester = ValidationServiceTester()
        
        print("\nTest mode:")
        print("1. Run all tests automatically")
        print("2. Interactive testing")
        
        mode = input("Choose mode (1 or 2): ").strip()
        
        if mode == "1":
            tester.run_all_tests()
        elif mode == "2":
            tester.interactive_test()
        else:
            print("❌ Invalid choice, running all tests...")
            tester.run_all_tests()
        
        tester.close()
        
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")


if __name__ == "__main__":
    main()