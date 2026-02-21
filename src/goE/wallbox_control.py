## @file wallbox_control.py
#  @brief go-eCharger wallbox surplus charging controller.
#
#  Implements PV surplus charging logic for a go-eCharger wallbox.
#  Calculates the optimal charging current from average PV production
#  and house consumption, supporting automatic 1-phase / 3-phase switching.

import statistics
from collections import deque
from influxdb_client import Point
from datetime import datetime, timezone
from mqtt_client import MQTTManager
from influx_bucket import influxConfig
import time

## @name MQTT Publisher Configuration
## @{
publisher = [
    ["go-eCharger/254959/amp/set", 8],
    ["go-eCharger/254959/frc/set", 1],
    ["go-eCharger/254959/psm/set", 0]
]
AMP_ARRAY_INDEX = 0   ## Index for ampere command in publisher list
FRC_ARRAY_INDEX = 1   ## Index for force-charge command
PSM_ARRAY_INDEX = 2   ## Index for phase-switch-mode command
## @}

## go-eCharger serial number
SSE = "254959"

## @name Charging Constants
## @{
CHARGING_ON = 0               ## frc value to enable charging
CHARGING_OFF = 1              ## frc value to disable charging
DEFAULT_CHARGE_CURRENT = 8   ## Default charge current in Ampere
BATTERY_MIN_CHARGE_SOC = 6   ## Minimum battery SOC before grid charging
THREE_PHASE_MIN_POWER = 4100  ## Minimum surplus power for 3-phase charging [W]
SINGLE_PHASE_MIN_POWER = 1400 ## Minimum surplus power for 1-phase charging [W]
## @}

## @name Phase Switch Modes
## @{
PHASE_SWITCH_AUTOMATIC = 0
PHASE_SWITCH_SINGLE = 1
PHASE_SWITCH_THREE = 2
## @}

## @name InfluxDB Configuration
## @{
INFLUX_BUCKET = "goe"
influx = influxConfig(INFLUX_BUCKET)
## @}

## @name Module-level State (rolling averages)
## @{
charging_on: bool = False
ppv_mean: float = 0
ppv_list: deque = deque(maxlen=10)
house_power_use_mean: float = 0
house_power_use_list: deque = deque(maxlen=10)
battery_soc: int = 100
## @}


def control(mqtt_client: MQTTManager) -> None:
    """@brief Main wallbox control loop – evaluate surplus and set charging.

    Reads the current wallbox status via MQTT, calculates the target
    charging current from PV surplus, and sends the appropriate
    MQTT commands to the wallbox.

    @param mqtt_client  MQTTManager instance for reading status and sending commands.
    """
    global charging_on, battery_soc, ppv_mean

    status = mqtt_client.message
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
        mqtt_client.set_keys(publisher)

    elif battery_soc <= BATTERY_MIN_CHARGE_SOC and ppv_mean == 0:
        print(f"battery low SOC {battery_soc}%, set default charge current {DEFAULT_CHARGE_CURRENT}A")
        charging_on = True
        publisher[AMP_ARRAY_INDEX][1] = DEFAULT_CHARGE_CURRENT
        publisher[FRC_ARRAY_INDEX][1] = CHARGING_ON
        publisher[PSM_ARRAY_INDEX][1] = PHASE_SWITCH_AUTOMATIC
        mqtt_client.set_keys(publisher)

    else:
        if charging_on:
            print("stop charging")
            charging_on = False
            publisher[AMP_ARRAY_INDEX][1] = DEFAULT_CHARGE_CURRENT
            publisher[FRC_ARRAY_INDEX][1] = CHARGING_OFF
            publisher[PSM_ARRAY_INDEX][1] = PHASE_SWITCH_AUTOMATIC
            mqtt_client.set_keys(publisher)


def charge_current_calculation(phases: int = 3, charge_current: int = 0,
                                car_state: int = 0, current_energy_car: float = 0) -> dict:
    """@brief Calculate optimal charging current from PV surplus.

    Uses rolling average PV power and house consumption to determine
    the available surplus. Selects 3-phase or 1-phase mode depending
    on surplus magnitude.

    @param phases              Current phase switch mode.
    @param charge_current      Current charging current (informational).
    @param car_state           Car connection state (2 = charging).
    @param current_energy_car  Current power drawn by the car [W].
    @return dict with 'ampere' (int, max 14A) and 'phases' keys.
    """
    global ppv_mean, house_power_use_mean
    target = {}

    if ppv_mean < SINGLE_PHASE_MIN_POWER:
        surplus_power = 0
    elif car_state == 2:  # car is currently charging
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

    print(f"calculated charge current: {target['ampere']}A on phases: {target['phases']}")
    target["ampere"] = min(int(target["ampere"]), 14)
    return target


def power_to_current(surplus_power: float, phases: int = 3, voltage: int = 230,
                     min_current: int = 6, max_current: int = 14) -> float:
    """@brief Convert surplus power to charging current.

    Applies P = U * I * phases to calculate the current.
    Adds a small offset (0.2A) to compensate for measurement lag.

    @param surplus_power  Available surplus power in Watts.
    @param phases         Number of active phases (1 or 3).
    @param voltage        Grid voltage in Volts (default 230).
    @param min_current    Minimum allowed current in Ampere.
    @param max_current    Maximum allowed current in Ampere.
    @return Calculated current in Ampere (float).
    """
    if surplus_power <= 0:
        return 0
    return surplus_power / (phases * voltage) + 0.2


def set_inverter_data(inverter_data: dict) -> None:
    """@brief Update rolling averages from latest inverter readings.

    Appends the current PV power and house consumption to rolling
    deques and recalculates mean values used for surplus calculation.

    @param inverter_data  dict with 'ppv', 'house_consumption', and 'battery_soc' keys.
    """
    global ppv_mean, ppv_list, house_power_use_list, house_power_use_mean, battery_soc
    house_power_use_list.append(inverter_data["house_consumption"])
    ppv_list.append(inverter_data["ppv"])
    ppv_mean = statistics.mean(ppv_list)
    house_power_use_mean = statistics.mean(house_power_use_list)
    battery_soc = inverter_data["battery_soc"]["value"]


def write_data_to_influx(status_data: dict) -> None:
    """@brief Write full wallbox status to InfluxDB.

    @param status_data  dict with wallbox status fields from MQTT.
    """
    try:
        point = Point("goE_wallbox").tag("device", SSE)
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
        point.time(time.time_ns())
        print(f"\n--- new goE measurement ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
        influx.write_bucket_point(point)
    except Exception as e:
        print(f"error writing goE data to influxDB: {e}")


def write_current_energy_to_influx(mqtt_client: MQTTManager) -> None:
    """@brief Write only the current wallbox energy consumption to InfluxDB.

    Called at 2s intervals independently of the full status write.

    @param mqtt_client  MQTTManager instance to read current wallbox data.
    """
    status = mqtt_client.message
    try:
        point = Point("goE_wallbox").tag("device", SSE)
        point.field("currentEnergy", float(status["nrg"][11]))
        point.time(time.time_ns())
        influx.write_bucket_point(point)
    except Exception as e:
        print(f"error writing goE current energy data to influxDB: {e}")


if __name__ == "__main__":
    print("wallbox test:")
    inverter_data = {
        "house_consumption": 1200,
        "ppv": 2400,
        "battery_soc": {"value": 50}
    }
    for _ in range(20):
        set_inverter_data(inverter_data)
    print(f"ppv_mean={ppv_mean}, house_mean={house_power_use_mean}")

