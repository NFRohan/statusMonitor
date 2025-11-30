import asyncio
import websockets

async def test_client():
    uri = "ws://localhost:8002/ws"
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}")
        while True:
            message = await websocket.recv()
            print(f"Received: {message[:100]}...") # Print first 100 chars

if __name__ == "__main__":
    try:
        asyncio.run(test_client())
    except KeyboardInterrupt:
        print("Client stopped")
