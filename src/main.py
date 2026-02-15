## @file main.py
#  @brief Main entry point for the PV monitoring and wallbox control system.
#
#  Orchestrates periodic tasks for inverter data reading, wallbox control,
#  and MQTT communication using the schedule library.

import time
import schedule
from goE import wallbox_control
from inverter import readInverter
from mqtt_client import MQTTManager

mqtt = MQTTManager("mqtt_client/broker_config.json")


def task_2s():
    """@brief Periodic 2-second task: reads inverter data, updates wallbox, writes energy to InfluxDB.

    Reads current inverter measurements, passes data to the wallbox controller,
    and writes the current energy consumption to InfluxDB.

    @exception Exception Logs error and pauses 10s on failure.
    """
    try:
        inverter_data = readInverter.read_inverter(mqtt)
        wallbox_control.set_inverter_data(inverter_data)
        wallbox_control.write_current_energy_to_influx(mqtt)

        print(f"\n--- new measurement 2s Task: ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
        time.sleep(10)


def task_10s():
    """@brief Periodic 10-second task: reads extended inverter registers.

    Reads slower-changing inverter data (energy totals, battery health, etc.)
    and writes to InfluxDB.

    @exception Exception Logs error and pauses 10s on failure.
    """
    try:
        readInverter.read_inverter_10s_task()
        print(f"\n--- new measurement 10s Task: ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    except Exception as e:
        print(f"Error reading inverter data: {e}")
        time.sleep(10)


def task_30s():
    """@brief Periodic 30-second task: controls wallbox charging.

    Evaluates surplus PV power and adjusts the wallbox charging current accordingly.

    @exception Exception Logs error and pauses 10s on failure.
    """
    try:
        wallbox_control.control(mqtt)
        print(f"wallbox control finished ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    except Exception as e:
        print(f"Error calling wallbox: {e}")
        time.sleep(10)


schedule.every(2).seconds.do(task_2s)
schedule.every(10).seconds.do(task_10s)
schedule.every(30).seconds.do(task_30s)


def main():
    """@brief Application entry point.

    Starts the MQTT client thread and continuously runs scheduled tasks.
    """
    mqtt.start()
    while True:
        schedule.run_pending()
        time.sleep(0.1)


if __name__ == "__main__":
    main()
