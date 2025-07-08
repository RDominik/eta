from inverter import readGoodwe
import asyncio
import time

RERUN_TIME = 5  # seconds

async def main():
    try:
        inverter = await readGoodwe.initInverter()
    except Exception as e:
        print(f"Error initializing inverter: {e}")
        return

    while True:
        try:
            await readGoodwe.readInverter(inverter)
            print("inverter measurement finished ")
        except Exception as e:
            print(f"Error reading inverter data: {e}")

       # try:
        #    print("Waiting for 2 seconds before next read...")
        #except Exception as e:
        #    print(f"Error during wait test: {e}")
        print(f"wait for {RERUN_TIME} seconds")
        await asyncio.sleep(RERUN_TIME)

if __name__ == "__main__":
    asyncio.run(main())
