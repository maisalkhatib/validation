"""
API Bridge Service for BARNS Dashboard
Translates HTTP requests to RabbitMQ messages and vice versa
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Set
import uuid

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import socketio

# Add parent directory to path for shared imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.rabbitmq_client import RabbitMQClient, EventListener

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Socket.IO server
sio = socketio.AsyncServer(
    cors_allowed_origins="*",
    async_mode='asgi',
    logger=False,
    engineio_logger=False
)

app = FastAPI(title="BARNS API Bridge Service")


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instance
# ws_manager = WebSocketManager()

# Global RabbitMQ clients
rabbitmq_client: Optional[RabbitMQClient] = None
event_listener: Optional[EventListener] = None

# WebSocket connections for real-time updates
active_websockets = []


# Track client subscriptions for Socket.IO
client_subscriptions: Dict[str, Set[str]] = {}

# Statistics
stats = {
    "total_connections": 0,
    "active_connections": 0,
    "total_events_sent": 0,
    "events_by_topic": {}
}



# Request/Response models
class OrderCreate(BaseModel):
    cups: list

class OrderUpdate(BaseModel):
    status: str
    reason: Optional[str] = None

class InventoryRefill(BaseModel):
    ingredient: str
    amount: Optional[int] = 100

@app.on_event("startup")
async def startup_event():
    """Initialize RabbitMQ connections on startup"""
    global rabbitmq_client, event_listener
    
    try:
        # Initialize RabbitMQ client
        rabbitmq_client = RabbitMQClient("api_bridge")
        await rabbitmq_client.connect()
        
        # Initialize event listener for real-time updates
        event_listener = EventListener("api_bridge")
        await event_listener.connect()
        
        # Subscribe to events for real-time dashboard updates
        await event_listener.subscribe_to_events([
            "oms.*", "scheduler.*", "validation.*", "automation.*", "routine.*"
        ])
        
        # Register event handlers for all order-related events
        # OMS Events
        event_listener.register_event_handler("oms.order_created", handle_order_event)
        event_listener.register_event_handler("oms.order_started", handle_order_event)
        event_listener.register_event_handler("oms.order_status_updated", handle_order_event)
        event_listener.register_event_handler("oms.order_halted", handle_order_event)
        event_listener.register_event_handler("oms.order_resumed", handle_order_event)
        event_listener.register_event_handler("oms.order_completed", handle_order_event)
        event_listener.register_event_handler("oms.order_failed", handle_order_event)
        event_listener.register_event_handler("oms.order_deleted", handle_order_event)
        
        # Scheduler Events
        event_listener.register_event_handler("scheduler.order_received", handle_order_event)
        event_listener.register_event_handler("scheduler.order_processing_started", handle_order_event)
        event_listener.register_event_handler("scheduler.order_completed", handle_order_event)
        event_listener.register_event_handler("scheduler.order_failed", handle_order_event)
        event_listener.register_event_handler("scheduler.order_error", handle_order_event)
        
        # Inventory Events
        event_listener.register_event_handler("validation.inventory_updated", handle_inventory_updated_event)
        event_listener.register_event_handler("validation.all_inventory_updated", handle_inventory_updated_event_all)
        event_listener.register_event_handler("validation.stock_level_updated", handle_stock_level_event)
        event_listener.register_event_handler("validation.category_summary_updated", handle_category_summary_event)

        logger.info("API Bridge service started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start API Bridge service: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up RabbitMQ connections on shutdown"""
    global rabbitmq_client, event_listener
    
    if rabbitmq_client:
        await rabbitmq_client.disconnect()
    if event_listener:
        await event_listener.disconnect()
    
    logger.info("API Bridge service stopped")

# Event handlers for real-time updates
async def handle_order_event(data: Dict):
    """Handle order-related events and broadcast to WebSocket clients"""
    logger.info(f"📡 Broadcasting order event to {len(active_websockets)} WebSocket clients: {data}")
    
    print(f"Order data: {data}")
    
    await broadcast_to_websockets({
        "type": "order_update",
        "event": data.get("event_type", "unknown"),
        "data": data,
        "timestamp": datetime.now().isoformat()
    })

async def handle_inventory_event(data: Dict):
    """Handle inventory-related events and broadcast to WebSocket clients"""
    # logger.info(f"📡 Broadcasting inventory event to {len(active_websockets)} WebSocket clients: {json.dumps(data, indent=2)}")
    
    inventory_data = data.get("data", {})
    print("--------------------------------")
    print(f"Inventory data in handle_inventory_event: {inventory_data}")
    print("--------------------------------")
    

    message = {
        "type": "inventory_update",
        "event": data.get("event_type", "unknown"),
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"message to websocket: {json.dumps(message, indent=2)}")


    await broadcast_to_websockets({
        "type": "inventory_update",
        "event": data.get("event_type", "unknown"),
        "data": data,
        "timestamp": datetime.now().isoformat()
    })


async def broadcast_to_websockets(message: Dict):
    """Broadcast message to all connected WebSocket clients"""
    if active_websockets:
        logger.info(f"📡 Broadcasting to {len(active_websockets)} WebSocket clients: {message.get('type', 'unknown')}")
        disconnected = []
        for websocket in active_websockets:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected clients
        for ws in disconnected:
            if ws in active_websockets:
                active_websockets.remove(ws)
                logger.info(f"Removed disconnected WebSocket client. {len(active_websockets)} clients remaining.")
    else:
        logger.debug("No active WebSocket clients to broadcast to")

# HTTP API Endpoints (translating to RabbitMQ)

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "api_bridge",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def root_health_check():
    """Root health check endpoint"""
    return {
        "status": "healthy",
        "service": "api_bridge",
        "timestamp": datetime.now().isoformat()
    }

# Order Management Endpoints
@app.post("/api/orders")
async def create_order(order: OrderCreate):
    """Create a new order"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="create_order",
            data={"order": order.dict()},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to create order"))
            
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders")
async def list_orders(status: Optional[str] = None):
    """List orders with optional status filter"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="list_orders",
            data={"status": status} if status else {},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to list orders"))
            
    except Exception as e:
        logger.error(f"Error listing orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/orders/{order_id}")
async def get_order(order_id: int):
    """Get a specific order by ID"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="get_order",
            data={"order_id": order_id},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=404, detail=response.get("error", "Order not found"))
            
    except Exception as e:
        logger.error(f"Error getting order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/orders/{order_id}/start")
async def start_order(order_id: int):
    """Start processing an order"""
    try:
        logger.info(f"🚀 Starting order {order_id} - sending RabbitMQ request to OMS")
        
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="start_order",
            data={"order_id": order_id},
            timeout=30
        )
        
        logger.info(f"📨 Received response from OMS for order {order_id}: {response}")
        
        if response.get("success"):
            logger.info(f"✅ Order {order_id} started successfully")
            return response
        else:
            logger.error(f"❌ Order {order_id} start failed: {response.get('error')}")
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to start order"))
            
    except Exception as e:
        logger.error(f"💥 Exception starting order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/orders/{order_id}/status")
async def update_order_status(order_id: int, update: OrderUpdate):
    """Update order status"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="update_order_status",
            data={
                "order_id": order_id,
                "status": update.status,
                "reason": update.reason
            },
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to update order"))
            
    except Exception as e:
        logger.error(f"Error updating order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/orders/{order_id}")
async def delete_order(order_id: int):
    """Delete an order"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="delete_order",
            data={"order_id": order_id},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to delete order"))
            
    except Exception as e:
        logger.error(f"Error deleting order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/orders/{order_id}/halt")
async def halt_order(order_id: int, reason: str = None):
    """Halt an order with reason"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="halt_order",
            data={"order_id": order_id, "reason": reason},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to halt order"))
            
    except Exception as e:
        logger.error(f"Error halting order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/orders/{order_id}/resume")
async def resume_order(order_id: int):
    """Resume a halted order"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="resume_order",
            data={"order_id": order_id},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to resume order"))
            
    except Exception as e:
        logger.error(f"Error resuming order {order_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Queue Management Endpoints
@app.get("/api/queue")
async def get_queue():
    """Get current order queue"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="sync_queue",
            data={},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to get queue"))
            
    except Exception as e:
        logger.error(f"Error getting queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/queue/reorder")
async def reorder_queue(order_data: dict):
    """Reorder the queue"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="bulk_reorder_queue",
            data=order_data,
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to reorder queue"))
            
    except Exception as e:
        logger.error(f"Error reordering queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# System Status Endpoints
@app.get("/api/system/status")
async def get_system_status():
    """Get overall system status"""
    try:
        # Get status from multiple services
        services = ["validation"]
        statuses = {}
        
        for service in services:
            try:
                response = await rabbitmq_client.send_request(
                    target_service=service,
                    action="health",
                    data={},
                    timeout=10
                )
                statuses[service] = response
            except Exception as e:
                statuses[service] = {"status": "error", "error": str(e)}
        
        return {
            "success": True,
            "services": statuses,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/stop")
async def stop_system(request: dict):
    """Emergency stop system"""
    try:
        reason = request.get("reason", "Emergency stop requested")
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="emergency_stop",
            data={"reason": reason},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to stop system"))
            
    except Exception as e:
        logger.error(f"Error stopping system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/system/resume")
async def resume_system():
    """Resume system operations"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="resume_operations",
            data={},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to resume system"))
            
    except Exception as e:
        logger.error(f"Error resuming system: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Recipe Management Endpoints
@app.get("/api/recipes")
async def get_recipes():
    """Get available recipes from recipes.json file"""
    try:
        recipes_file = os.path.join('/app', 'data', 'recipes.json')
        
        if not os.path.exists(recipes_file):
            logger.error(f"Recipes file not found at {recipes_file}")
            raise HTTPException(status_code=500, detail="Recipes file not found")
        
        with open(recipes_file, 'r', encoding='utf-8') as f:
            recipes_data = json.load(f)
        
        # Extract recipe names and convert to title case for display
        recipe_names = []
        for recipe_name in recipes_data.keys():
            # Convert from lowercase to title case (e.g., "latte" -> "Latte")
            display_name = recipe_name.replace('_', ' ').title()
            recipe_names.append({
                "name": recipe_name,
                "display_name": display_name,
                "steps": len(recipes_data[recipe_name])
            })
        
        logger.info(f"Successfully loaded {len(recipe_names)} recipes from file")
        return {
            "success": True,
            "data": recipe_names,  # Use 'data' field for consistency with dashboard API client
            "message": f"Successfully loaded {len(recipe_names)} recipes",
            "count": len(recipe_names),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error loading recipes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load recipes: {str(e)}")

# Inventory Management Endpoints

@app.post("/api/inventory/test_summary")
async def test_summary():
    """Test summary endpoint"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="validation",
            action="category_summary",
            data={},
            timeout=30
        )
        
        if response.get("success") or response.get("passed"):
        # publish to socket io 
            await handle_category_summary_event(response.get("details", {}))
        else:
            error_msg = response.get("error", "Failed to get category summary from validation service")
            logger.error(f"Validation service returned error: {error_msg}")
            raise HTTPException(status_code=503, detail=error_msg)
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error getting inventory category summary: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/inventory/status")
async def get_inventory_status(ingredient_type: Optional[str] = None, subtype: Optional[str] = None):
    """Get inventory status - all, by type, or specific item"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="validation",
            action="inventory_status",
            data={
                "ingredient_type": ingredient_type,
                "subtype": subtype
            },
            timeout=30
        )
        
        if response.get("success") or response.get("passed"):
            # Return hierarchical format as-is - no flattening
            return {
                "success": True,
                "inventory": response.get("details", {}),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to get inventory status"))
            
    except Exception as e:
        logger.error(f"Error getting inventory status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/inventory/category-info")
async def get_inventory_category_info():
    """Get inventory category info"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="validation",
            action="category_info",
            data={},
            timeout=30
        )
        
        if response.get("success") or response.get("passed"):
            return response.get("details", {})
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to get inventory category info"))
            
    except Exception as e:
        logger.error(f"Error getting inventory category info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/inventory/refill")
async def refill_inventory(ingredient_type: Optional[str] = None, subtype: Optional[str] = None):
    """Refill inventory"""
    try:
        print(f"Refilling inventory for {ingredient_type}:{subtype}")
        response = await rabbitmq_client.send_request(
            target_service="validation",
            action="inventory_refill",
            data={
                "ingredient_type": ingredient_type, 
                "subtype": subtype
            },
            timeout=30
        )
        
        if response.get("success") or response.get("passed"):
            return response
        else:
            # Return success for mock data
            logger.warning(f"Validation service not available, simulating refill")
            return {
                "passed": False,
                "details": {},
                "request_id": uuid.uuid4(),
                "client_type": "api_bridge"
            }
            
    except Exception as e:
        logger.error(f"Error refilling inventory: {e}")
        # Return success for mock data
        return {
            "passed": False,
            "details": {},
            "request_id": uuid.uuid4(),
            "client_type": "api_bridge"
        }

@app.get("/api/inventory/category-summary")
async def get_inventory_category_summary():
    """Get inventory category summary with lowest levels per category"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="validation",
            action="category_summary",
            data={},
            timeout=30
        )
        
        if response.get("success") or response.get("passed"):
            return {
                "success": True,
                "summary": response.get("details", {}),
                "timestamp": datetime.now().isoformat()
            }
        else:
            error_msg = response.get("error", "Failed to get category summary from validation service")
            logger.error(f"Validation service returned error: {error_msg}")
            raise HTTPException(status_code=503, detail=error_msg)
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(f"Error getting inventory category summary: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/inventory/stock-level")
async def get_inventory_stock_level():
    """Get inventory stock level statistics"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="validation",
            action="stock_level",
            data={},
            timeout=30
        )
        
        if response.get("success") or response.get("passed"):
            return {
                "success": True,
                "stock_level": response.get("details", {}),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to get severity statistics")
            
    except Exception as e:
        logger.error(f"Error getting inventory severity: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/inventory/category-count")
async def get_inventory_category_count():
    """Get inventory category count"""
    try:
        print("Getting inventory category count")
        response = await rabbitmq_client.send_request(
            target_service="validation",
            action="category_count",
            data={},
            timeout=30
        )

        print(f"Response: {json.dumps(response, indent=2)}")
        
        if response.get("success") or response.get("passed"):
            return {
                "success": True,
                "request_id": response.get("request_id"),
                "client_type": response.get("client_type"),
                "details": response.get("details", {})
            }
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to get inventory category count"))
            
    except Exception as e:
        logger.error(f"Error getting inventory category count: {e}")
        raise HTTPException(status_code=500, detail=str(e))
            

# Alert Management Endpoints
@app.get("/api/alerts/active")
async def get_active_alerts():
    """Get active alerts"""
    try:
        # Check if rabbitmq_client is available
        if rabbitmq_client is None:
            logger.warning("RabbitMQ client not initialized, returning empty alerts")
            return {
                "success": True,
                "alerts": [],
                "timestamp": datetime.now().isoformat()
            }
        
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="get_active_alerts",
            data={},
            timeout=10
        )
        
        if response and response.get("success"):
            return response
        else:
            # Return empty alerts if OMS doesn't have this endpoint yet
            logger.warning(f"OMS service doesn't have get_active_alerts endpoint or returned error: {response}")
            return {
                "success": True,
                "alerts": [],
                "timestamp": datetime.now().isoformat()
            }
            
    except TimeoutError as e:
        logger.warning(f"Timeout getting active alerts from OMS: {e}")
        return {
            "success": True,
            "alerts": [],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting active alerts: {type(e).__name__}: {str(e)}")
        # Return empty alerts on error
        return {
            "success": True,
            "alerts": [],
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/alerts/acknowledged")
async def get_acknowledged_alerts():
    """Get acknowledged alerts"""
    try:
        # Check if rabbitmq_client is available
        if rabbitmq_client is None:
            logger.warning("RabbitMQ client not initialized, returning empty acknowledged alerts")
            return {
                "success": True,
                "alerts": [],
                "timestamp": datetime.now().isoformat()
            }
        
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="get_acknowledged_alerts",
            data={},
            timeout=10
        )
        
        if response and response.get("success"):
            return response
        else:
            # Return empty alerts if OMS doesn't have this endpoint yet
            logger.warning(f"OMS service doesn't have get_acknowledged_alerts endpoint or returned error: {response}")
            return {
                "success": True,
                "alerts": [],
                "timestamp": datetime.now().isoformat()
            }
            
    except TimeoutError as e:
        logger.warning(f"Timeout getting acknowledged alerts from OMS: {e}")
        return {
            "success": True,
            "alerts": [],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting acknowledged alerts: {type(e).__name__}: {str(e)}")
        # Return empty alerts on error
        return {
            "success": True,
            "alerts": [],
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    """Acknowledge an alert"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="oms",
            action="acknowledge_alert",
            data={"alert_id": alert_id},
            timeout=30
        )
        
        if response.get("success"):
            return response
        else:
            raise HTTPException(status_code=400, detail=response.get("error", "Failed to acknowledge alert"))
            
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))



#------------------------------------------------------------------------
# socket io endpoints
#------------------------------------------------------------------------


# Socket.IO Event Handlers - SIMPLIFIED
@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    stats["total_connections"] += 1
    stats["active_connections"] += 1
    
    logger.info(f"🔌 Socket.IO client connected: {sid}")
    
    # Send welcome message
    await sio.emit('connected', {
        "status": "connected",
        "client_id": sid,
        "message": "Socket.IO connection established",
        "timestamp": datetime.now().isoformat()
    }, room=sid)

    # await asyncio.sleep(3)
    # # Send initial inventory status
    # await emit_inventory_status_on_connect()
    # await emit_stock_level_on_connect()
    # # await emit_inventory_summary_on_connect()

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    stats["active_connections"] -= 1
    logger.info(f"🔌 Socket.IO client disconnected: {sid}")

@sio.event
async def ping(sid):
    """Handle ping for heartbeat"""
    await sio.emit('pong', {
        "timestamp": datetime.now().isoformat()
    }, room=sid)

# Update emission functions to broadcast to ALL clients
async def emit_inventory_update(category: str, inventory_data: Dict):
    """Emit inventory update for specific category"""
    # Emit with specific event name
    await sio.emit(f'inventory.update.{category}', {
        "category": category,
        "inventory": inventory_data,
        "timestamp": datetime.now().isoformat()
    })
    
    # Also emit general update
    await sio.emit('inventory.update', {
        "category": category,
        "inventory": inventory_data,
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info(f"📡 Emitted inventory.update.{category}")

async def emit_stock_level_update(stock_data: Dict):
    """Emit stock level statistics update"""
    await sio.emit('inventory.stock_level', {
        "success": True,
        "stock_levels": stock_data,
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info("📡 Emitted inventory.stock_level")

async def emit_inventory_summary(summary_data: Dict):
    """Emit inventory category summary update"""
    await sio.emit('inventory.summary', {
        "success": True,
        "summary": summary_data,
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info("📡 Emitted inventory.summary")

# Replace your existing event handlers with these:
async def handle_inventory_updated_event(data: Dict):
    """Handle category-specific inventory update events"""
    category = data.get("category")
    inventory_data = data.get("inventory", {})
    
    logger.info(f"📦 Received inventory update for category: {category}")
    print(f"Inventory data: {json.dumps(inventory_data, indent=2)}")
    
    # Emit to Socket.IO clients
    await emit_inventory_update(category, inventory_data)

async def handle_stock_level_event(data: Dict):
    """Handle stock level summary update events"""
    logger.info(f"📊 Received stock level update")
    print(f"Stock level data: {json.dumps(data, indent=2)}")
    
    # Emit to Socket.IO clients
    await emit_stock_level_update(data)

async def handle_category_summary_event(data: Dict):
    """Handle category summary update events"""
    logger.info(f"📋 Received category summary update")
    print(f"Category summary data: {json.dumps(data, indent=2)}")
    
    # Emit to Socket.IO clients
    await emit_inventory_summary(data)

async def handle_inventory_updated_event_all(data: Dict):
    """Handle all inventory update events"""
    logger.info(f"📦 Received all inventory update")
    print(f"All inventory data: {json.dumps(data, indent=2)}")
    
    # Emit to Socket.IO clients
    await emit_inventory_update_all(data)

async def emit_inventory_update_all(data: Dict):
    """Emit all inventory update"""
    print("emit inventory.status")
    await sio.emit('inventory.status', {
        "success": True,
        "inventory": data,
        "timestamp": datetime.now().isoformat()
    })

# async def emit_inventory_status_on_connect(ingredient_type: Optional[str] = None, subtype: Optional[str] = None):
#     """Emit inventory status"""
#     """Get inventory status - all, by type, or specific item"""
#     try:
#         response = await rabbitmq_client.send_request(
#             target_service="validation",
#             action="inventory_status",
#             data={
#                 "ingredient_type": ingredient_type,
#                 "subtype": subtype
#             },
#             timeout=30
#         )
        
#         if response.get("success") or response.get("passed"):
#             print("--------------------------------")
#             print(f"Response: {json.dumps(response, indent=2)}")
#             print("--------------------------------")
#             # Return hierarchical format as-is - no flattening
#             await sio.emit('inventory.status', {
#                 "success": True,
#                 "inventory": response.get("details", {}),
#                 "timestamp": datetime.now().isoformat()
#             })
#         else:
#             await sio.emit('inventory.status', {
#                 "success": False,
#                 "error": response.get("error", "Failed to get inventory status"),
#                 "timestamp": datetime.now().isoformat()
#             })
            
#     except Exception as e:
#         logger.error(f"Error getting inventory status: {e}")
#         await sio.emit('inventory.status', {
#             "success": False,
#             "error": str(e),
#             "timestamp": datetime.now().isoformat()
#         })

async def emit_stock_level_on_connect():
    """Emit stock level"""
    """Get inventory stock level statistics"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="validation",
            action="stock_level",
            data={},
            timeout=30
        )
        
        if response.get("success") or response.get("passed"):
            await sio.emit('inventory.stock_level', {
                "success": True,
                "stock_level": response.get("details", {}),
                "timestamp": datetime.now().isoformat()
            })
        else:
            await sio.emit('inventory.stock_level', {
                "success": False,
                "error": response.get("error", "Failed to get severity statistics"),
                "timestamp": datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Error getting inventory severity: {e}")
        await sio.emit('inventory.stock_level', {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })

async def emit_category_summary_on_connect():
    """Emit inventory summary"""
    """Get inventory summary"""
    try:
        response = await rabbitmq_client.send_request(
            target_service="validation",
            action="category_summary",
            data={},
            timeout=30
        )
        if response.get("success") or response.get("passed"):
            await sio.emit('inventory.summary', {
                "success": True,
                "summary": response.get("details", {}),
                "timestamp": datetime.now().isoformat()
            })
        else:
            await sio.emit('inventory.summary', {
                "success": False,
                "error": response.get("error", "Failed to get inventory summary"),
                "timestamp": datetime.now().isoformat()
            })
            
    except Exception as e:
        logger.error(f"Error getting inventory summary: {e}")
        await sio.emit('inventory.summary', {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })

# Add Socket.IO stats endpoint
@app.get("/api/socketio/stats")
async def get_socketio_stats():
    """Get Socket.IO connection statistics"""
    return {
        "success": True,
        "stats": stats,
        "active_topics": list(set().union(*client_subscriptions.values())) if client_subscriptions else [],
        "timestamp": datetime.now().isoformat()
    }

# WebSocket endpoint for real-time updates
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates"""
    await websocket.accept()
    active_websockets.append(websocket)
    client_id = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    logger.info(f"🔌 WebSocket client connected: {client_id}. Total clients: {len(active_websockets)}")
    
    # Send welcome message
    await websocket.send_text(json.dumps({
        "type": "connection",
        "status": "connected",
        "message": "Real-time updates enabled",
        "timestamp": datetime.now().isoformat()
    }))
    
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    # Respond to ping with pong
                    await websocket.send_text(json.dumps({
                        "type": "pong", 
                        "timestamp": datetime.now().isoformat()
                    }))
                else:
                    # Echo back other messages for debugging
                    await websocket.send_text(json.dumps({
                        "type": "echo", 
                        "received": message,
                        "timestamp": datetime.now().isoformat()
                    }))
            except json.JSONDecodeError:
                # Handle non-JSON messages
                await websocket.send_text(json.dumps({
                    "type": "error", 
                    "message": "Invalid JSON received",
                    "timestamp": datetime.now().isoformat()
                }))
            
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        logger.info(f"🔌 WebSocket client disconnected: {client_id}. Total clients: {len(active_websockets)}")
    except Exception as e:
        logger.error(f"🔌 WebSocket error for {client_id}: {e}")
        if websocket in active_websockets:
            active_websockets.remove(websocket)


# Mount Socket.IO app
socket_app = socketio.ASGIApp(sio, app)

if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=8000) 