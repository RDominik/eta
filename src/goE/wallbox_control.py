import statistics
from collections import deque
from influxdb_client import InfluxDBClient, Point
from datetime import datetime, timezone
from influx_bucket import influxConfig
import time

# Neuer MQTT-Service mit JSON-Konfiguration
from mqtt_client.service import MqttService

CONFIG_PATH = "src/mqtt_client/config/goe.json"
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

# Start MQTT-Service im Hintergrund und nutze Getter/Setter
mqtt_service = MqttService(CONFIG_PATH)
mqtt_service.start()

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
    """Berechne Lade-Parameter basierend auf MQTT-Werten und setze Sollwerte via Setter."""
    global charging_on
    global battery_soc
    global ppv_mean

    # Werte per Getter lesen
    status = mqtt_service.get_all()
    # Fallbacks
    amp = status.get("amp", 0)
    car = status.get("car", 0)
    psm = status.get("psm", 0)
    nrg = status.get("nrg", [0] * 12)

    wallbox_target = charge_current_calculation(psm, amp, car, nrg[11] if len(nrg) > 11 else 0)

    write_data_to_influx(status)

    if wallbox_target["ampere"] >= 6:
        print(f"charge current set to {wallbox_target['ampere']}A")
        charging_on = True
        mqtt_service.set("amp", wallbox_target["ampere"])  # Publish via Setter
        mqtt_service.set("frc", CHARGING_ON)
        mqtt_service.set("psm", wallbox_target["phases"])  # Phase mode

    elif battery_soc <= BATTERY_MIN_CHARGE_SOC and ppv_mean == 0:
        print(
            f"battery low SOC {battery_soc}%, set default charge current {DEFAULT_CHARGE_CURRENT}A"
        )
        charging_on = True
        mqtt_service.set("amp", DEFAULT_CHARGE_CURRENT)
        mqtt_service.set("frc", CHARGING_ON)
        mqtt_service.set("psm", PHASE_SWITCH_AUTOMATIC)

    else:
        if charging_on is True:
            print("stop charging")
            charging_on = False
            mqtt_service.set("frc", CHARGING_OFF)
            mqtt_service.set("psm", PHASE_SWITCH_AUTOMATIC)


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
        ts = status_data.pop("timestamp", datetime.now(timezone.utc)) if isinstance(status_data, dict) else datetime.now(timezone.utc)
        point = Point("goE_wallbox").tag("device", SSE).time(ts)
        def fnum(x):
            try:
                return float(x)
            except Exception:
                return 0.0
        point.field("ampere", fnum(status_data.get("amp")))
        point.field("carState", fnum(status_data.get("car")))
        point.field("cableLock", fnum(status_data.get("cus")))
        point.field("chargeLimit", fnum(status_data.get("dwo")))
        point.field("energyTotal", fnum(status_data.get("eto")))
        point.field("allowedCharge", fnum(status_data.get("frc")))
        point.field("energyConnected", fnum(status_data.get("wh")))
        nrg = status_data.get("nrg", [0] * 12)
        point.field("currentEnergy", float(nrg[11] if isinstance(nrg, list) and len(nrg) > 11 else 0))
        point.field("phaseSwitchMode", fnum(status_data.get("psm")))
        point.field("modelStatus", fnum(status_data.get("modelStatus")))
        print(f"\n--- new goE measurement ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
        influx.write_bucket_point(point)
    except Exception as e:
        print(f"error writing goE data to influxDB: {e}")


# Beispielnutzung
if __name__ == "__main__":
    print("wallbox subscribe (service):")
    inverter_data = {"house_consumption": 1200, "ppv": 2400, "battery_soc": 50}
    for index in range(20):
        get_inverter_data(inverter_data)
    for index in range(2):
        wallbox_control()
