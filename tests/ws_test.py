import asyncio
import websockets

async def test_websocket():
    uri = "ws://localhost:8000/ws/notifications/2"
    async with websockets.connect(uri) as websocket:
        print("Connected to WebSocket")
        while True:
            message = await websocket.recv()
            print("Notification received:", message)

asyncio.run(test_websocket())
