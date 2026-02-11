import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt


class MqttService:
    def __init__(self, config_path: str):
        self._config_path = Path(config_path)
        self._config = self._load_config(self._config_path)
        self._broker: str = self._config["broker"]
        self._prefix: str = self._config.get("prefix", "")
        self._subs = self._config.get("subscribe", [])
        self._set_map: Dict[str, str] = self._config.get("setMap", {})

        self._client = mqtt.Client(
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        self._values: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._loop_thread: Optional[threading.Thread] = None
        self._running = False

    @staticmethod
    def _load_config(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        topics = [(f"{self._prefix}{t}", 0) for t in self._subs]
        if topics:
            client.subscribe(topics)

    def _on_message(self, client, userdata, msg):
        key = msg.topic.removeprefix(self._prefix)
        try:
            payload = msg.payload.decode()
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                pass
        except UnicodeDecodeError:
            payload = msg.payload
        with self._lock:
            self._values[key] = payload

    def start(self):
        if self._running:
            return
        self._running = True
        self._client.connect(self._broker, 1883, 60)
        self._client.loop_start()
        # background refresher thread (optional; keeps process alive and allows reloads)
        self._loop_thread = threading.Thread(target=self._watch_config, daemon=True)
        self._loop_thread.start()

    def stop(self):
        if not self._running:
            return
        self._running = False
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass

    def _watch_config(self):
        last_mtime = self._config_path.stat().st_mtime
        while self._running:
            try:
                mtime = self._config_path.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    self._config = self._load_config(self._config_path)
                    self._subs = self._config.get("subscribe", self._subs)
                    self._set_map = self._config.get("setMap", self._set_map)
                    # resubscribe if needed
                    topics = [(f"{self._prefix}{t}", 0) for t in self._subs]
                    if topics:
                        self._client.subscribe(topics)
            except Exception:
                pass
            time.sleep(2)

    # getters / setters
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._values)

    def set(self, key: str, value: Any) -> bool:
        topic = self._set_map.get(key)
        if not topic:
            return False
        payload = value
        if not isinstance(value, (str, bytes)):
            payload = json.dumps(value)
        result = self._client.publish(topic, payload)
        return result.rc == mqtt.MQTT_ERR_SUCCESS
