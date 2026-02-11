from inverter import readGoodwe  # noqa: F401 (imported for side-effects / future use)
import asyncio
import time
import signal
import schedule
from goE import wallbox_control
from goE.wallbox_control import mqtt_service
from inverter import readInverter


shutdown = False

def _signal_handler(sig, frame):
    global shutdown
    shutdown = True


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
        print(f"wallbox control finished ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    except Exception as e:
        print(f"Error calling wallbox: {e}")
        time.sleep(10)


schedule.every(1).seconds.do(task_1s)
schedule.every(10).seconds.do(task_10s)
schedule.every(30).seconds.do(task_30s)


async def main():
    # Start MQTT thread service
    mqtt_service.start()

    # Trap SIGINT/SIGTERM for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        while not shutdown:
            schedule.run_pending()
            await asyncio.sleep(0.5)  # prevent tight loop / CPU spin
    finally:
        # Stop MQTT thread service
        try:
            mqtt_service.stop()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
