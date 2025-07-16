import os
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

class influxConfig:
    def __init__(self, bucket):
        self.INFLUX_URL = "http://localhost:8086"
        self.INFLUX_TOKEN = os.environ.get("INFLUX_TOKEN")
        self.INFLUX_ORG = "dominik"
        self.INFLUX_BUCKET = bucket
        # InfluxDB Client initialisieren
        self.client = InfluxDBClient(url=self.INFLUX_URL, token=self.INFLUX_TOKEN, org=self.INFLUX_ORG)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
    def write_bucket_point(self, point):
        try:
            self.write_api.write(bucket=self.INFLUX_BUCKET, org=self.INFLUX_ORG, record=point)
        except Exception as e:
            print(f"Error writing to InfluxDB: {e}")   





