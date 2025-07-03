from inverter import readGoodwe
import asyncio
import time

while True:
    try:
        readGoodwe.readInverter()
        print("Hello")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
    try:
        print("Waiting for 2 second before next read...")
    except ExceptioSn as e:
        print(f"Error during wait test: {e}")
    time.sleep(5)

