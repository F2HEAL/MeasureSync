import asyncio
from bleak import BleakScanner

def detection_callback(device, advertisement_data):
    print(f"Name: {advertisement_data.local_name or '<No Name>'}\t"
          f"Address: {device.address}\t"
          f"RSSI: {advertisement_data.rssi}")

async def run():
    scanner = BleakScanner()
    scanner.register_detection_callback(detection_callback)
    await scanner.start()
    await asyncio.sleep(5.0)
    await scanner.stop()

asyncio.run(run())