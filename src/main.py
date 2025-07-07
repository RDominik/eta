from inverter import readGoodwe
import asyncio
import time

RERUN_TIME = 5  # seconds

inverter = readGoodwe.initInverter()
while True:
    try:
        readGoodwe.readInverter(inverter)
        print("Hello")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
    try:
        print("Waiting for 2 second before next read...")
    except Exception as e:
        print(f"Error during wait test: {e}")
    time.sleep(RERUN_TIME)

