import asyncio
import goodwe
import time
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# InfluxDB Konfiguration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "dein-api-token-hier"
INFLUX_ORG = "dominik"
INFLUX_BUCKET = "goodwe"

# InfluxDB Client initialisieren
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

async def main():
    inverter = await goodwe.connect('192.168.188.67', 8899)
    print("Verbindung hergestellt. Sende Daten an InfluxDB... (Strg+C zum Beenden)")

    try:
        while True:
            data = await inverter.read_runtime_data()
            ts = time.time_ns()

            for key, value in data.items():
                point = Point("inverter_data").tag("device", inverter.serial_number).field(key, float(value)).time(ts)
                write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)

            print(f"Gesendet: {len(data)} Felder")
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("Beendet.")
    finally:
        client.close()

asyncio.run(main())
