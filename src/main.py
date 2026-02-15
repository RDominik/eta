import asyncio
import time
import schedule
from goE import wallbox_control
from inverter import readInverter
from mqtt_client import MQTTManager

mqtt = MQTTManager("mqtt_client/broker_config.json")

def task_1s():
    try:
        inverter_data = readInverter.read_inverter()
        wallbox_control.set_inverter_data(inverter_data)
        wallbox_control.write_current_energy_to_influx(mqtt)
        
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
        wallbox_control.control(mqtt)
        print("wallbox control finished ({time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"Error calling wallbox: {e}")
        time.sleep(10)

schedule.every(1).seconds.do(task_1s)
schedule.every(10).seconds.do(task_10s)
schedule.every(30).seconds.do(task_30s)

def main():
    mqtt.start()
    while True:
        schedule.run_pending()


if __name__ == "__main__":
    main()
