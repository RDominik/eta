from inverter import readGoodwe
import asyncio
import time
import schedule
from goE import wallbox_control
from inverter import readInverter

def call_inverter():
    try:
        inverter_data = readInverter.read_inverter()
        wallbox_control.get_inverter_data(inverter_data)
        print(f"\n--- new measurement ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
        time.sleep(10)

def call_wallbox():
    try:
        wallbox_control.wallbox_control()
        print("wallbox control finished ({time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"Error calling wallbox: {e}")
        time.sleep(10)
    
schedule.every(2).seconds.do(call_inverter)
schedule.every(30).seconds.do(call_wallbox)
# schedule.every(5).seconds.do(wallbox_mean_calculation)

async def main():
    while True:
        schedule.run_pending()


if __name__ == "__main__":
    asyncio.run(main())
