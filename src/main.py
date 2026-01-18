from inverter import readGoodwe
import asyncio
import time
import schedule
from goE import goEcontrol

RERUN_TIME = 5  # seconds
# inverter_data = {
#     #"house_consumption": 1000,
#     "ppv": 5000,
#     "battery_soc": 80
# }    
############
inverter_data = None
inverter = None

async def init_routines():
    print("Initializing routines...")
    try:
        inverter = await readGoodwe.initInverter()
    except Exception as e:
        print(f"Error initializing inverter: {e}")
        await asyncio.sleep(10)
    return inverter

async def call_inverter():
    global inverter_data
    try:
        inverter_data = await readGoodwe.readInverter(inverter)
        print("inverter measurement finished ")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
        await asyncio.sleep(10)
    return inverter_data

def call_wallbox():
    try:
        goEcontrol.load_control(inverter_data)
        print("wallbox control finished ")
    except Exception as e:
        print(f"Error calling wallbox: {e}")
        time.sleep(10)

def wallbox_mean_calculation():
    try:
        goEcontrol.mean_calculation(inverter_data)
    except Exception as e:
        print(f"Error mean calculation wallbox: {e}")
        time.sleep(10)
    
#schedule.every(5).seconds.do(call_inverter)
schedule.every(60).seconds.do(call_wallbox)
schedule.every(5).seconds.do(wallbox_mean_calculation)

async def main():
    global inverter_data
    inverter = await init_routines()
    while True:
        inverter_data = await readGoodwe.getInverter(inverter)
        schedule.run_pending()
        await asyncio.sleep(RERUN_TIME)

if __name__ == "__main__":
    asyncio.run(main())
