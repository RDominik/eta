import requests
import statistics
from collections import deque
import os
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import time
from influx_bucket import influxConfig

class goE_wallbox:
    chargingState = False
    previousChargingState = False
    
    def __init__(self, ip):
        self.baseURL = f"http://{ip}/api"  # Konvention: Unterstrich = "intern"

    def get_status(self, filter="alw,amp,car,pnp,eto,frc,sse,wh,nrg"):
        # nrg = energy array, U (L1, L2, L3, N), I (L1, L2, L3), P (L1, L2, L3, N, Total), pf (L1, L2, L3, N)
        # alw = car allowed to charge, sse = serial number, frc = forceState (Neutral=0, Off=1, On=2)
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
influx = influxConfig(INFLUX_BUCKET)
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
        print("already charging.")
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
    target_current = min(int(target_current), 14)
    return target_current

def write_data_to_influx(status_data):
    ts = status_data.pop("timestamp", datetime.utcnow())
    point = Point("goE_wallbox").tag("device", status_data["sse"])
    point = point.time(ts)
    point.field("ampere", int(status_data["amp"]))
    point.field("carState", int(status_data["car"]))
    point.field("energyTotal", int(status_data["eto"]))
    point.field("allowedCharge", int(status_data["frc"]))
    point.field("energyConnected", int(status_data["wh"]))
    print(f"\n--- new goE measurement ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    try:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")

def load_control(inverter_data):

    """Query the charging status once and set the charging current"""
    try:
        status = goE.get_status()
        currentTarget = calc_current(inverter_data, status["pnp"], status["amp"], status["car"])
        write_data_to_influx(status)    
    except requests.RequestException as e:
        print(f"error get wallbox status: {e}")
        currentTarget = 0
        status["frc"] = 0
        return
    print(f"current status: {currentTarget}")
    if currentTarget >= 6:
        print(f"charge current set to {currentTarget}A")
        try:
            status['amp_response'] = goE.set_current(currentTarget)
        except requests.RequestException as e:
            print(f"error set wallbox current: {e}")
            
        if status["frc"] != 0:
            goE.chargingState = True
            goE.set_charging(True)
    else:
        if status["frc"] != 1:
            goE.chargingState = False
            goE.set_charging(False)
    print(f"charging state: {goE.chargingState}")


    goE.previousChargingState = goE.chargingState



# Beispielnutzung
if __name__ == "__main__":
    print("Ladezustand vorher:")
    status = goE.get_status()
    print(status)

    write_data_to_influx(status)  

