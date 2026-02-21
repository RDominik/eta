## @file main.py
#  @brief Main entry point for the PV monitoring and wallbox control system.
#
#  Orchestrates periodic tasks for inverter data reading, wallbox control,
#  and MQTT communication using APScheduler for async scheduling.

import asyncio
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from goE import wallbox_control
from inverter import readInverter
from mqtt_client import MQTTManager

mqtt = MQTTManager("mqtt_client/broker_config.json")
scheduler = AsyncIOScheduler()


async def task_2s():
    """@brief Periodic 2-second task: reads inverter data, updates wallbox, writes energy to InfluxDB.

    Reads current inverter measurements, passes data to the wallbox controller,
    and writes the current energy consumption to InfluxDB.

    @exception Exception Logs error and pauses 10s on failure.
    """
    try:
        inverter_data = await readInverter.read_inverter(mqtt)
        wallbox_control.set_inverter_data(inverter_data)
        wallbox_control.write_current_energy_to_influx(mqtt)
        print(f"\n--- new measurement 2s Task: ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
        await asyncio.sleep(10)


async def task_10s():
    """@brief Periodic 10-second task: reads extended inverter registers.

    Reads slower-changing inverter data (energy totals, battery health, etc.)
    and writes to InfluxDB.

    @exception Exception Logs error and pauses 10s on failure.
    """
    try:
        await readInverter.read_inverter_10s_task()
        print(f"\n--- new measurement 10s Task: ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
        await asyncio.sleep(10)


async def task_30s():
    """@brief Periodic 30-second task: controls wallbox charging.

    Evaluates surplus PV power and adjusts the wallbox charging current accordingly.

    @exception Exception Logs error and pauses 10s on failure.
    """
    try:
        wallbox_control.control(mqtt)
        print(f"wallbox control finished ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    except Exception as e:
        print(f"Error calling wallbox: {e}")
        await asyncio.sleep(10)


scheduler.add_job(task_2s, "interval", seconds=2, id="task_2s")
scheduler.add_job(task_10s, "interval", seconds=10, id="task_10s")
scheduler.add_job(task_30s, "interval", seconds=30, id="task_30s")


async def main():
    """@brief Application entry point.

    Starts the MQTT client thread and the APScheduler async scheduler.
    """
    mqtt.start()
    scheduler.start()
    # Keep the event loop running
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
