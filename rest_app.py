from pydantic_req_structure import UpdateInventoryRequest, PreCheckRequest, CheckCupPlacedRequest, CheckCupPickedRequest, InventoryStatusRequest
from fastapi import FastAPI, HTTPException
import uvicorn
import threading
import time
import uuid
import logging
from queue import Queue
from typing import Dict, Any

from main_validation import MainValidation

"""
A Class if REST API is used 
NOTE!!!!!!!!!!!!!!!!!!!!!!! 
this class is not tested yet, so it might not work
"""

class ValidationServiceApp:
    def __init__(self):
        # FastAPI app
        self.app = FastAPI(title="Validation Service", description="Inventory Validation API", docs_url="/")
        
        # Main validation object (pure business logic)
        self.main_validation = MainValidation()
        
        # Internal queues for request/response handling
        self._request_queue = Queue()
        self._response_queue = Queue()
        
        # Response storage for HTTP requests
        self.response_storage: Dict[str, Any] = {}
        self.storage_lock = threading.Lock()
        
        # Event flags for workers
        self._request_event = threading.Event()
        self._response_event = threading.Event()
        
        # Setup workers and routes
        self.setup_workers()
        self.setup_routes()
        
        # Logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def setup_workers(self):
        """Setup request and response workers"""
        
        # Request worker thread
        self._request_worker = threading.Thread(target=self.request_worker, daemon=True)
        self._response_worker = threading.Thread(target=self.response_worker, daemon=True)
        
        # Start workers
        self._request_worker.start()
        self._response_worker.start()
        
        self.logger.info("Request and Response workers started")
    
    def post_request(self, request: Dict[Any, Any]):
        """Add request to internal queue for processing"""
        try:
            self.logger.info(f"Received request: {request.get('function_name')} with request_id: {request.get('request_id')}")
            
            # Add request to internal queue
            self._request_queue.put(request)
            
            # Signal request worker
            self._request_event.set()
            
        except Exception as e:
            self.logger.error(f"Failed to add request to queue: {e}")
            raise
    
    def request_worker(self):
        """Worker that processes requests from internal queue"""
        while True:
            try:
                # Wait for request event
                self._request_event.wait()
                
                # Get request from queue
                if not self._request_queue.empty():
                    request = self._request_queue.get()
                    self._request_event.clear()
                    
                    # Process request based on function name
                    function_name = request.get("function_name")
                    
                    if function_name == "update_inventory":
                        result = self.main_validation.process_update_inventory_request(request)
                        
                    elif function_name == "pre_check":
                        result = self.main_validation.process_pre_check_request(request)
                        
                    elif function_name == "ingredient_status":
                        result = self.main_validation.process_ingredient_status_request(request)
                        
                    else:
                        result = {
                            "request_id": request.get("request_id"),
                            "client_type": request.get("client_type"),
                            "passed": False,
                            "details": {"error": f"Unknown function: {function_name}"}
                        }
                        self.logger.error(f"Unknown function name: {function_name}")
                    
                    # Put result in response queue
                    self._response_queue.put(result)
                    self._response_event.set()
                
            except Exception as e:
                self.logger.error(f"Error in request worker: {e}")
    
    def response_worker(self):
        """Worker that handles processed responses"""
        while True:
            try:
                # Wait for response event
                self._response_event.wait()
                
                # Get response from queue
                if not self._response_queue.empty():
                    response = self._response_queue.get()
                    self._response_event.clear()
                    
                    # Store response for HTTP client retrieval
                    request_id = response.get("request_id")
                    if request_id:
                        with self.storage_lock:
                            response["_processed_at"] = time.time()
                            self.response_storage[request_id] = response
                        
                        self.logger.info(f"Processed and stored response for request: {request_id}")
                        
                        # Optional: Print response for debugging
                        print(f"Response: {response}")
                
            except Exception as e:
                self.logger.error(f"Error in response worker: {e}")
    
    def wait_for_response(self, request_id: str, timeout: int = 30) -> Dict[Any, Any]:
        """Wait for response to be processed and stored"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self.storage_lock:
                if request_id in self.response_storage:
                    response = self.response_storage.pop(request_id)
                    # Remove internal timestamp
                    response.pop("_processed_at", None)
                    return response
            
            time.sleep(0.1)  # Poll every 100ms
        
        raise HTTPException(status_code=408, detail="Request timeout - response not received")
    
    def setup_routes(self):
        """Setup all API routes"""
        self.app.post("/update_inventory")(self.update_inventory)
        self.app.post("/pre_check")(self.pre_check)
        self.app.post("/inventory_status")(self.inventory_status)
        self.app.post("/check_cup_placed")(self.check_cup_placed)
        self.app.post("/check_cup_picked")(self.check_cup_picked)
        self.app.get("/health")(self.health_check)
        self.app.get("/status/{request_id}")(self.get_request_status)
    
    async def update_inventory(self, request: UpdateInventoryRequest):
        """Update inventory levels"""
        try:
            # Generate unique request ID
            request_id = str(uuid.uuid4())
            
            # Convert request to internal format
            request_json = request.model_dump()
            request_json["request_id"] = request_id
            request_json["function_name"] = "update_inventory"
            
            # Send to internal processing
            self.post_request(request_json)
            
            # Wait for response
            response = self.wait_for_response(request_id)
            
            return {
                "passed": response.get("passed", False),
                "details": response.get("details", {}),
                "request_id": request_id
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

    async def pre_check(self, request: PreCheckRequest):
        """Check ingredient availability before order processing"""
        try:
            # Generate unique request ID
            request_id = str(uuid.uuid4())
            
            # Convert request to internal format
            request_json = request.model_dump()
            request_json["request_id"] = request_id
            request_json["function_name"] = "pre_check"
            
            # Send to internal processing
            self.post_request(request_json)
            
            # Wait for response
            response = self.wait_for_response(request_id)
            
            return {
                "passed": response.get("passed", False),
                "details": response.get("details", {}),
                "request_id": request_id
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

    async def inventory_status(self, request: InventoryStatusRequest):
        """Get current inventory status"""
        try:
            # Generate unique request ID
            request_id = str(uuid.uuid4())
            
            # Convert request to internal format
            request_json = request.model_dump()
            request_json["request_id"] = request_id
            request_json["function_name"] = "ingredient_status"
            
            # Send to internal processing
            self.post_request(request_json)
            
            # Wait for response
            response = self.wait_for_response(request_id)
            
            return {
                "passed": True,
                "details": response.get("details", {}),
                "request_id": request_id
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

    async def check_cup_placed(self, request: CheckCupPlacedRequest):
        """Check if cup is properly placed (placeholder)"""
        return {
            "passed": True, 
            "details": {"message": "Cup placement check passed"},
            "request_id": str(uuid.uuid4())
        }

    async def check_cup_picked(self, request: CheckCupPickedRequest):
        """Check if cup is properly picked (placeholder)"""
        return {
            "passed": True, 
            "details": {"message": "Cup pick check passed"},
            "request_id": str(uuid.uuid4())
        }

    async def health_check(self):
        """Health check endpoint"""
        return {
            "status": "healthy",
            "service": "validation_service",
            "workers": {
                "request_worker": self._request_worker.is_alive(),
                "response_worker": self._response_worker.is_alive()
            },
            "queue_sizes": {
                "request_queue": self._request_queue.qsize(),
                "response_queue": self._response_queue.qsize(),
                "stored_responses": len(self.response_storage)
            }
        }

    async def get_request_status(self, request_id: str):
        """Get status of a specific request (for debugging)"""
        with self.storage_lock:
            response = self.response_storage.get(request_id)
            
        if response:
            return {"status": "completed", "response": response}
        else:
            return {"status": "not_found", "message": "Request not found or already retrieved"}


# Create the app instance
validation_service = ValidationServiceApp()
app = validation_service.app


if __name__ == "__main__":
    print("Starting Validation Service with REST API and Internal Workers")
    print("Available endpoints:")
    print("  POST /update_inventory")
    print("  POST /pre_check") 
    print("  POST /inventory_status")
    print("  POST /check_cup_placed")
    print("  POST /check_cup_picked")
    print("  GET  /health")
    print("  GET  /status/{request_id}")
    print("  GET  / (API docs)")
    print("\nInternal Architecture:")
    print("  HTTP Request → post_request() → request_worker → MainValidation.process_*() → response_worker → HTTP Response")
    
    uvicorn.run(app, host="localhost", port=8069)