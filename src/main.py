import inverter.readGoodwe
import asyncio

async def main():
    while True:
        try:
            await inverter.readGoodwe.read_data()
        except Exception as e:
            print(f"Error reading data: {e}")
        try:
            print("Waiting for 1 second before next read...")
        except Exception as e:
            print(f"Error during wait: {e}")

        await asyncio.sleep(5)

