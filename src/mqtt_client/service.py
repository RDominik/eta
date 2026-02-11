import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, Sequence, Union

import paho.mqtt.client as mqtt


class MqttService(threading.Thread):
    """MQTT Service running in its own Thread.

    - Subscribes to one or more prefixes + keys from JSON config
    - Supports alternative config format (broker_ip + goE full topics)
    - Stores latest message values per key (last topic segment, e.g. "alw")
    - Provides getters/setters and a generic publish()
    """

    def __init__(self, config_path: str):
        super().__init__(daemon=True)
        self._config_path = Path(config_path)
        raw = self._load_config(self._config_path)
        self._config = self._normalize_config(raw)

        self._broker: str = self._config["broker"]
        # prefix can be string or list[str]
        self._prefixes: Sequence[str] = self._normalize_prefixes(self._config.get("prefix", ""))
        self._subs = self._config.get("subscribe", [])
        # Optional: direct topic subscription in addition to prefix+key
        self._extra_topics = self._config.get("subscribeTopics", [])
        self._set_map: Dict[str, str] = self._config.get("setMap", {})

        self._client = mqtt.Client(
            protocol=mqtt.MQTTv311,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        self._values: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._running = False

    @staticmethod
    def _load_config(path: Path) -> Dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _normalize_prefixes(prefix: Union[str, Sequence[str]]) -> Sequence[str]:
        if isinstance(prefix, str):
            return [prefix]
        return list(prefix or [])

    @staticmethod
    def _normalize_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Allow both legacy and reviewed JSON formats.

        Legacy:
        {
          "broker": "192.168.1.10",
          "prefix": ["go-eCharger/254959/"],
          "subscribe": ["alw", "amp"]
        }

        Reviewed (per PR comment):
        {
          "broker_ip": "192.168.188.97",
          "goE": [
             "go-eCharger/254959/alw",
             "go-eCharger/254959/amp"
          ]
        }
        """
        out = dict(cfg)
        # broker
        if "broker" not in out and "broker_ip" in out:
            out["broker"] = out["broker_ip"]
        # map goE full topics to subscribeTopics
        if "goE" in out and isinstance(out["goE"], list):
            out.setdefault("subscribeTopics", [])
            # extend, avoiding dups
            existing = set(out["subscribeTopics"]) if isinstance(out["subscribeTopics"], list) else set()
            for t in out["goE"]:
                if t not in existing:
                    existing.add(t)
            out["subscribeTopics"] = list(existing)
            # If no prefix/subscribe provided, leave them empty; we extract keys from last segment
            out.setdefault("prefix", [])
            out.setdefault("subscribe", [])
        return out

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        topics = []
        for p in self._prefixes:
            topics.extend([(f"{p}{t}", 0) for t in self._subs])
        topics.extend([(t, 0) for t in self._extra_topics])
        if topics:
            client.subscribe(topics)

    def _on_message(self, client, userdata, msg):
        # Determine key from last topic segment (e.g., .../alw -> "alw")
        topic = msg.topic or ""
        key = topic.rsplit("/", 1)[-1] if "/" in topic else topic
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

    # Thread lifecycle
    def run(self):
        self._running = True
        self._client.connect(self._broker, 1883, 60)
        self._client.loop_start()
        last_mtime = self._config_path.stat().st_mtime
        try:
            while self._running:
                # Hot-reload config (lightweight)
                try:
                    mtime = self._config_path.stat().st_mtime
                    if mtime != last_mtime:
                        last_mtime = mtime
                        raw = self._load_config(self._config_path)
                        self._config = self._normalize_config(raw)
                        self._prefixes = self._normalize_prefixes(self._config.get("prefix", self._prefixes))
                        self._subs = self._config.get("subscribe", self._subs)
                        self._extra_topics = self._config.get("subscribeTopics", self._extra_topics)
                        self._set_map = self._config.get("setMap", self._set_map)
                        # resubscribe
                        topics = []
                        for p in self._prefixes:
                            topics.extend([(f"{p}{t}", 0) for t in self._subs])
                        topics.extend([(t, 0) for t in self._extra_topics])
                        if topics:
                            self._client.subscribe(topics)
                except Exception:
                    pass
                time.sleep(1.0)
        finally:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass

    def stop(self):
        self._running = False

    # getters / setters
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._values)

    def set(self, key: str, value: Any, qos: int = 0, retain: bool = False) -> bool:
        topic = self._set_map.get(key)
        if not topic:
            return False
        return self.publish(topic, value, qos=qos, retain=retain)

    def publish(self, topic: str, value: Any, qos: int = 0, retain: bool = False) -> bool:
        payload = value
        if not isinstance(value, (str, bytes)):
            payload = json.dumps(value)
        result = self._client.publish(topic, payload, qos=qos, retain=retain)
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    # Convenience properties for common go-eCharger keys
    @property
    def amp(self) -> Any:
        return self.get("amp")

    @amp.setter
    def amp(self, value: Any) -> None:
        self.set("amp", value)

    @property
    def frc(self) -> Any:
        return self.get("frc")

    @frc.setter
    def frc(self, value: Any) -> None:
        self.set("frc", value)

    @property
    def psm(self) -> Any:
        return self.get("psm")

    @psm.setter
    def psm(self, value: Any) -> None:
        self.set("psm", value)
