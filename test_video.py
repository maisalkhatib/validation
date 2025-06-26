"""
Mock Video Stream Service to test computer vision validation
Simulates receiving requests from validation service and responding with detection results
"""

import asyncio
import logging
import json
from typing import Dict, Any
from datetime import datetime
from shared.rabbitmq_client import RabbitMQClient

class VideoStreamTestService:
    def __init__(self):
        """Initialize video stream test service"""
        self.service_name = "video-stream"
        self.rabbitmq_client = RabbitMQClient(self.service_name)
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Silence RabbitMQ debug logs
        logging.getLogger('aio_pika').setLevel(logging.WARNING)
        logging.getLogger('aiormq').setLevel(logging.WARNING)
    
    async def start(self):
        """Start the video stream service and register handlers"""
        try:
            await self.rabbitmq_client.connect()
            
            # Register handlers for computer vision actions
            self.rabbitmq_client.register_handler("check_cup_picked", self.handle_check_cup_picked)
            self.rabbitmq_client.register_handler("check_cup_placed", self.handle_check_cup_placed)
            self.rabbitmq_client.register_handler("check_coffee_beans", self.handle_check_coffee_beans)
            self.rabbitmq_client.register_handler("health", self.handle_health)
            
            self.logger.info("🎥 Video Stream Service started")
            self.logger.info("📋 Available actions: check_cup_picked, check_cup_placed, check_coffee_beans")
            
            # Run forever
            try:
                await asyncio.Future()
            except KeyboardInterrupt:
                self.logger.info("Stopping video stream service...")
                await self.stop()
                
        except Exception as e:
            self.logger.error(f"Failed to start video stream service: {e}")
            await self.stop()
            raise
    
    async def handle_check_cup_picked(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle cup pick detection requests from validation service"""
        try:
            self.logger.info(f"🔍 Processing cup pick detection: {data}")
            
            # Extract parameters
            arm_id = data.get("arm_id", "unknown")
            cup_temperature = data.get("cup_temperature", "unknown")
            
            # Simulate computer vision processing
            await asyncio.sleep(1)  # Simulate processing time
            
            # Mock detection logic (you can modify this for testing)
            detected = True  # Change to False to test failure scenarios
            confidence = 0.92 if detected else 0.3
            
            self.logger.info(f"🤖 Cup pick detection result: detected={detected}, confidence={confidence}")
            
            response = {
                "success": True,
                "detected": detected,
                "confidence": confidence,
                "arm_id": arm_id,
                "cup_temperature": cup_temperature,
                "timestamp": datetime.now().isoformat(),
            }
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error in cup pick detection: {e}")
            return {
                "success": False,
                "detected": False,
                "error": f"Detection failed: {str(e)}"
            }
    
    async def handle_check_cup_placed(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle cup placement detection requests"""
        try:
            self.logger.info(f"🔍 Processing cup placement detection: {data}")
            
            # Simulate processing
            await asyncio.sleep(0.8)
            
            # Mock detection
            detected = True
            confidence = 0.89
            
            self.logger.info(f"📍 Cup placement detection result: detected={detected}")
            
            return {
                "success": True,
                "detected": detected,
                "confidence": confidence,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in cup placement detection: {e}")
            return {
                "success": False,
                "detected": False,
                "error": str(e)
            }
    
    async def handle_check_coffee_beans(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle coffee beans quality detection requests"""
        try:
            self.logger.info(f"🔍 Processing coffee beans detection: {data}")
            
            # Simulate processing
            await asyncio.sleep(1.2)
            
            # Mock detection
            detected = True
            quality_score = 0.85
            
            self.logger.info(f"☕ Coffee beans detection result: quality={quality_score}")
            
            return {
                "success": True,
                "detected": detected,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error in coffee beans detection: {e}")
            return {
                "success": False,
                "detected": False,
                "error": str(e)
            }
    
    async def handle_health(self, data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Handle health check requests"""
        return {
            "status": "healthy",
            "service": "video-stream",
            "timestamp": datetime.now().isoformat(),
            "capabilities": ["check_cup_picked", "check_cup_placed", "check_coffee_beans"]
        }
    
    async def stop(self):
        """Stop the video stream service"""
        try:
            if self.rabbitmq_client:
                await self.rabbitmq_client.disconnect()
            self.logger.info("🎥 Video Stream Service stopped")
        except Exception as e:
            self.logger.error(f"Error stopping service: {e}")

async def main():
    """Main entry point"""
    print("🎥 Starting Video Stream Test Service")
    print("📋 This service simulates computer vision detection")
    print("🔧 Will respond to requests from validation service")
    
    service = VideoStreamTestService()
    await service.start()

if __name__ == "__main__":
    asyncio.run(main())