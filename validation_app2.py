"""
Simplified Validation Service App using async RabbitMQ communication
Request-response only, with live inventory updates for API Bridge
"""

import asyncio
import logging
import signal
import sys
from typing import Dict, Any
from datetime import datetime
import json
# Import your existing business logic (unchanged)
from main_validation import MainValidation
# Import the shared RabbitMQ client
from shared.rabbitmq_client import RabbitMQClient

class ValidationServiceApp:
    def __init__(self):
        """Initialize validation service with async RabbitMQ communication"""
        self.service_name = "validation"
        
        # Your existing business logic (unchanged)
        self.main_validation = MainValidation()
        
        # New async communication clients
        self.rabbitmq_client = RabbitMQClient(self.service_name)
        
        # Service state
        self.is_running = False
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Silence Pika's verbose DEBUG logs
        logging.getLogger('pika').setLevel(logging.WARNING)
    
    async def start(self):
        """Start the validation service and register handlers"""
        try:
            # Connect to RabbitMQ
            await self.rabbitmq_client.connect()
            
            # Register handlers for all validation actions
            self.register_handlers()

            # START THE PERIODIC COFFEE BEANS DETECTION
            await self.main_validation.start_periodic_detection()
            
            self.is_running = True
            self.logger.info(f"Validation service started. Listening on service: {self.service_name}")
            self.logger.info("Available actions: pre_check, update_inventory, ingredient_status, refill_inventory")
            
            # Run forever
            try:
                await asyncio.Future()
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal, stopping service...")
                await self.stop()
                
        except Exception as e:
            self.logger.error(f"Failed to start validation service: {e}")
            await self.stop()
            raise
    
    def register_handlers(self):
        """Register message handlers for all validation actions"""
        
        # Inventory validation handlers
        self.rabbitmq_client.register_handler("pre_check", self.handle_pre_check)
        self.rabbitmq_client.register_handler("update_inventory", self.handle_update_inventory)
        self.rabbitmq_client.register_handler("inventory_status", self.handle_ingredient_status)
        self.rabbitmq_client.register_handler("inventory_refill", self.handle_refill_inventory)
        self.rabbitmq_client.register_handler("category_summary", self.handle_category_summary)
        self.rabbitmq_client.register_handler("stock_level", self.handle_inventory_stock_level)
        self.rabbitmq_client.register_handler("category_count", self.handle_category_count)
        self.rabbitmq_client.register_handler("category_info", self.handle_category_info)
        
        # Computer vision handlers (placeholders)
        self.rabbitmq_client.register_handler("check_cup_picked", self.handle_check_cup_picked)
        self.rabbitmq_client.register_handler("check_cup_placed", self.handle_check_cup_placed)
        self.rabbitmq_client.register_handler("check_coffee_beans", self.handle_check_coffee_beans)
        
        # System handlers
        self.rabbitmq_client.register_handler("health", self.handle_health)
        
        self.logger.info("All message handlers registered")
    
    # =============================================================================
    # INVENTORY HANDLERS
    # =============================================================================
    
    async def handle_pre_check(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle pre-check requests - validate ingredient availability before order processing"""
        try:
            # self.logger.info(f"Processing pre_check request: {data.get('request_id', 'no-id')}")
            print(f"Processing pre_check request: {data}")
            # Convert new format to your existing format
            # request_data = self.convert_to_validation_format(data, "pre_check")
            
            # Call your existing business logic (synchronous)
            result = self.main_validation.process_pre_check_request(data)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in pre_check: {e}")
            return {
                "request_id": data.get("request_id"),
                "passed": False,
                "error": f"Pre-check failed: {str(e)}"
            }
    
    async def handle_update_inventory(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle inventory update requests - update ingredient levels after consumption"""
        try:
            self.logger.info(f"Processing update_inventory request: {data.get('request_id', 'no-id')}")
            
            # Convert new format to your existing format
            request_data = self.convert_to_validation_format(data, "update_inventory")
            
            # Call your existing business logic
            result = self.main_validation.process_update_inventory_request(request_data)
            
            # Track affected categories
            affected_categories = set()
            
            # Extract categories from the request
            for item in data.get("payload", {}).get("ingredients", []):
                for ingredient, details in item.items():
                    if ingredient == "espresso":
                        affected_categories.add("coffee_beans")
                    elif ingredient == "cup":
                        affected_categories.add("cups")
                    else:
                        affected_categories.add(ingredient)
            
            # Send category-specific updates only if successful
            if result.get("passed"):
                await self.send_inventory_status_event(affected_categories)
                await self.send_all_inventory_status()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in update_inventory: {e}")
            return {
                "request_id": data.get("request_id"),
                "passed": False,
                "error": f"Inventory update failed: {str(e)}"
            }
    
    # async def handle_ingredient_status(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
    #     """Handle ingredient status requests - get current inventory status and levels"""
    #     try:
    #         self.logger.info(f"Processing ingredient_status request: {data.get('request_id', 'no-id')}")
            
    #         # Convert new format to your existing format
    #         request_data = self.convert_to_validation_format(data, "ingredient_status")
            
    #         # Call your existing business logic
    #         result = self.main_validation.process_ingredient_status_request(request_data)
            
    #         return result
            
    #     except Exception as e:
    #         self.logger.error(f"Error in ingredient_status: {e}")
    #         return {
    #             "request_id": data.get("request_id"),
    #             "passed": False,
    #             "error": f"Ingredient status failed: {str(e)}"
    #         }
    
    
    async def handle_ingredient_status(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle ingredient status requests - get current inventory status and levels"""
        try:
            self.logger.info(f"Processing ingredient_status request: {data.get('request_id', 'no-id')}")
            print("###################################")
            print(f"Ingredient status request: {data}")
            print("###################################")
            # Convert new format to your existing format
            request_data = {
                "request_id": data.get("request_id", f"async-{datetime.now().timestamp()}"),
                "client_type": "api_bridge",
                "function_name": "ingredient_status",
                "payload": {
                    "ingredient_type": data.get("payload", {}).get("ingredient_type"),
                    "subtype": data.get("payload", {}).get("subtype")
                }
            }
            print("###################################")
            print(f"Ingredient status request: {json.dumps(request_data, indent=2)}")
            print("###################################")
            result = self.main_validation.process_ingredient_status_request(request_data)
            
            print(f"Ingredient status result: {json.dumps(result, indent=2)}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error in ingredient_status: {e}")
            return {
                "request_id": data.get("request_id"),
                "passed": False,
                "error": f"Ingredient status failed: {str(e)}"
            }
    
    async def handle_category_info(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle category info requests"""
        try:
            request_data = {
                "request_id": data.get("request_id", f"async-{datetime.now().timestamp()}"),
                "client_type": "api_bridge",
                "function_name": "category_info",
                "payload": {}
            }
            result = self.main_validation.process_category_info_request(request_data)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in category_info: {e}")
            return {
                "request_id": data.get("request_id"),
                "passed": False,
                "error": f"Category info failed: {str(e)}"
            }
    

    async def handle_refill_inventory(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle inventory refill requests - refill inventory to maximum levels"""
        try:
            self.logger.info(f"Processing refill_inventory request: {data.get('request_id', 'no-id')}")
            
            # Convert new format to your existing format
            # request_data = self.convert_to_validation_format(data, "refill_ingredient")
            # Track affected categories
            affected_categories = set()
            
            # Extract category from request
            ingredient_type = data.get("payload", {}).get("ingredient_type")
            subtype = data.get("payload", {}).get("subtype")
            function_name = data.get("payload", {}).get("function_name")
            print(f"inside handle_refill_inventory: function_name: {function_name}")

            print(f"inside handle_refill_inventory: ingredient_type: {ingredient_type}, subtype: {subtype}")
            
            if ingredient_type:
                affected_categories.add(ingredient_type)
            else:
                # If no specific type, all categories are affected
                affected_categories = {"coffee_beans", "cups", "milk", "syrup"}
            
            # Call your existing business logic
            result = self.main_validation.process_refill_ingredient_request(data)
            
            # Send category-specific updates only if successful
            if result.get("passed"):
                await self.send_inventory_status_event(affected_categories)
                await self.send_all_inventory_status()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in refill_inventory: {e}")
            return {
                "request_id": data.get("request_id"),
                "passed": False,
                "error": f"Inventory refill failed: {str(e)}"
            }
    
    async def handle_category_summary(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle category summary requests"""
        try:
            request_data = {
                "request_id": data.get("request_id", f"async-{datetime.now().timestamp()}"),
                "client_type": "api_bridge",
                "function_name": "category_summary",
                "payload": {}
            }
            
            result = self.main_validation.process_category_summary_request(request_data)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in category_summary: {e}")
            return {
                "request_id": data.get("request_id"),
                "passed": False,
                "error": f"Category summary failed: {str(e)}"
            }

    async def handle_inventory_stock_level(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle inventory stock level statistics requests"""
        try:
            request_data = {
                "request_id": data.get("request_id", f"async-{datetime.now().timestamp()}"),
                "client_type": "api_bridge",
                "function_name": "stock_level",
                "payload": {}
            }
            
            result = self.main_validation.process_stock_level_request(request_data)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in stock_level: {e}")
            return {
                "request_id": data.get("request_id"),
                "passed": False,
                "error": f"Stock level failed: {str(e)}"
            }
    
    async def handle_category_count(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle category count requests"""
        try:
            request_data = {
                "request_id": data.get("request_id", f"async-{datetime.now().timestamp()}"),
                "client_type": "api_bridge",
                "function_name": "category_count",
                "payload": {}
            }
            print(f"Category count request: {request_data}")
            result = self.main_validation.process_category_count_request(request_data)
            print(f"Category count result: {result}")
            return result
        
        except Exception as e:
            self.logger.error(f"Error in category_count: {e}")
            return {
                "request_id": data.get("request_id"),
                "passed": False,
                "error": f"Category count failed: {str(e)}"
            }


    # =============================================================================
    # COMPUTER VISION HANDLERS (Placeholders)
    # =============================================================================
    
    async def handle_check_cup_picked(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle cup pick validation requests"""
        try:
            self.logger.info(f"Processing check_cup_picked request: {data.get('request_id', 'no-id')}")
            cv_response = await self.rabbitmq_client.send_request(
                target_service="video-stream",
                action="check_cup_picked",
                data=data
            )

            if cv_response.get("success"):
                detection_result = cv_response.get("detected", False)

                if detection_result:
                    result = {
                        "request_id": data.get("request_id"),
                        "passed": True,
                    }
                else:
                    result = {
                        "request_id": data.get("request_id"),
                        "passed": False,
                    }

                return result
            
            else:
                return {
                    "request_id": data.get("request_id"),
                    "passed": False,
                }
            
        except Exception as e:
            self.logger.error(f"Error in check_cup_picked: {e}")
            return {
                "request_id": data.get("request_id"),
                "passed": False,
            }
    
    async def handle_check_cup_placed(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle cup placement validation requests"""
        return {
            "request_id": data.get("request_id"),
            "passed": True,
            "details": {"message": "Cup placement validation passed (placeholder)"}
        }
    
    async def handle_check_coffee_beans(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle coffee beans validation requests"""
        return {
            "request_id": data.get("request_id"),
            "passed": True,
            "details": {"message": "Coffee beans validation passed (placeholder)"}
        }
    
    # =============================================================================
    # SYSTEM HANDLERS
    # =============================================================================
    
    async def handle_health(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle health check requests"""
        return {
            "status": "healthy",
            "service": "validation",
            "timestamp": datetime.now().isoformat(),
            "capabilities": [
                "pre_check", "update_inventory", "ingredient_status", "refill_inventory",
                "check_cup_picked", "check_cup_placed", "check_coffee_beans"
            ]
        }
    
    
    # =============================================================================
    # UTILITY METHODS
    # =============================================================================

    async def send_all_inventory_status(self):
        """Send all inventory status to API Bridge"""
        try:
            status_request = {
                "request_id": f"auto-update-{datetime.now().timestamp()}",
                "client_type": "api_bridge",
                "function_name": "ingredient_status",
                "payload": {}
            }
            status_request = self.convert_to_validation_format(status_request, "ingredient_status")
            status_response = self.main_validation.process_ingredient_status_request(status_request)
            await self.rabbitmq_client.send_event("validation.all_inventory_updated", 
                 status_response.get("details", {})
            )
            
        except Exception as e:
            self.logger.error(f"Error sending all inventory status to API Bridge: {e}")



    async def send_inventory_status_event(self, affected_categories: set):
        """Send live inventory status update for affected categories only"""
        try:
            for category in affected_categories:
                # Get status for this category only
                status_request = {
                    "request_id": f"auto-update-{datetime.now().timestamp()}",
                    "client_type": "api_bridge",
                    "function_name": "ingredient_status",
                    "payload": {
                        "ingredient_type": category
                    }
                }
                
                category_status = self.main_validation.process_ingredient_status_request(status_request)
                
                # Send category-specific event
                await self.rabbitmq_client.send_event("validation.inventory_updated", {
                    "category": category,
                    "inventory": category_status.get("details", {}).get(category, {}),
                    "timestamp": datetime.now().isoformat()
                })

                # CHECK FOR ALERTS - NEW CODE
                await self.check_and_send_alerts(category, category_status)
                
                self.logger.info(f"Sent inventory update for category: {category}")
            
            # Also send summary updates
            await self.send_summary_events()
            
        except Exception as e:
            self.logger.error(f"Error sending inventory status to API Bridge: {e}")

    async def send_summary_events(self):
        """Send stock level and category summary events"""
        try:
            # Stock level summary
            stock_request = {
                "request_id": f"stock-update-{datetime.now().timestamp()}",
                "client_type": "api_bridge",
                "function_name": "stock_level",
                "payload": {}
            }
            stock_stats = self.main_validation.process_stock_level_request(stock_request)
            await self.rabbitmq_client.send_event("validation.stock_level_updated", 
                stock_stats.get("details", {}))
            
            # Category summary
            summary_request = {
                "request_id": f"summary-update-{datetime.now().timestamp()}",
                "client_type": "api_bridge", 
                "function_name": "category_summary",
                "payload": {}
            }
            category_summary = self.main_validation.process_category_summary_request(summary_request)
            await self.rabbitmq_client.send_event("validation.category_summary_updated", 
                category_summary.get("details", {}))
                
        except Exception as e:
            self.logger.error(f"Error sending summary events: {e}")


    async def check_and_send_alerts(self, category: str, category_status: dict):
        """Check inventory status and send alerts if needed"""
        try:
            # Get the inventory details for this category
            inventory_details = category_status.get("details", {}).get(category, {})
            print(f"inside check_and_send_alerts: inventory_details: {json.dumps( inventory_details, indent=2)}")
            
            # Loop through each subtype in the category
            for subtype, item_data in inventory_details.items():
                status = item_data.get("status")  # This is "high", "medium", "low", or "empty"
                amount = item_data.get("amount", 0)
                percentage = item_data.get("percentage", 0)
                
                # Send alert based on status
                if status == "empty" or status == "low":
                    await self.send_alert_to_oms(status, category, subtype)
                
                elif status == "high" or status == "medium":
                    await self.send_resolution_to_oms(status, category, subtype)
                
        except Exception as e:
            self.logger.error(f"Error checking status for alerts: {e}")
    

    async def send_alert_to_oms(self, severity: str, ingredient_type: str, subtype: str):
        """Send simple alert event to OMS (matching threshold_warning format)"""
        try:
            # Create simple alert event like threshold_warning
            alert_event = {
                "ingredient": f"{ingredient_type}_{subtype}",
                "severity": severity  # "low", or "empty"
            }
            
            # Send alert event to OMS using same pattern as threshold warnings
            await self.rabbitmq_client.send_event("validation.threshold_warning", alert_event)
            
            self.logger.info(f"Sent {severity} threshold warning to OMS for {ingredient_type}:{subtype}")
            
        except Exception as e:
            self.logger.error(f"Error sending alert to OMS: {e}")

    async def send_resolution_to_oms(self, severity: str, ingredient_type: str, subtype: str):
        """Send resolution event to OMS"""
        try:
            # Create resolution event
            resolution_event = {
                "ingredient": f"{ingredient_type}_{subtype}",
                "severity": "acknowledged"  # or "normal"
            }
            
            # Send resolution event to OMS
            await self.rabbitmq_client.send_event("validation.threshold_resolved", resolution_event)
            
            self.logger.info(f"Sent {severity} threshold resolution to OMS for {ingredient_type}:{subtype}")
            
        except Exception as e:
            self.logger.error(f"Error sending resolution to OMS: {e}")


    def convert_to_validation_format(self, new_data: Dict[Any, Any], function_name: str) -> Dict[Any, Any]:
        # Check if data is nested (from RabbitMQClient wrapper)
        actual_data = new_data.get("data", new_data)
        print(f"Actual data: {actual_data}")
        
        return {
            "request_id": new_data.get("request_id", f"async-{datetime.now().timestamp()}"),
            "client_type": self.determine_client_type(actual_data),
            "function_name": function_name,
            "payload": actual_data.get("payload", actual_data)  # Extract payload or use data directly
        }
    
    def determine_client_type(self, data: Dict[Any, Any]) -> str:
        """Determine client type from the new message format"""
        # Check if explicitly specified
        if "client_type" in data:
            return data["client_type"]
        
        # Infer from source service
        source_service = data.get("source_service", "")
        if "scheduler" in source_service.lower():
            return "scheduler"
        elif "api_bridge" in source_service.lower() or "dashboard" in source_service.lower():
            return "api_bridge"
        else:
            return "api_bridge"  # Default to api_bridge
    
    # async def send_inventory_status_event(self):
    #     """Send live inventory status update to API Bridge after any inventory change"""
    #     try:
    #         # Get current full inventory status
    #         status_request = {
    #             "request_id": f"auto-update-{datetime.now().timestamp()}",
    #             "client_type": "api_bridge",
    #             "function_name": "ingredient_status",
    #             "payload": {}
    #         }
            
    #         current_status = self.main_validation.process_ingredient_status_request(status_request)
            
    #         # Send as event for live updates that API Bridge can subscribe to
    #         await self.rabbitmq_client.send_event("validation.status_updated", {
    #             "current_status": current_status,
    #             "timestamp": datetime.now().isoformat()
    #         })
            
    #         self.logger.info("Sent live inventory status update to API Bridge")
            
    #     except Exception as e:
    #         self.logger.error(f"Error sending inventory status to API Bridge: {e}")
    
    async def stop(self):
        """Gracefully stop the validation service"""
        self.is_running = False
        
        try:
            # STOP THE PERIODIC DETECTION
            await self.main_validation.stop_periodic_detection()

            if self.rabbitmq_client:
                await self.rabbitmq_client.disconnect()
            
                
            self.logger.info("Validation service stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping service: {e}")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger = logging.getLogger("ValidationApp")
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


async def main():
    """Main entry point for the validation service"""
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start the validation service
    try:
        validation_app = ValidationServiceApp()
        await validation_app.start()
        
    except Exception as e:
        logger = logging.getLogger("ValidationApp")
        logger.error(f"Failed to start validation service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("🚀 Starting Validation Service with Async RabbitMQ")
    print("📋 Available actions:")
    print("  Inventory: pre_check, update_inventory, ingredient_status, refill_inventory")
    print("  Computer Vision: check_cup_picked, check_cup_placed, check_coffee_beans")
    print("  System: health")
    print("🔧 Simple request-response pattern with live inventory updates")
    
    asyncio.run(main())