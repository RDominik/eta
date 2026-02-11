import statistics
from collections import deque
from influxdb_client import InfluxDBClient, Point
from datetime import datetime, timezone
from mqtt_client import mqtt_client
from influx_bucket import influxConfig
import time

# call function as module with python3 -m goE.wallbox_control
BROKER = "192.168.188.97"
TOPIC = [
    "alw",
    "amp",
    "car",
    "cus",
    "dwo",
    "eto",
    "frc",
    "wh",
    "nrg",
    "tma",
    "psm",
    "modelStatus",
]
publisher = [
    ["go-eCharger/254959/amp/set", 8],
    ["go-eCharger/254959/frc/set", 1],
    ["go-eCharger/254959/psm/set", 0],
]
AMP_ARRAY_INDEX = 0
FRC_ARRAY_INDEX = 1
PSM_ARRAY_INDEX = 2

PREFIX = "go-eCharger/254959/"
SSE = "254959"

CHARGING_ON = 0
CHARGING_OFF = 1
DEFAULT_CHARGE_CURRENT = 8
BATTERY_MIN_CHARGE_SOC = 6
THREE_PHASE_MIN_POWER = 4100
SINGLE_PHASE_MIN_POWER = 1400

PHASE_SWITCH_AUTOMATIC = 0
PHASE_SWITCH_SINGLE = 1
PHASE_SWITCH_THREE = 2

wallbox = mqtt_client(BROKER, PREFIX, TOPIC)
# InfluxDB Konfiguration
INFLUX_BUCKET = "goe"
influx = influxConfig(INFLUX_BUCKET)

charging_on = False

ppv_mean = 0
ppv_list = deque(maxlen=10)
house_power_use_mean = 0
house_power_use_list = deque(maxlen=10)
battery_soc = 100


def wallbox_control():
    """Query the charging status once and set the charging current"""
    global charging_on
    global battery_soc
    global ppv_mean

    status = wallbox.subscribe(publisher)
    wallbox_target = charge_current_calculation(
        status["psm"], status["amp"], status["car"], status["nrg"][11]
    )

    write_data_to_influx(status)

    if wallbox_target["ampere"] >= 6:
        print(f"charge current set to {wallbox_target['ampere']}A")
        charging_on = True

        publisher[AMP_ARRAY_INDEX][1] = wallbox_target["ampere"]
        publisher[FRC_ARRAY_INDEX][1] = CHARGING_ON
        publisher[PSM_ARRAY_INDEX][1] = wallbox_target["phases"]

    elif battery_soc <= BATTERY_MIN_CHARGE_SOC and ppv_mean == 0:
        print(
            f"battery low SOC {battery_soc}%, set default charge current {DEFAULT_CHARGE_CURRENT}A"
        )
        charging_on = True

        publisher[AMP_ARRAY_INDEX][1] = DEFAULT_CHARGE_CURRENT
        publisher[FRC_ARRAY_INDEX][1] = CHARGING_ON
        publisher[PSM_ARRAY_INDEX][1] = PHASE_SWITCH_AUTOMATIC

    else:
        if charging_on is True:
            print("stop charging")
            charging_on = False

            publisher[AMP_ARRAY_INDEX][1] = DEFAULT_CHARGE_CURRENT
            publisher[FRC_ARRAY_INDEX][1] = CHARGING_OFF
            publisher[PSM_ARRAY_INDEX][1] = PHASE_SWITCH_AUTOMATIC


def charge_current_calculation(
    phases=3, charge_current=0, carState=0, current_energy_car=0
) -> dict:
    global ppv_mean
    global house_power_use_mean
    target = {}

    if ppv_mean < SINGLE_PHASE_MIN_POWER:
        surplus_power = 0
    elif carState == 2:  # carState == Charging
        surplus_power = ppv_mean - (house_power_use_mean - current_energy_car)
    else:
        surplus_power = ppv_mean - house_power_use_mean

    print(f"surplus power: {surplus_power}W")

    if surplus_power >= THREE_PHASE_MIN_POWER:
        target["ampere"] = power_to_current(surplus_power)
        target["phases"] = PHASE_SWITCH_AUTOMATIC
    elif surplus_power >= SINGLE_PHASE_MIN_POWER:
        target["ampere"] = power_to_current(surplus_power, phases=1)
        target["phases"] = PHASE_SWITCH_SINGLE
    else:
        target["ampere"] = 0
        target["phases"] = PHASE_SWITCH_AUTOMATIC

    print(
        f"calculated charge current: {target['ampere']}A on phases: {target['phases']}"
    )

    # create a decimal value for ampere and limit to max 14A
    target["ampere"] = min(int(target["ampere"]), 14)
    return target


def power_to_current(surplusPower, phases=3, voltage=230, minCurrent=6, maxCurrent=14):
    # min power is 1400W with 6A and 1 phase
    if surplusPower <= 0:
        return 0
    return surplusPower / (phases * voltage) + 0.200  # nudge to ensure >=6A when rounded


def get_inverter_data(inverter_data):
    global ppv_mean
    global ppv_list
    global house_power_use_list
    global house_power_use_mean
    global battery_soc
    house_power_use_list.append(inverter_data["house_consumption"])
    ppv_list.append(inverter_data["ppv"])
    ppv_mean = statistics.mean(ppv_list)
    house_power_use_mean = statistics.mean(house_power_use_list)
    battery_soc = inverter_data["battery_soc"]["value"]


def write_data_to_influx(status_data):
    try:
        ts = status_data.pop("timestamp", datetime.now(timezone.utc))
        point = Point("goE_wallbox").tag("device", SSE).time(ts)
        point.field("ampere", float(status_data["amp"]))
        point.field("carState", float(status_data["car"]))
        point.field("cableLock", float(status_data["cus"]))
        point.field("chargeLimit", float(status_data["dwo"]))
        point.field("energyTotal", float(status_data["eto"]))
        point.field("allowedCharge", float(status_data["frc"]))
        point.field("energyConnected", float(status_data["wh"]))
        point.field("currentEnergy", float(status_data["nrg"][11]))
        point.field("phaseSwitchMode", float(status_data["psm"]))
        point.field("modelStatus", float(status_data["modelStatus"]))
        print(f"\n--- new goE measurement ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
        influx.write_bucket_point(point)
    except Exception as e:
        print(f"error writing goE data to influxDB: {e}")


# Beispielnutzung
if __name__ == "__main__":
    print("wallbox subscribe:")
    inverter_data = {"house_consumption": 1200, "ppv": 2400, "battery_soc": 50}
    for index in range(20):
        get_inverter_data(inverter_data)
    for index in range(2):
        wallbox_control()
