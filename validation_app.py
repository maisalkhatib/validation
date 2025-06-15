"""
This is the main file for the validation app using rabbitMQ.
It is responsible for receiving requests from the client and sending them to the validation service.
It also receives responses from the validation service and sends them to the client.

It also handles the worker and the queue for the validation service.
"""


import pika
import json
import logging
import signal
import sys
from typing import Dict, Any
from datetime import datetime

from main_validation import MainValidation


class ValidationServiceApp:

    def __init__(self, rabbitmq_host='localhost', rabbitmq_port=5672, rabbitmq_user="rabbitmq", rabbitmq_pass="rabbitmq"):
        self.service_name = "validation"
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.rabbitmq_user = rabbitmq_user
        self.rabbitmq_pass = rabbitmq_pass
        
        # Queue configuration
        self.input_queue = "validation_queue" # the queue that is responsible for receiving requests from the client
        self.output_queues = {
            "scheduler": "scheduler_response_queue", # the queue that is responsible for sending responses to the scheduler     
            "dashboard": "dashboard_response_queue", # the queue that is responsible for sending responses to the dashboard
        }
        
        # RabbitMQ connections
        self.connection = None
        self.channel = None
        
        # Initialize the core validation service
        self.main_validation = MainValidation()
        
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

        
    def setup_rabbitmq_connection(self):
        """Establish connection to RabbitMQ and declare queues"""
        try:
            # Create connection
            connection_params = pika.ConnectionParameters(
                host=self.rabbitmq_host,
                port=self.rabbitmq_port,
                credentials=pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_pass),
                heartbeat=600, # the heartbeat is the time in seconds that the server will wait for a response from the client
                blocked_connection_timeout=300 # the blocked connection timeout is the time in seconds that the server will wait for a response from the client
            )
            
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()
            
            # Declare input queue
            self.channel.queue_declare(queue=self.input_queue, durable=True) # the queue that is responsible for receiving requests from the client, it is durable so that it survives a restart of the server
            
            # Declare all output queues
            for service, queue_name in self.output_queues.items():
                self.channel.queue_declare(queue=queue_name, durable=True)
            
            # Set QoS for fair distribution
            self.channel.basic_qos(prefetch_count=1)
            
            self.logger.info(f"Connected to RabbitMQ at {self.rabbitmq_host}:{self.rabbitmq_port}")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    def send_response(self, response: Dict[Any, Any]):
        """Send response to appropriate service queue based on client_type"""
        try:
            client_type = response.get("client_type")
            print(f"client_type: {client_type}")
            print(f"response: {response}")
            
            if not client_type:
                self.logger.error("Response missing client_type field")
                return
            
            # Determine target queue
            target_queue = self.output_queues.get(client_type)
            if not target_queue:
                self.logger.error(f"Unknown client_type: {client_type}")
                return
            
            # Add service metadata
            response_with_metadata = {
                **response,
                "server_type": self.service_name,
                "timestamp": datetime.now().isoformat()
            }
            
            # Publish response
            self.channel.basic_publish(
                exchange='',
                routing_key=target_queue,
                body=json.dumps(response_with_metadata),
                properties=pika.BasicProperties(delivery_mode=2)  # Persistent
            )
            
            self.logger.info(f"Sent response to {client_type} (queue: {target_queue})")
            
        except Exception as e:
            self.logger.error(f"Failed to send response: {e}")
    
    def process_message(self, ch, method, properties, body):
        """Process incoming validation requests"""
        try:
            # Parse message
            message = json.loads(body.decode('utf-8'))
            
            request_id = message.get("request_id")
            client_type = message.get("client_type")
            function_name = message.get("function_name")
            
            self.logger.info(f"Processing {function_name} request from {client_type} (ID: {request_id})")
            
            # Route to appropriate processing method in MainValidation
            if function_name == "update_inventory":
                result = self.main_validation.process_update_inventory_request(message)
                
            elif function_name == "pre_check":
                result = self.main_validation.process_pre_check_request(message)
            
            elif function_name == "ingredient_status":
                result = self.main_validation.process_ingredient_status_request(message)
                
            else:
                # Unknown function
                result = {
                    "request_id": request_id,
                    "client_type": client_type,
                    "passed": False,
                    "error": f"Unknown function: {function_name}"
                }
                self.logger.error(f"Unknown function: {function_name}")
            
            # Send response back to requesting service
            self.send_response(result)
            
            # Acknowledge message processing
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    
    def start_consuming(self):
        """Start consuming messages from validation queue"""
        try:
            if not self.connection or self.connection.is_closed:
                self.setup_rabbitmq_connection()
            
            # Setup consumer
            self.channel.basic_consume(
                queue=self.input_queue,
                on_message_callback=self.process_message
            )
            
            self.is_running = True
            self.logger.info(f"Validation service started. Listening on queue: {self.input_queue}")
            self.logger.info("Press CTRL+C to stop the service")
            
            # Start consuming
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal, stopping service...")
            self.stop()
            
        except Exception as e:
            self.logger.error(f"Error in message consumption: {e}")
            self.stop()
            raise
    
    def stop(self):
        """Stop the validation service"""
        self.is_running = False
        
        try:
            if self.channel:
                self.channel.stop_consuming()
                
            if self.connection and not self.connection.is_closed:
                self.connection.close()
                
            self.logger.info("Validation service stopped successfully")
            
        except Exception as e:
            self.logger.error(f"Error stopping service: {e}")
    
    def health_check(self):
        """Check if the service is healthy"""
        try:
            if not self.connection or self.connection.is_closed:
                return False
            
            # Try to declare the input queue (lightweight operation)
            self.channel.queue_declare(queue=self.input_queue, passive=True)
            return True
            
        except Exception:
            return False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger = logging.getLogger("ValidationApp")
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Main entry point for the validation service"""
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create and start the validation service
    try:
        validation_app = ValidationServiceApp()
        validation_app.start_consuming()
        
    except Exception as e:
        logger = logging.getLogger("ValidationApp")
        logger.error(f"Failed to start validation service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()