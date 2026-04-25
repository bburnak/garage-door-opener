"""
Example configuration for garage door opener.

Copy this file to `config.py` and fill in your actual values.
`config.py` is gitignored so your credentials stay local.
"""

# Raspberry Pi GPIO settings
GPIO_PIN = 17  # Physical Pin 11 on Raspberry Pi
RELAY_ACTIVATION_TIME = 0.3  # seconds

# MQTT settings
MQTT_BROKER = "homeassistant.local"  # Home Assistant IP or hostname
MQTT_PORT = 1883
MQTT_USERNAME = "your_mqtt_username"
MQTT_PASSWORD = "your_mqtt_password"

# Topic configuration
MQTT_COMMAND_TOPIC = "homeassistant/garage/command"
MQTT_STATE_TOPIC = "homeassistant/garage/state"

# Relay behavior
# Some relay modules are active-LOW (GPIO LOW = relay ON)
# Set to True if your relay activates on LOW signal
RELAY_ACTIVE_LOW = False
