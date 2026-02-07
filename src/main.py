from inverter import readGoodwe
import asyncio
import time
import schedule
from goE import goEcontrol
from goE import wallbox_control
from inverter import readInverter

RERUN_TIME = 5  # seconds
# inverter_data = {
#     #"house_consumption": 1000,
#     "ppv": 5000,
#     "battery_soc": 80
# }    
############'
inverter_data = None
inverter = None

# async def init_routines():
#     print("Initializing routines...")
#     try:
#         inverter = await readGoodwe.initInverter()
#     except Exception as e:
#         print(f"Error initializing inverter: {e}")
#         await asyncio.sleep(10)
#     return inverter

def call_inverter():
    try:
        # inverter_data = await readGoodwe.readInverter(inverter)
        inverter_data = readInverter.read_inverter()
        wallbox_control.get_inverter_data(inverter_data)
        print("inverter measurement finished ")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
        # await asyncio.sleep(10)
        time.sleep(10)

def call_wallbox():
    try:
        wallbox_control.wallbox_control()
        # goEcontrol.load_control(inverter_data)
        print("wallbox control finished ")
    except Exception as e:
        print(f"Error calling wallbox: {e}")
        time.sleep(10)

# def wallbox_mean_calculation():
#     try:
#         goEcontrol.mean_calculation(inverter_data)
#     except Exception as e:
#         print(f"Error mean calculation wallbox: {e}")
#         time.sleep(10)
    
schedule.every(2).seconds.do(call_inverter)
schedule.every(30).seconds.do(call_wallbox)
# schedule.every(5).seconds.do(wallbox_mean_calculation)

async def main():
    # global inverter_data
    # inverter = await init_routines()
    while True:
        # inverter_data = await readGoodwe.getInverter(inverter)
        # wallbox_control.get_inverter_data(inverter_data)
        schedule.run_pending()
        # await asyncio.sleep(RERUN_TIME)

if __name__ == "__main__":
    asyncio.run(main())
