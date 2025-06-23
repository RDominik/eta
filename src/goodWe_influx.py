import asyncio
import goodwe
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import os
from datetime import datetime


# InfluxDB Konfiguration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = os.environ.get("INFLUXDB_TOKEN")
INFLUX_ORG = "dominik"
INFLUX_BUCKET = "goodwe"

# InfluxDB Client initialisieren
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

async def main():
    inverter = await goodwe.connect('192.168.188.67', 8899, 'ET', 0, 1, 10)
    print("Verbindung hergestellt. Sende Daten an InfluxDB... (Strg+C zum Beenden)")

    try:
        while True:
            data = await inverter.read_runtime_data()
            # timestamp separat behandeln
            ts = data.pop("timestamp", datetime.utcnow())

            point = Point("inverter_data").tag("device", inverter.serial_number)

            for key, value in data.items():
                # Nur gültige Datentypen als Felder einfügen
                if isinstance(value, (int, float)):
                   point = point.field(key, value)
                elif isinstance(value, str):
                    point = point.tag(key, value)

            point = point.time(ts)

            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
            await asyncio.sleep(3)

    except KeyboardInterrupt:
        print("Beendet.")
    finally:
        client.close()

asyncio.run(main())
