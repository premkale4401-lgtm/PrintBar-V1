"""
PrintBar — Raspberry Pi Hardware Agent Simulator

Simulates an actual Raspberry Pi print kiosk connecting to the PrintBar backend
via WebSocket. Demonstrates real-time hardware event loops, heartbeats,
file downloading, and printing.

Usage:
    python scripts/simulate_kiosk_hardware.py
"""
import asyncio
import json
import os
import sys

try:
    import websockets
except ImportError:
    print("Installing websockets package for simulator...")
    os.system(f"{sys.executable} -m pip install websockets")
    import websockets

BACKEND_WS_URL = os.environ.get("WS_URL", "ws://localhost:8000/api/v1/ws/kiosk")
# Standard seed kiosk API key or test key
KIOSK_ID = os.environ.get("KIOSK_ID", "00000000-0000-0000-0000-000000000001")
API_KEY = os.environ.get("KIOSK_API_KEY", "pb_kiosk_dev_key_123456789")


async def kiosk_simulator():
    url = f"{BACKEND_WS_URL}/{KIOSK_ID}?api_key={API_KEY}"
    print(f"🤖 [Kiosk Hardware Agent] Connecting to backend at: {url}")

    try:
        async with websockets.connect(url) as ws:
            print("✅ [Kiosk Hardware Agent] Connected to PrintBar WebSocket!")

            # Start heartbeat loop
            async def heartbeat_loop():
                while True:
                    hb_msg = {
                        "type": "HEARTBEAT",
                        "data": {
                            "printing": False,
                            "appVersion": "1.0.0-pi",
                            "cpuPercent": 12.5,
                            "ramPercent": 34.1,
                            "diskPercent": 45.0,
                            "temperatureC": 42.0,
                            "printerStatus": "READY",
                        },
                    }
                    await ws.send(json.dumps(hb_msg))
                    await asyncio.sleep(15)

            heartbeat_task = asyncio.create_task(heartbeat_loop())

            # Listen for messages
            async for raw_msg in ws:
                msg = json.loads(raw_msg)
                msg_type = msg.get("type")
                data = msg.get("data", {})

                print(f"📩 Received event: {msg_type}")

                if msg_type == "CONNECTED":
                    print(f"🎉 Kiosk registered with backend! Server time: {data.get('serverTime')}")

                elif msg_type == "JOB_ASSIGNED":
                    job_id = data.get("jobId")
                    print(f"📄 [PRINT JOB RECEIVED] Job ID: {job_id} ({data.get('colorMode')}, {data.get('pagesSelected')} pages)")

                    # Request download URL
                    print(f"📥 Requesting download URL for job {job_id}...")
                    await ws.send(json.dumps({
                        "type": "DOWNLOAD_URL_REQUEST",
                        "data": {"jobId": job_id}
                    }))

                elif msg_type == "DOWNLOAD_URL":
                    job_id = data.get("jobId")
                    file_url = data.get("url")
                    print(f"⬇️ Received signed file download URL. Simulating file transfer...")

                    # Send status: DOWNLOADING
                    await ws.send(json.dumps({
                        "type": "JOB_STATUS",
                        "data": {"jobId": job_id, "status": "DOWNLOADING"}
                    }))
                    await asyncio.sleep(2)

                    # Send status: PRINTING
                    print(f"🖨️ File transferred to local printer spooler. Printing pages...")
                    await ws.send(json.dumps({
                        "type": "JOB_STATUS",
                        "data": {"jobId": job_id, "status": "PRINTING"}
                    }))
                    await asyncio.sleep(3)

                    # Send status: JOB_COMPLETED
                    print(f"✅ Printing complete! Sending JOB_COMPLETED to backend...")
                    await ws.send(json.dumps({
                        "type": "JOB_COMPLETED",
                        "data": {"jobId": job_id}
                    }))

            heartbeat_task.cancel()

    except Exception as err:
        print(f"❌ Kiosk simulator connection error: {err}")


if __name__ == "__main__":
    asyncio.run(kiosk_simulator())
