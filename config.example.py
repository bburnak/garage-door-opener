"""
Example configuration for garage door opener.

Copy this file to `config.py` and fill in your actual values.
`config.py` is gitignored so your credentials stay local.
"""

# ---------------------------------------------------------------------------
# Raspberry Pi GPIO
# ---------------------------------------------------------------------------
GPIO_PIN = 17  # BCM numbering; physical pin 11 on Raspberry Pi
RELAY_ACTIVATION_TIME = 0.3  # seconds the relay is held closed (button press)

# Some relay modules are active-LOW (GPIO LOW = relay ON).
# Set to True if your relay clicks when GPIO is LOW.
RELAY_ACTIVE_LOW = False

# ---------------------------------------------------------------------------
# MQTT broker
# ---------------------------------------------------------------------------
MQTT_BROKER = "homeassistant.local"   # Mosquitto add-on host (HA's IP/hostname)
MQTT_PORT = 1883
MQTT_USERNAME = "your_mqtt_username"
MQTT_PASSWORD = "your_mqtt_password"

# ---------------------------------------------------------------------------
# Device identity
# ---------------------------------------------------------------------------
# Stable unique ID; only change if you want HA to treat this as a new device.
DEVICE_ID = "garage_door_pi"
DEVICE_NAME = "Garage Door"

# How long the door takes to fully open or close, in seconds.
# Used only to transition the reported state from "opening"/"closing" to
# "open"/"closed" in Home Assistant. Tune to match your real door.
TRAVEL_TIME = 15.0

# Initial assumed state on first start: "closed" or "open".
INITIAL_STATE = "closed"

# ---------------------------------------------------------------------------
# MQTT topics (auto-derived from DEVICE_ID; usually no need to change)
# ---------------------------------------------------------------------------
MQTT_BASE_TOPIC = f"garage_door/{DEVICE_ID}"
MQTT_COMMAND_TOPIC = f"{MQTT_BASE_TOPIC}/set"
MQTT_STATE_TOPIC = f"{MQTT_BASE_TOPIC}/state"
MQTT_AVAILABILITY_TOPIC = f"{MQTT_BASE_TOPIC}/availability"

# Home Assistant MQTT discovery
# (HA's default discovery prefix is "homeassistant"; leave as-is unless changed in HA.)
HA_DISCOVERY_PREFIX = "homeassistant"
