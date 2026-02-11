# Backwards-compat shim (optional import path)
# Prefer using mqtt_client.service.MqttService
from .service import MqttService  # noqa: F401
