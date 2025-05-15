import asyncio
import websockets
import json
import threading
import sys
import logging
from app import run_app
from share import command_queue
from queue import Empty
from share import command_queue, esp32_status
from pathlib import Path

log_path = Path(__file__).parent / "app_log.txt"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, mode="w"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Redirect print to logging
print = lambda *args, **kwargs: logging.info(" ".join(map(str, args)))

def clear_queue(q):
    while True:
        try:
            q.get_nowait()
        except Empty:
            break

async def handler(websocket):
    clear_queue(command_queue)
    print("ESP32 connected")
    esp32_status["connected"] = True
    try:
        while True:
            if not command_queue.empty():
                command = command_queue.get()
                msg = json.dumps({ "cmd": command })
                await websocket.send(msg)
                print(f"> Sent: {msg}")

                esp_ack = await websocket.recv()
                print(f"< ESP Ack: {esp_ack}")

                mega_ack = await websocket.recv()
                print(f"< Mega Ack: {mega_ack}")

            await asyncio.sleep(0.1)
    except websockets.ConnectionClosed:
        print("Websocket is closed")
        esp32_status["connected"] = False

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