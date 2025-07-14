from inverter import readGoodwe
import asyncio
import time
import schedule
from goE import goEcontrol

RERUN_TIME = 5  # seconds
# inverter_data = {
#     "house_consumption": 1000,
#     "ppv": 5000,
#     "battery_soc": 80
# }
inverterData = None
inverter = None

async def init_routines():
    print("Initializing routines...")
    try:
        inverter = await readGoodwe.initInverter()
    except Exception as e:
        print(f"Error initializing inverter: {e}")
    return inverter

async def call_inverter():
    try:
        inverter_data = await readGoodwe.readInverter(inverter)
        print("inverter measurement finished ")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
    return inverter_data

def call_wallbox():
    try:
        goEcontrol.load_control(inverterData)
        print("wallbox control finished ")
    except Exception as e:
        print(f"Error calling wallbox: {e}")
    
#schedule.every(5).seconds.do(await call_inverter)
schedule.every(30).seconds.do(call_wallbox)

async def main():

    inverter = await init_routines()
    while True:
        inverter_data = await readGoodwe.readInverter(inverter)
        inverterData = inverter_data
        schedule.run_pending()
       # #try:
        #    print("Waiting for 2 seconds before next read...")
        #except Exception as e:
        #    print(f"Error during wait test: {e}")
        print(f"wait for {RERUN_TIME} seconds")
        await asyncio.sleep(RERUN_TIME)

if __name__ == "__main__":
    asyncio.run(main())
