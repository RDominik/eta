import asyncio
import goodwe
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import json
from influxPoints import write_point
from datetime import datetime

current_path = os.path.dirname(os.path.abspath(__file__))
filePath_dataJson = os.path.join(current_path, "current_influx_data.json")
# InfluxDB Konfiguration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN")
# INFLUX_TOKEN = "0R7WsRl_3hfg3mYaC4KvCqGsgNmJ2YFgAv8u8EQFzQL0oKWGJaIFAnXKHLil2DiWHMr2KZmbG1xcF-uEivfM4w=="
INFLUX_ORG = "dominik"
INFLUX_BUCKET = "goodwe"
print("InfluxDB-Token:", INFLUX_TOKEN)
# InfluxDB Client initialisieren
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

def readGoodwe():
    # Beispiel: datetime in String umwandeln
    print("Starte Goodwe Inverter Datenlesung...")