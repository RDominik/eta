## @file service.py
#  @brief MQTT client service running as a daemon thread.
#
#  Provides a thread-safe MQTT manager that subscribes to topics defined
#  in a JSON configuration, stores incoming message values, and offers
#  publish/subscribe helpers for inter-module communication.

import paho.mqtt.client as mqtt
import threading
import json
from pathlib import Path
from typing import Any


class MQTTManager(threading.Thread):
    """@brief MQTT service running in its own daemon thread.

    Subscribes to topics from a JSON config file, stores the latest
    received value per topic key, and provides thread-safe getters
    and a generic publish method.

    @param broker_config  Path to the JSON broker configuration file.
    """

    def __init__(self, broker_config: Path):
        super().__init__(daemon=True)
        config = self._load_config(broker_config)

        ## @brief MQTT broker hostname/IP.
        self.broker = config.get("broker_ip") or config.get("broker") or "localhost"

        # Collect all list-valued items from JSON as subscription topics
        topics_list: list[str] = []
        for section, entries in config.items():
            if section in ("broker_ip", "broker"):
                continue
            if isinstance(entries, list):
                for item in entries:
                    if isinstance(item, str):
                        topics_list.append(item)

        ## @brief List of (topic, qos) tuples for MQTT subscription.
        self.topics = [(entry, 0) for entry in topics_list]

        self.client = mqtt.Client(protocol=mqtt.MQTTv311, callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish

        ## @brief True when connected to broker, False otherwise.
        self._connected = threading.Event()
        ## @brief Dict storing the latest received value per short topic key.
        self.received: dict[str, Any] = {}
        ## @brief Lock for thread-safe access to received data.
        self.rx_lock = threading.Lock()

    @staticmethod
    def _load_config(path: str | Path) -> dict:
        """@brief Load broker configuration from a JSON file.
        @param path  Path to the JSON configuration file.
        @return dict with configuration data.
        """
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @property
    def message(self) -> dict:
        """@brief Thread-safe getter for all received MQTT messages.
        @return Copy of the received messages dictionary.
        """
        with self.rx_lock:
            return dict(self.received)

    @message.setter
    def message(self, value: dict) -> None:
        """@brief Thread-safe setter to replace the received messages dict.
        @param value  New dictionary of messages.
        """
        with self.rx_lock:
            self.received = value

    def set_keys(self, data: list, qos: int = 0, retain: bool = False) -> None:
        """@brief Publish multiple key-value pairs via MQTT.

        @param data    List of [topic, value] pairs.
        @param qos     MQTT Quality of Service level (default 0).
        @param retain  Whether the broker should retain messages (default False).
        """
        for key, value in data:
            self.publish(key, value, qos=qos, retain=retain)

    def publish(self, topic: str, msg: Any, qos: int = 0, retain: bool = False):
        """@brief Publish a message to an MQTT topic.

        Waits up to 5 seconds for an active broker connection before
        attempting to publish. Reconnection is handled automatically
        by paho's loop_forever().

        @param topic   MQTT topic string.
        @param msg     Message payload (will be serialized by paho).
        @param qos     MQTT QoS level.
        @param retain  Retain flag.
        @return paho MQTTMessageInfo or None on failure / not connected.
        """
        if not self._connected.wait(timeout=5):
            print(f"MQTT not connected, dropping message for {topic}")
            return None
        try:
            result = self.client.publish(topic, msg, qos=qos, retain=retain)
            status = getattr(result, "rc", None)
            if status != 0:
                print(f"Failed to send message to topic {topic} rc={status}")
            return result
        except (BrokenPipeError, OSError) as e:
            print(f"MQTT publish error: {e} — waiting for auto-reconnect")
            self._connected.clear()
            return None

    def _on_publish(self, client, userdata, mid, *args, **kwargs):
        """@brief Callback invoked when a message has been published.
        @param client    MQTT client instance.
        @param userdata  User data (unused).
        @param mid       Message ID of the published message.
        """
        print(f"📤 Message published (mid={mid})")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        """@brief Callback invoked on successful broker connection.

        Subscribes to all configured topics upon connection.

        @param client       MQTT client instance.
        @param userdata     User data (unused).
        @param flags        Response flags from the broker.
        @param reason_code  Connection result code.
        @param properties   MQTT v5 properties (optional).
        """
        print(f"broker connected with result code {reason_code}")
        self._connected.set()
        client.subscribe(self.topics)

    def _on_disconnect(self, client, userdata, *args, **kwargs):
        """@brief Callback invoked when the broker connection is lost.

        Clears the connected flag so publish() will wait for reconnect
        instead of writing to a broken socket.
        """
        self._connected.clear()
        print("⚠️ MQTT disconnected — loop_forever will auto-reconnect")

    def _on_message(self, client, userdata, msg):
        """@brief Callback invoked when a subscribed message is received.

        Stores the decoded payload in self.received keyed by the
        last segment of the topic path.

        @param client    MQTT client instance.
        @param userdata  User data (unused).
        @param msg       MQTTMessage with topic and payload.
        """
        try:
            payload = msg.payload.decode()
            payload = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = msg.payload

        short_topic = msg.topic.split("/")[-1]
        with self.rx_lock:
            self.received[short_topic] = payload

    def run(self):
        """@brief Thread entry point – connects to broker and runs the MQTT loop.

        Uses loop_forever() which handles reconnection automatically.
        """
        self.client.connect(self.broker, 1883, 60)
        self.client.loop_forever()
