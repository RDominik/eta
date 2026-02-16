## @file readInverter.py
#  @brief GoodWe inverter data acquisition and InfluxDB logging.
#
#  Reads real-time and periodic data from a GoodWe ET inverter via Modbus TCP,
#  calculates derived values (total PV power, house consumption), and writes
#  measurement points to InfluxDB.

from modbus import modbus_client
from datetime import datetime, timezone
from influxdb_client import Point
from influx_bucket import influxConfig
from mqtt_client import MQTTManager
import time

## @name InfluxDB Configuration
## @{
INFLUX_BUCKET = "goodwe"
influx = influxConfig(INFLUX_BUCKET)
## @}

## @name Modbus Connection Parameters
## @{
IP = "192.168.188.200"    ## RS485-to-Ethernet adapter IP
PORT = 4196               ## Modbus TCP port
UNIT = 247                ## GoodWe ET Modbus device address
## @}

## Inverter serial number used as InfluxDB tag
DEVICE = "9020KETT232W0041"

## @name MQTT Publisher Array Indices
## @{
PPV_ARRAY_INDEX = 0
HC_ARRAY_INDEX = 1
BSC_ARRAY_INDEX = 2
PB_ARRAY_INDEX = 3
## @}

## MQTT topics and initial values for publishing inverter data
publisher = [
    [f"goodwe/{DEVICE}/ppv", 0],
    [f"goodwe/{DEVICE}/house_consumption", 0],
    [f"goodwe/{DEVICE}/battery_soc", 0],
    [f"goodwe/{DEVICE}/pbattery", 0]
]

inverter = modbus_client(IP, PORT, UNIT, "inverter/register_config.json", "inverter/register_config_10s.json")


def read_inverter(mqtt_client: MQTTManager) -> dict:
    """@brief Read fast-changing inverter registers (2s cycle) and publish via MQTT.

    Reads PV voltages, currents, powers, battery and grid data.
    Calculates total PV power and house consumption, then writes
    an InfluxDB data point and publishes key values via MQTT.

    @param mqtt_client  MQTTManager instance for publishing data.
    @return dict containing all register values plus computed fields.
    """
    data = inverter.get_register1()
    data["ppv"] = data["pv1_power"]["value"]+data["pv2_power"]["value"]+data["pv3_power"]["value"]+data["pv4_power"]["value"]
    data["house_consumption"] = (data["ppv"])+(data["pbattery1"]["value"])-(data["active_power"]["value"]) 
    _write_fast_points(data)
    publisher[PPV_ARRAY_INDEX][1] = data["ppv"]
    publisher[HC_ARRAY_INDEX][1] = data["house_consumption"]
    publisher[BSC_ARRAY_INDEX][1] = data["battery_soc"]["value"]
    publisher[PB_ARRAY_INDEX][1] = data["pbattery1"]["value"]
    mqtt_client.set_keys(publisher)
    return data

def read_inverter_10s_task() -> None:
    """@brief Read slow-changing inverter registers (10s cycle).

    Reads energy totals, battery health, meter status, and operational
    mode data. Writes a single InfluxDB data point.
    """
    data = inverter.get_register2()
    point = Point("inverter_data").tag("device", DEVICE)
    point.field("grid_mode", float(data["grid_mode"]["value"]))
    point.field("warning_code", float(data["warning_code"]["value"]))
    point.field("operation_mode", float(data["operation_mode"]["value"])) 
    point.field("e_total", float(data["pv_energy_total"]["value"]))  
    point.field("e_day", float(data["pv_energy_day"]["value"]))
    point.field("e_total_exp", float(data["energy_total_feed"]["value"]))
    point.field("h_total", float(data["feeding_hours_total"]["value"]))
    point.field("e_day_exp", float(data["energy_day_sell"]["value"])) 
    point.field("e_total_imp", float(data["energy_total_buy"]["value"]))
    point.field("e_day_imp", float(data["energy_day_buy"]["value"]))
    point.field("e_load_total", float(data["energy_total_load"]["value"]))  
    point.field("e_load_day", float(data["energy_load_day"]["value"]))
    point.field("e_bat_charge_total", float(data["battery_charge_energy"]["value"]))
    point.field("e_bat_charge_day", float(data["charge_energy_day"]["value"]))
    point.field("e_bat_discharge_total", float(data["battery_discharge_energy"]["value"])) 
    point.field("e_bat_discharge_day", float(data["discharge_energy_day"]["value"]))
    point.field("battery_bms", float(data["bms_status"]["value"]))
    point.field("battery_temperature", float(data["bms_pack_temperature"]["value"]))
    point.field("battery_soh", float(data["bms_soh"]["value"])) 
    point.field("battery_warning_l", float(data["bms_warning_code_l"]["value"]))
    point.field("rssi", float(data["rssi"]["value"]))
    point.field("meter_test_status", float(data["meter_connect_status"]["value"]))
    point.field("meter_comm_status", float(data["meter_communication_status"]["value"]))        
    point.field("meter_freq", float(data["meter_frequency"]["value"])) 
    point.field("work_mode", float(data["work_mode"]["value"]))
    point.time(time.time_ns())
    influx.write_bucket_point(point)

def _write_fast_points(data: dict) -> None:
    """@brief Write fast-cycle inverter measurements to InfluxDB.

    Creates an InfluxDB Point with PV string data (voltage, current, power
    for all 4 strings), grid power, temperatures, battery data, and
    computed house consumption.

    @param data  Dictionary with register values from get_register1().
    """
    point = Point("inverter_data").tag("device", DEVICE)
    # PV String 1
    point.field("vpv1", float(data["pv1_voltage"]["value"]))
    point.field("ipv1", float(data["pv1_current"]["value"]))
    point.field("ppv1", int(data["pv1_power"]["value"]))
    # PV String 2
    point.field("vpv2", float(data["pv2_voltage"]["value"]))
    point.field("ipv2", float(data["pv2_current"]["value"]))
    point.field("ppv2", int(data["pv2_power"]["value"]))
    # PV String 3
    point.field("vpv3", float(data["pv3_voltage"]["value"]))
    point.field("ipv3", float(data["pv3_current"]["value"]))
    point.field("ppv3", int(data["pv3_power"]["value"]))
    # PV String 4
    point.field("vpv4", float(data["pv4_voltage"]["value"]))
    point.field("ipv4", float(data["pv4_current"]["value"]))
    point.field("ppv4", int(data["pv4_power"]["value"]))
    point.field("ppv", float(data["ppv"])) 
    point.field("total_inverter_power", float(data["total_inverter_power"]["value"]))
    point.field("active_power", float(data["active_power"]["value"]))
    point.field("backup_ptotal", float(data["backup_ptotal"]["value"]))
    point.field("load_ptotal", float(data["total_load_power"]["value"]))
    point.field("ups_load", float(data["ups_load_percent"]["value"]))
    point.field("temperature_air", float(data["air_temperature"]["value"]))
    point.field("temperature_module", float(data["temperature_module"]["value"]))
    point.field("temperature", float(data["temperature_radiator"]["value"]))  
    point.field("vbattery1", float(data["vbattery1"]["value"]))
    point.field("ibattery1", float(data["ibattery1"]["value"])) 
    point.field("pbattery1", float(data["pbattery1"]["value"]))
    point.field("battery_mode", float(data["battery_mode"]["value"]))
    point.field("house_consumption", float(data["house_consumption"]))
    point.field("battery_soc", float(data["battery_soc"]["value"]))
    point.time(time.time_ns())
    influx.write_bucket_point(point)

if __name__ == "__main__":
    read_inverter_10s_task()