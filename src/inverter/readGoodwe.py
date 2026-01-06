import asyncio
import goodwe
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os
import json
from inverter.influxPoints import write_point
from datetime import datetime
from influx_bucket import influxConfig

current_path = os.path.dirname(os.path.abspath(__file__))
filePath_dataJson = os.path.join(current_path, "current_influx_data.json")
# InfluxDB Konfiguration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "KT_MOqmtD5yCIdujbU9xhz8BTIS8Wxvd6yLdwJjFsZ0gkYKsg4ZoIa8KPjIZBNaOK3iFFqafQBtO4CAoxuxdQg=="
# INFLUX_TOKEN = "0R7WsRl_3hfg3mYaC4KvCqGsgNmJ2YFgAv8u8EQFzQL0oKWGJaIFAnXKHLil2DiWHMr2KZmbG1xcF-uEivfM4w=="
INFLUX_ORG = "dominik"
INFLUX_BUCKET = "goodwe"
print("InfluxDB-Token:", INFLUX_TOKEN)
print("InfluxDB token copy KT_MOqmtD5yCIdujbU9xhz8BTIS8Wxvd6yLdwJjFsZ0gkYKsg4ZoIa8KPjIZBNaOK3iFFqafQBtO4CAoxuxdQg==")
# InfluxDB Client initialisieren
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)


influx = influxConfig(INFLUX_BUCKET)

def serialize_data(d):
    def convert(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    return {k: convert(v) for k, v in d.items()}

async def connect_inverter(ip, port, retries=999, delay=20):
    for attempt in range(retries):
        try:
            inverter = await goodwe.connect(ip, port, 'ET', 0, 1, 1)
            print("Verbindung zum Wechselrichter hergestellt. {ip}")
            return inverter
        except Exception as e:
            print(f"[Fehler] Verbindung {ip} fehlgeschlagen: {e}")
            print(f"Versuche erneut in {delay} Sekunden... (Versuch {attempt + 1})")
            await asyncio.sleep(delay)
    raise RuntimeError("Verbindung zum Wechselrichter konnte nach mehreren Versuchen nicht hergestellt werden.")

async def read_inverter(inverter, retries=999, delay=20):
    for attempt in range(retries):    
        try:
            data = await inverter.read_runtime_data()
            # Hier kannst du mit 'data' weiterarbeiten...
            return data
        except Exception as e:
            print(f"Fehler beim Lesen der Daten: {e}. Warte 5 Sekunden und versuche es erneut...")
            print(f"Versuche erneut in {delay} Sekunden... (Versuch {attempt + 1})")
            await asyncio.sleep(delay)
    raise RuntimeError("Daten vom Wechselrichter konnte nach mehreren Versuchen nicht gelesen werden.")

async def initInverter():
    inverter = await connect_inverter('192.168.188.120', 8899)
    print("Send data to InfluxDB...")
    return inverter

async def getInverter(inverter):
    data = await read_inverter(inverter)
    #  Aktuelle Daten in eine Datei schreiben
    with open(filePath_dataJson, "w") as f:
        json.dump(serialize_data(data), f, indent=2)

    # timestamp separat behandeln
    point = write_point(data, inverter)
    print(f"\n--- new measurement ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---")
    # write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
    influx.write_bucket_point(point)
    return data
