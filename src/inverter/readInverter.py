from modbus import modbus_client
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influx_bucket import influxConfig
from datetime import datetime, timezone
import time

# InfluxDB Konfiguration
INFLUX_BUCKET = "goodwe"
influx = influxConfig(INFLUX_BUCKET)

IP = "192.168.188.200"   # eth adapter ip
PORT = 4196
UNIT = 247 

inverter = modbus_client(IP, PORT, UNIT, "inverter/register_config.json","inverter/register_config_10s.json")


def read_inverter() -> dict:
    data = inverter.get_register1()
    data["ppv"] = data["pv1_power"]["value"]+data["pv2_power"]["value"]+data["pv3_power"]["value"]+data["pv4_power"]["value"]
    data["house_consumption"] = (data["ppv"])+(data["pbattery1"]["value"])-(data["active_power"]["value"]) 
    write_points(data)
    return data

def read_inverter_10s_task() -> dict:
    data = inverter.get_register2()
    ts = data.pop("timestamp", datetime.now(timezone.utc))
    point = Point("inverter_data").tag("device", "9020KETT232W0041")
    point = point.time(ts)
    point = Point("inverter_data") 
    point.tag("device", "9020KETT232W0041")
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

def write_points(data: dict):
    ts = data.pop("timestamp", datetime.now(timezone.utc))
    point = Point("inverter_data").tag("device", "9020KETT232W0041")
    point = point.time(ts)
    point = Point("inverter_data") 
    point.tag("device", "9020KETT232W0041")
    point.field("vpv1", float(data["pv1_voltage"]["value"]))
    point.field("ipv1", float(data["pv1_current"]["value"]))
    point.field("ppv1", int(data["pv1_power"]["value"]))
    point.field("vpv2", float(data["pv2_voltage"]["value"]))
    point.field("ipv2", float(data["pv2_current"]["value"]))
    point.field("ppv2", int(data["pv2_power"]["value"]))
    point.field("vpv2", float(data["pv3_voltage"]["value"]))
    point.field("ipv2", float(data["pv3_current"]["value"]))
    point.field("ppv2", int(data["pv3_power"]["value"]))
    point.field("vpv2", float(data["pv4_voltage"]["value"]))
    point.field("ipv2", float(data["pv4_current"]["value"]))
    point.field("ppv2", int(data["pv4_power"]["value"]))
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
    read_inverter()
    read_inverter_10s_task()