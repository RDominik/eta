from inverter import readGoodwe
import asyncio
import time
import schedule
from goE import wallbox_control
from inverter import readInverter

def task_1s():
    try:
        inverter_data = readInverter.read_inverter()
        wallbox_control.get_inverter_data(inverter_data)
        print(f"\n--- new measurement 1s Task: ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
        time.sleep(10)

def task_10s():
    try:
        readInverter.read_inverter_10s_task()
        print(f"\n--- new measurement 10s Task: ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
        time.sleep(10)

def task_30s():
    try:
        wallbox_control.wallbox_control()
        print("wallbox control finished ({time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"Error calling wallbox: {e}")
        time.sleep(10)
    
schedule.every(1).seconds.do(task_1s)
schedule.every(10).seconds.do(task_10s)
schedule.every(30).seconds.do(task_30s)

async def main():
    while True:
        schedule.run_pending()


if __name__ == "__main__":
    asyncio.run(main())
