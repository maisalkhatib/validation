import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")
        
        # Send ping
        await websocket.send(json.dumps({"type": "ping"}))
        
        # Listen for messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=30)
                print(f"Received: {json.dumps(message, indent=2)}")
                data = json.loads(message)
                
                # If it's a connection message, trigger an inventory update
                if data.get("type") == "connection":
                    print("Connection established, triggering inventory update...")
                    # You can trigger an inventory refill via REST API to see WebSocket update
                    
            except asyncio.TimeoutError:
                print("No message received in 30 seconds")
                break
            except Exception as e:
                print(f"Error: {e}")
                break

# Run the test
asyncio.run(test_websocket())