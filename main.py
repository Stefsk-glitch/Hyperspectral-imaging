import asyncio
import websockets
import json
import threading
import sys
import logging
from app import run_app
from models import command_queue, app_context, esp32_status, pipeline, stopped, cam_was_scanning, camera_data
from queue import Empty
from pathlib import Path
from time import sleep
import camera_connector

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
                
                try:
                    mega_ack = json.loads(mega_ack)
                except json.JSONDecodeError:
                    def show_fallback():
                        app_context["message_box"](f"Mega Ack (raw): {mega_ack}")
                    app_context["window"].after(0, show_fallback)
                else:
                    def show_mega_ack():
                        msg = ""
                        print(mega_ack)
                        if "uno_ack" in mega_ack:
                            if mega_ack["uno_ack"] == "start_scan" and pipeline["visualize"] == False:
                                msg = "✅ Started scan"
                            elif mega_ack["uno_ack"] == "stop_scan":
                                msg = "🛑 Stopped scan"
                            elif "length" in mega_ack["uno_ack"]:
                                msg = "Length set" 
                            elif "speed" in mega_ack["uno_ack"]:
                                msg = "Speed set" 
                        
                        elif {"t1", "t2", "status", "length", "speed"} <= mega_ack.keys() and pipeline["visualize"] == False:
                            msg = (
                                f"🌡️ Temperature 1: {mega_ack['t1']} °C\n"
                                f"🌡️ Temperature 2: {mega_ack['t2']} °C\n"
                                f"📶 Status: {mega_ack['status']}\n"
                                f"📏 Length: {mega_ack['length']}\n"
                                f"🚀 Speed: {mega_ack['speed']}"
                            )
                        
                        elif {"t1", "t2", "status", "length", "speed"} <= mega_ack.keys() and pipeline["visualize"] == True:
                            if (mega_ack['status']) == "Waiting":
                                stopped["stop"] = True
                            if (camera_data["system"] or camera_data["cam"] is not None):
                                if (mega_ack['status']) == "Scanning":
                                    if (cam_was_scanning["cam_was_scanning"] == False):
                                        cam_was_scanning["cam_was_scanning"] = True
                                        camera_connector.quick_init_camera()
                                else:
                                    if (cam_was_scanning["cam_was_scanning"] == True):
                                        cam_was_scanning["cam_was_scanning"] = False
                                        camera_connector.extract_data()
                        if msg:
                            app_context["message_box"](msg)
                    app_context["window"].after(0, show_mega_ack)

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