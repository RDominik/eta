"""
@file goEcontrol.py
@brief Control and Monitoring for go-e Wallbox
@author Dominik Riepl
@version 0.1
@date 2024-07-19
@repository eta
This module provides a class and functions to control and monitor a go-e Wallbox charger.
It includes functionality to read status, set charging current, enable/disable charging,
and log data to InfluxDB. The control logic is designed to optimize charging based on
photovoltaic surplus and house consumption.
Classes:
    goE_wallbox:    
        Interface for go-e Wallbox API.
        - __init__(ip): Initialize with wallbox IP address.
        - get_status(filter): Get wallbox status with optional filter.
        - set_current(amps): Set charging current (6-14A).
        - set_charging(enable): Enable or disable charging.
Functions:
    power_to_current(surplusPower, phases, voltage, minCurrent, maxCurrent):
        Convert surplus power to charging current.
    calc_current(inverter_data, phases, charge_current, carState):
        Calculate target charging current based on PV and house consumption.
    write_data_to_influx(status_data):
        Write wallbox status data to InfluxDB.
    mean_calculation(inverter_data):
        Calculate mean values for PV and house consumption.
    load_control(inverter_data):
        Main control loop for charging logic.
Usage:
    Run as main to print current wallbox status and log to InfluxDB.
"""


import requests
import statistics
from collections import deque
import os
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import time
from influx_bucket import influxConfig

class goE_wallbox:
    
    def __init__(self, ip):
        self.baseURL = f"http://{ip}/api"  # Konvention: Unterstrich = "intern"

    def get_status(self, filter="alw,amp,car,pnp,eto,frc,sse,wh,nrg,modelStatus"):
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
INFLUX_BUCKET = "goe"

# IP-Adresse deiner go-e Wallbox
IP = "192.168.188.86"  # <- anpassen!
goE = goE_wallbox(IP)
influx = influxConfig(INFLUX_BUCKET)
ppvList = deque(maxlen=10)
houseConsumptionList = deque(maxlen=10)
house_mean = 0
ppv_mean = 0

"""
@brief Converts surplus power to electrical current per phase.

@param surplusPower (float): The available surplus power in watts.
@param phases (int, optional): Number of phases in the system. Default is 3.
@param voltage (float, optional): Voltage per phase in volts. Default is 230.
@param minCurrent (float, optional): Minimum allowable current in amperes. Default is 6.
@param maxCurrent (float, optional): Maximum allowable current in amperes. Default is 14.

@return float: The calculated current per phase in amperes. Returns 0 if surplusPower is less than or equal to zero.
"""
def power_to_current(surplusPower, phases=3, voltage=230, minCurrent=6, maxCurrent=14):

    if surplusPower <= 0:
        return 0
    return surplusPower / (phases * voltage)
    
def calc_current(inverter_data, phases, charge_current=0, carState=0):

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

"""
@brief Writes status data from a goE wallbox to an InfluxDB bucket.

Extracts relevant fields from the provided status_data dictionary, creates an InfluxDB Point,
and writes it to the configured bucket. The function expects specific keys in status_data:
'timestamp', 'sse', 'amp', 'car', 'eto', 'frc', 'wh', and 'nrg'.

@param status_data (dict): Dictionary containing status information from the goE wallbox.
                          Must include keys: 'timestamp', 'sse', 'amp', 'car', 'eto', 'frc', 'wh', 'nrg'.
@return None
"""
def write_data_to_influx(status_data):
    ts = status_data.pop("timestamp", datetime.now(timezone.utc))
    point = Point("goE_wallbox").tag("device", status_data["sse"])
    point = point.time(ts)
    point.field("ampere", float(status_data["amp"]))
    point.field("carState", float(status_data["car"]))
    point.field("energyTotal", float(status_data["eto"]))
    point.field("allowedCharge", float(status_data["frc"]))
    point.field("energyConnected", float(status_data["wh"]))
    point.field("currentEnergy", float(status_data["nrg"][11]))
    point.field("modelStatus", float(status_data["modelStatus"]))
    print(f"\n--- new goE measurement ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    influx.write_bucket_point(point)

def mean_calculation(inverter_data):
    global ppv_mean
    global house_mean
    houseConsumptionList.append(inverter_data["house_consumption"]) 
    ppvList.append(inverter_data["ppv"])
    ppv_mean = statistics.mean(ppvList)
    house_mean = statistics.mean(houseConsumptionList)

"""
@brief Queries the charging status from the goE wallbox and sets the charging current accordingly.

This function retrieves the current charging status, calculates the target charging current based on inverter data and wallbox status,
writes status data to InfluxDB, and adjusts the charging current and state of the wallbox. It ensures that the charging current is set
to a minimum value if the battery state of charge (SOC) is low, and manages the charging state based on the calculated current and wallbox status.

@param inverter_data (dict): Dictionary containing inverter data, including battery SOC.
@return None
"""
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

    print(f"modelStatus: {status['modelStatus']}")
    print(f"current status: {currentTarget}")
    if status['modelStatus'] != 8 and status['modelStatus']  != 9 and status['modelStatus'] != 10:
        if currentTarget >= 6:
            print(f"charge current set to {currentTarget}A")
            try:
                status['amp_response'] = goE.set_current(currentTarget)
            except requests.RequestException as e:
                print(f"error set wallbox current: {e}")
                
            if status["frc"] != 0:
                goE.set_charging(True)
        else:
            if status["frc"] != 1:
                goE.set_charging(False)
    print(f"charging state: {status['frc']}")



# Beispielnutzung
if __name__ == "__main__":
    print("Ladezustand vorher:")
    status = goE.get_status()
    print(status)

    write_data_to_influx(status)  

