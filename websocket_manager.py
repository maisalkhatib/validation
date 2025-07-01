# scalable_websocket_manager.py
# This would be a new file in your project

import asyncio
import json
import logging
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import re
from fastapi import WebSocket
from enum import Enum
import fnmatch

# Define event types as an enum for type safety
class EventType(Enum):
    # Inventory events
    INVENTORY_UPDATE = "inventory.update"
    INVENTORY_CATEGORY_UPDATE = "inventory.update"
    INVENTORY_ITEM_UPDATE = "inventory.item.update"
    INVENTORY_STOCK_LEVEL = "inventory.stock_level"
    INVENTORY_SUMMARY = "inventory.summary"
    
    # Alert events
    ALERT_NEW = "alert.new"
    ALERT_ACKNOWLEDGED = "alert.acknowledged"
    ALERT_RESOLVED = "alert.resolved"
    
    # System events
    SYSTEM_STATUS = "system.status"
    SYSTEM_ERROR = "system.error"

@dataclass
class WebSocketClient:
    """Represents a connected WebSocket client with its subscriptions"""
    websocket: WebSocket
    client_id: str
    subscriptions: Set[str] = field(default_factory=set)
    metadata: Dict = field(default_factory=dict)
    connected_at: datetime = field(default_factory=datetime.now)

class EventRouter:
    """Routes events to subscribers based on topic patterns"""
    
    def __init__(self):
        self.exact_subscriptions: Dict[str, Set[str]] = {}  # Changed to store client_ids
        self.pattern_subscriptions: List[tuple[re.Pattern, Set[str]]] = []  # Changed to store client_ids
    
    def add_subscription(self, client: WebSocketClient, topic: str):
        """Add a subscription for a client"""
        client_id = client.client_id  # Use client_id instead of client object
        
        if '*' in topic or '?' in topic:
            # Convert wildcard to regex pattern
            pattern = self._wildcard_to_regex(topic)
            # Check if pattern already exists
            for existing_pattern, client_ids in self.pattern_subscriptions:
                if existing_pattern.pattern == pattern.pattern:
                    client_ids.add(client_id)
                    return
            # Add new pattern
            self.pattern_subscriptions.append((pattern, {client_id}))
        else:
            # Exact match subscription
            if topic not in self.exact_subscriptions:
                self.exact_subscriptions[topic] = set()
            self.exact_subscriptions[topic].add(client_id)
    
    def remove_subscription(self, client: WebSocketClient, topic: str):
        """Remove a subscription for a client"""
        client_id = client.client_id
        
        if '*' in topic or '?' in topic:
            pattern = self._wildcard_to_regex(topic)
            self.pattern_subscriptions = [
                (p, client_ids - {client_id}) 
                for p, client_ids in self.pattern_subscriptions 
                if client_ids - {client_id}  # Keep only non-empty sets
            ]
        else:
            if topic in self.exact_subscriptions:
                self.exact_subscriptions[topic].discard(client_id)
                if not self.exact_subscriptions[topic]:
                    del self.exact_subscriptions[topic]
    
    def get_subscribers(self, event_topic: str, clients_map: Dict[str, WebSocketClient]) -> List[WebSocketClient]:
        """Get all clients subscribed to a specific event topic"""
        subscriber_ids = set()
        
        # Check exact matches
        if event_topic in self.exact_subscriptions:
            subscriber_ids.update(self.exact_subscriptions[event_topic])
        
        # Check pattern matches
        for pattern, client_ids in self.pattern_subscriptions:
            if pattern.match(event_topic):
                subscriber_ids.update(client_ids)
        
        # Convert client_ids back to WebSocketClient objects
        # Return a list instead of a set to avoid hashability issues
        return [clients_map[client_id] for client_id in subscriber_ids if client_id in clients_map]
    
    @staticmethod
    def _wildcard_to_regex(pattern: str) -> re.Pattern:
        """Convert wildcard pattern to regex"""
        # Escape special regex characters except * and ?
        pattern = re.escape(pattern)
        # Replace wildcards with regex equivalents
        pattern = pattern.replace(r'\*', '.*').replace(r'\?', '.')
        return re.compile(f'^{pattern}$')

class WebSocketManager:
    """Manages WebSocket connections and event routing"""
    
    def __init__(self):
        self.clients: Dict[str, WebSocketClient] = {}
        self.event_router = EventRouter()
        self.logger = logging.getLogger(__name__)
        
        # Event statistics for monitoring
        self.stats = {
            "total_connections": 0,
            "total_messages_sent": 0,
            "events_by_type": {}
        }
    
    async def connect(self, websocket: WebSocket) -> WebSocketClient:
        """Handle new WebSocket connection"""
        await websocket.accept()
        
        client_id = f"{websocket.client.host}:{websocket.client.port}_{datetime.now().timestamp()}"
        client = WebSocketClient(
            websocket=websocket,
            client_id=client_id
        )
        
        self.clients[client_id] = client
        self.stats["total_connections"] += 1
        
        # Send welcome message with available event types
        await self._send_to_client(client, {
            "type": "connection",
            "status": "connected",
            "client_id": client_id,
            "available_events": [e.value for e in EventType],
            "timestamp": datetime.now().isoformat()
        })
        
        self.logger.info(f"Client connected: {client_id}")
        return client
    
    async def disconnect(self, client: WebSocketClient):
        """Handle WebSocket disconnection"""
        # Remove from all subscriptions
        for topic in list(client.subscriptions):
            self.event_router.remove_subscription(client, topic)
        
        # Remove from clients
        if client.client_id in self.clients:
            del self.clients[client.client_id]
        
        self.logger.info(f"Client disconnected: {client.client_id}")
    
    async def handle_client_message(self, client: WebSocketClient, message: Dict):
        """Process messages from clients"""
        msg_type = message.get("type")
        
        if msg_type == "subscribe":
            await self._handle_subscribe(client, message.get("topics", []))
        
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(client, message.get("topics", []))
        
        elif msg_type == "ping":
            await self._send_to_client(client, {
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            })
        
        else:
            await self._send_to_client(client, {
                "type": "error",
                "message": f"Unknown message type: {msg_type}",
                "timestamp": datetime.now().isoformat()
            })
    
    async def _handle_subscribe(self, client: WebSocketClient, topics: List[str]):
        """Handle subscription request"""
        successful = []
        failed = []
        
        for topic in topics:
            try:
                # Validate topic format
                if self._is_valid_topic(topic):
                    client.subscriptions.add(topic)
                    self.event_router.add_subscription(client, topic)
                    successful.append(topic)
                else:
                    failed.append({"topic": topic, "reason": "Invalid topic format"})
            except Exception as e:
                failed.append({"topic": topic, "reason": str(e)})
        
        # Send confirmation
        await self._send_to_client(client, {
            "type": "subscription_result",
            "successful": successful,
            "failed": failed,
            "current_subscriptions": list(client.subscriptions),
            "timestamp": datetime.now().isoformat()
        })
        
        self.logger.info(f"Client {client.client_id} subscribed to: {successful}")
    
    async def _handle_unsubscribe(self, client: WebSocketClient, topics: List[str]):
        """Handle unsubscription request"""
        print(f"Client {client.client_id} unsubscribed from: {topics}")
        for topic in topics:
            if topic in client.subscriptions:
                client.subscriptions.remove(topic)
                self.event_router.remove_subscription(client, topic)
        
        await self._send_to_client(client, {
            "type": "unsubscription_result",
            "unsubscribed": topics,
            "current_subscriptions": list(client.subscriptions),
            "timestamp": datetime.now().isoformat()
        })

        self.logger.info(f"Client {client.client_id} unsubscribed from: {topics}")
    
    async def broadcast_event(self, event_type: str, event_data: Dict, 
                            source: Optional[str] = None):
        """Broadcast an event to all subscribers"""
        # Track event statistics
        self.stats["events_by_type"][event_type] = \
            self.stats["events_by_type"].get(event_type, 0) + 1
        
        # Build event message
        event_message = {
            "type": "event",
            "event_type": event_type,
            "data": event_data,
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
        
        # Get subscribers for this event
        subscribers = self.event_router.get_subscribers(event_type, self.clients)
        
        if subscribers:
            self.logger.info(
                f"Broadcasting {event_type} to {len(subscribers)} subscribers"
            )
            
            # Send to all subscribers
            disconnected = []
            for client in subscribers:
                try:
                    await self._send_to_client(client, event_message)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to send to {client.client_id}: {e}"
                    )
                    disconnected.append(client)
            
            # Clean up disconnected clients
            for client in disconnected:
                await self.disconnect(client)
        else:
            self.logger.debug(f"No subscribers for event: {event_type}")
    
    async def _send_to_client(self, client: WebSocketClient, message: Dict):
        """Send a message to a specific client"""
        try:
            await client.websocket.send_text(json.dumps(message))
            self.stats["total_messages_sent"] += 1
        except Exception as e:
            self.logger.error(f"Error sending to client {client.client_id}: {e}")
            raise
    
    def _is_valid_topic(self, topic: str) -> bool:
        """Validate topic format"""
        # Topics should be dot-separated, alphanumeric with wildcards
        pattern = r'^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_*?]+)*$'
        return bool(re.match(pattern, topic))
    
    def get_stats(self) -> Dict:
        """Get manager statistics"""
        return {
            **self.stats,
            "active_connections": len(self.clients),
            "unique_subscriptions": len(self.event_router.exact_subscriptions),
            "pattern_subscriptions": len(self.event_router.pattern_subscriptions)
        }