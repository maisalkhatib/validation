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
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Add parent directory to path for shared imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.rabbitmq_client import RabbitMQClient, EventListener

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BARNS API Bridge Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global RabbitMQ clients
rabbitmq_client: Optional[RabbitMQClient] = None
event_listener: Optional[EventListener] = None

# WebSocket connections for real-time updates
active_websockets = []

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
        

        # event_listener.register_event_handler("scheduler.order_error", handle_order_event)
        
        # Inventory Events
        event_listener.register_event_handler("validation.inventory_updated", handle_inventory_updated_event)
        event_listener.register_event_handler("validation.stock_level_updated", handle_stock_level_event)
        event_listener.register_event_handler("validation.category_summary_updated", handle_category_summary_event)
        # event_listener.register_event_handler("validation.threshold_warning", handle_inventory_event)
        # event_listener.register_event_handler("inventory.refilled", handle_inventory_event)
        
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


# New event handlers for category-specific updates
async def handle_inventory_updated_event(data: Dict):
    """Handle category-specific inventory update events"""
    logger.info(f"📦 Received inventory update for category: {data.get('category')}")
    
    category = data.get("category")
    inventory_data = data.get("inventory", {})
    
    print("--------------------------------")
    print(f"[API Bridge] Inventory data in handle_inventory_updated_event: {json.dumps(inventory_data, indent=2)}")
    print("--------------------------------")
    
    # Send to WebSocket clients with hierarchical structure
    await broadcast_to_websockets({
        "type": "inventory_category_update",
        "event": "validation.inventory_updated",
        "data": {
            "category": category,
            "inventory": {
                category: inventory_data
            },
            "timestamp": data.get("timestamp", datetime.now().isoformat())
        },
        "timestamp": datetime.now().isoformat()
    })

async def handle_stock_level_event(data: Dict):
    """Handle stock level summary update events"""
    logger.info(f"📊 Received stock level update: high={data.get('high')}, medium={data.get('medium')}, low={data.get('low')}, empty={data.get('empty')}")
    
    await broadcast_to_websockets({
        "type": "stock_level_update",
        "event": "validation.stock_level_updated",
        "data": data,
        "timestamp": datetime.now().isoformat()
    })

async def handle_category_summary_event(data: Dict):
    """Handle category summary update events"""
    logger.info(f"📋 Received category summary update")
    
    print("--------------------------------")
    print(f"[API Bridge] Category summary data in handle_category_summary_event: {json.dumps(data, indent=2)}")
    # print("--------------------------------")
    
    await broadcast_to_websockets({
        "type": "category_summary_update",
        "event": "validation.category_summary_updated",
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

# Inventory Management Endpoints
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
            logger.warning(f"Validation service not available, simulating refill for {ingredient}")
            return {
                "success": True,
                "message": f"Refill initiated for {ingredient_type}:{subtype}",
                "ingredient_type": ingredient_type,
                "subtype": subtype,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error refilling inventory: {e}")
        # Return success for mock data
        return {
            "success": True,
            "message": f"Refill simulated for {ingredient_type}:{subtype}",
            "ingredient_type": ingredient_type,
            "subtype": subtype,
            "timestamp": datetime.now().isoformat()
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
                "category_summary": response.get("details", {}),
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
        
        if response.get("success") or response.get("passed"):
            return response
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 