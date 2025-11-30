import asyncio
import websockets

async def test_client():
    uri = "ws://localhost:8002/ws"
    async with websockets.connect(uri) as websocket:
        print(f"Connected to {uri}")
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=10)
            print(f"Received: {message[:200]}...")
        except asyncio.TimeoutError:
            print("Timeout - no message received in 10 seconds")

if __name__ == "__main__":
    asyncio.run(test_client())
