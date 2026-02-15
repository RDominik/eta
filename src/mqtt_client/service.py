import time
import paho.mqtt.client as mqtt
import threading
import json
from pathlib import Path
from typing import Any, Dict, Sequence, Union

class MQTTManager(threading.Thread):
    """MQTT Service running in its own Thread.

    - Subscribes to one or more prefixes + keys from JSON config
    - Stores latest message values per key (topic without prefix)
    - Provides getters/setters and a generic publish()
    """
    broker = "localhost"
    prefix = ""
    api_keys = []
    topics = []
    msg_values = {}
    msg_count = 0
    def __init__(self, broker_config: Path):
        super().__init__(daemon=True)
        config = self.load_registers(broker_config)
        # broker IP (fallbacks)
        self.broker = config.get("broker_ip") or config.get("broker") or "localhost"
        # collect all list-valued items from the JSON (don't assume the key name)
        topics_list: list[str] = []
        for section, entries in config.items():
            if section == "broker_ip" or section == "broker":
                continue
            if isinstance(entries, list):
                for item in entries:
                    if isinstance(item, str):
                        topics_list.append(item)
        # convert to (topic, qos) tuples for subscribe
        self.topics = [(entry, 0) for entry in topics_list]

        self.client = mqtt.Client(protocol=mqtt.MQTTv311,callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish

        self.received = {}           # <-- initialize as dict
        # locks for critical sections
        self.rx_lock = threading.Lock()
    
    @staticmethod
    def load_registers(path: str | Path) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
        
    # getter for received messages and publish data with locks to ensure thread safety
    @property
    def message(self):
        with self.rx_lock:
            return self.received

    @message.setter
    def message(self, key: str, value: Any, qos: int = 0, retain: bool = False) -> bool:
        return self.publish(key, value, qos=qos, retain=retain)

    def set_keys(self, data: list, qos: int = 0, retain: bool = False) -> bool:
        for key, value in data:
           self.publish(key, value, qos=qos, retain=retain)

    def publish(self, topic: Any, msg: Any, qos: int = 0, retain: bool = False):
        try:
            result = self.client.publish(topic, msg,  qos=qos, retain=retain)
            status = getattr(result, "rc", None)
            if status != 0:
                print(f"Failed to send message to topic {topic} rc={status}")
            return result
        except (BrokenPipeError, OSError, Exception) as e:
            print(f"MQTT publish error: {e}")
            try:
                self.client.reconnect()
            except Exception:
                try:
                    self.client.connect(self.broker, 1883, 60)
                except Exception:
                    pass
            return None

    # make on_publish an instance method
    def on_publish(self, client, userdata, mid, *args, **kwargs):
        # accept extra args (e.g. properties) from different callback API versions
        try:
            print(f"📤 Message published (mid={mid})")
        except Exception:
            # best-effort logging if signature differs
            print("📤 Message published (mid=? )")

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        print("broker connected with result code " + str(reason_code))
        client.subscribe(self.topics)

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            payload = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = msg.payload

        short_topic = msg.topic.split("/")[-1]
        with self.rx_lock:
            self.received[short_topic] = payload

    def run(self):

        self.client.connect(self.broker, 1883, 60)
        self.client.loop_start()

        while True:            
            time.sleep(0.1)
