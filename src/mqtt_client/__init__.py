import time
import paho.mqtt.client as mqtt
import json

DURATION = 10 # wait time for messages in seconds

class mqtt_client:
    broker = "localhost"
    prefix = ""
    api_keys = []
    topics = []
    msg_values = {}
    msg_count = 0
    def __init__(self, ip: str, prefix: str, set_keys: list):
        self.broker = ip
        self.api_keys = set_keys
        self.prefix = prefix
        self.topics = [(f"{prefix}{key}", 0) for key in set_keys]

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        print("Verbunden zum Broker")
        client.subscribe(self.topics)

    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode()
            payload = json.loads(payload)
        except UnicodeDecodeError:
            payload = msg.payload
        self.msg_count += 1
        short_topic = msg.topic.removeprefix(self.prefix)
        self.msg_values[short_topic] = payload

    def publish(self, client, topics:list):
        msg_count = 1

        for topic, msg in topics:
            result = client.publish(topic, msg)
          
            status = result[0]
            if status == 0:
                print(f"Send `{msg}` to topic `{topic}`with result code {status}")
            else:
                print(f"Failed to send message to topic {topic}")
            msg_count += 1
            print(f"published messages: {msg_count}")

    def subscribe(self, publish_topics: list = []):
        self.msg_count = 0
        client = mqtt.Client(protocol=mqtt.MQTTv311,callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = self.on_connect
        client.on_message = self.on_message

        client.connect(self.broker, 1883, 60)
        client.loop_start()

        interval = 0.01  # Sekunden, z.B. 0.01 für kürzere Wartezeit
        iterations = int(DURATION / interval)
        for _ in range(iterations):
            if self.msg_count >= len(self.topics):
                break
            time.sleep(interval)
        self.publish(client, publish_topics)
        client.loop_stop()
        client.disconnect()
        print("MQTT finished")
        return self.msg_values