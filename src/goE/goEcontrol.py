import requests
import statistics
from collections import deque
import os
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import time


class goE_wallbox:
    def __init__(self, ip):
        self.baseURL = f"http://{ip}/api"  # Konvention: Unterstrich = "intern"

    def get_status(self, filter="alw,amp,car,pnp,eto,frc,sse,wh"):
        # alw = car allowed to charge, sse = serial number
        # acu = actual current, amp = max current, wh = energy in Wh since car connected
        # car = carState, null if internal error (Unknown/Error=0, Idle=1, Charging=2, WaitCar=3, Complete=4, Error=5), pnp = numberOfPhases, 
        # eto = energy_total wh = energy in Wh since car connected
        response = requests.get(f"{self.baseURL}/status?filter=={filter}")
        response.raise_for_status()
        return response.json()
         
    def set_current(self, amps: int):
        """set current in Ampere (14 A)"""
        amps = max(6, min(amps, 14))
        payload = {'amp': amps}
        response = requests.get(self.baseURL + "/set", params=payload)
        response.raise_for_status()
        return response.json()  
    
    def set_charging(self, enable: bool):
        print("""start or stop charging""")
        payload = {'frc': 0 if enable else 1}
        response = requests.get(self.baseURL + "/set", params=payload)
        response.raise_for_status()
        return response.json() 
    
# InfluxDB Konfiguration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN")
# INFLUX_TOKEN = "0R7WsRl_3hfg3mYaC4KvCqGsgNmJ2YFgAv8u8EQFzQL0oKWGJaIFAnXKHLil2DiWHMr2KZmbG1xcF-uEivfM4w=="
INFLUX_ORG = "dominik"
INFLUX_BUCKET = "goe"

# InfluxDB Client initialisieren
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

# IP-Adresse deiner go-e Wallbox
IP = "192.168.188.86"  # <- anpassen!
goE = goE_wallbox(IP)
# Basis-URL
#BASE_URL = f"http://{IP}/api"
ppvList = deque(maxlen=5)
houseConsumptionList = deque(maxlen=5)

def power_to_current(surplusPower, phases=3, voltage=230, minCurrent=6, maxCurrent=14):
    if surplusPower <= 0:
        return 0
    return surplusPower / (phases * voltage)
    
def calc_current(inverter_data, phases, charge_current=0, carState=0):
    houseConsumptionList.append(inverter_data["house_consumption"]) 
    ppvList.append(inverter_data["ppv"])
    ppv_mean = statistics.mean(ppvList)
    house_mean = statistics.mean(houseConsumptionList)

    ppv_current = power_to_current(ppv_mean)
    house_current = power_to_current(house_mean)
    if ppv_current < 6:
        target_current = 0
    elif carState == 2:  # carState == Charging
        print("Ladevorgang läuft bereits.")
        surplus_current_charging = ppv_current - (house_current-charge_current)
        if surplus_current_charging > 6:
            target_current = surplus_current_charging
        else:
            target_current = 0
    else:
        target_current = ppv_current - house_current

    battery_soc = inverter_data["battery_soc"]
    print(f"power use house: {house_mean} -> current use house: {house_current}")
    print(f"power photovoltaik: {ppv_mean} -> current pv: {ppv_current}")
    print(f"battery_soc: {battery_soc} ")
    target_current = min(int(target_current), 14)
    return target_current

def write_point(status_data):
    ts = status_data.pop("timestamp", datetime.utcnow())
    point = Point("goE_wallbox").tag("device", status_data["sse"])
    point = point.time(ts)
    point.field("ampere", int(status_data["amp"]))
    point.field("carState", int(status_data["car"]))
    point.field("energyTotal", int(status_data["eto"]))
    point.field("allowedCharge", int(status_data["alw"]))
    point.field("energyConnected", int(status_data["wh"]))
    print(f"\n--- new measurement ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    try:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")

def load_control(inverter_data):
    # Beispiel: Wert lesen

    """Query the charging status once and set the charging current"""
    try:
        status = goE.get_status()
        print("Charge state:", status)
        currentTarget = calc_current(inverter_data, status["pnp"], status["amp"], status["car"])
    except requests.RequestException as e:
        print(f"error get wallbox status: {e}")
        currentTarget = 0
        status["frc"] = 0
        return

    if currentTarget >= 6:
        print(f"charge current set to {currentTarget}A")
        try:
            status['amp'] = goE.set_current(currentTarget)
        except requests.RequestException as e:
            print(f"error set wallbox current: {e}")
            
        if status["frc"] != 0:
            try:
                goE.set_charging(True)
            except requests.RequestException as e:
                print(f"error set wallbox charging on: {e}")
    else:
        try:
            if status["frc"] != 1:
                goE.set_charging(False)
        except requests.RequestException as e:
            print(f"error set wallbox charging off: {e}")
    write_point(status)

# Beispielnutzung
if __name__ == "__main__":
    print("Ladezustand vorher:")
    status = goE.get_status()
    print(status)

    write_point(status)

