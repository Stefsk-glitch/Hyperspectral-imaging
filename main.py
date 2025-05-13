import asyncio
import websockets
import json
import threading

from app import run_app

async def handler(websocket):
    print("ESP32 connected")
    try:
        while True:
            command = input("Enter command: ").strip()
            msg = json.dumps({ "cmd": command })
            await websocket.send(msg)
            print(f"> Sent: {msg}")

            esp_ack = await websocket.recv()
            print(f"< ESP Ack: {esp_ack}")

            mega_ack = await websocket.recv()
            print(f"< Mega Ack: {mega_ack}")

    except websockets.ConnectionClosed:
        print("ESP32 disconnected")

async def launchWebsocketServer():
    async with websockets.serve(handler, "0.0.0.0", 8765):
        print("WebSocket server running on ws://0.0.0.0:8765")
        await asyncio.Future()

def launchWebsocketServerOnNewThread():
    asyncio.run(launchWebsocketServer())

if __name__ == "__main__":
    # the daemon=True flag ensures the thread will exit when the main program exits.
    websocketServerThread = threading.Thread(target=launchWebsocketServerOnNewThread, daemon=True)
    websocketServerThread.start()
    
    run_app()


