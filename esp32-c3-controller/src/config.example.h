#pragma once

// Copy this file to config.h and fill in your values.
// config.h is gitignored so credentials stay local.

// ============================================================================
// WiFi
// ============================================================================
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// ============================================================================
// MQTT broker
// ============================================================================
#define MQTT_BROKER "homeassistant.local"
#define MQTT_PORT 1883
#define MQTT_USERNAME "your_mqtt_username"  // Leave empty if no auth
#define MQTT_PASSWORD "your_mqtt_password"  // Leave empty if no auth

// ============================================================================
// Device identity -- identical to the Raspberry Pi controller so Home
// Assistant sees the same cover entity and topics after the swap.
// ============================================================================
#define DEVICE_ID "garage_door_pi"
#define DEVICE_NAME "Garage Door"

#define MQTT_BASE_TOPIC "garage_door/" DEVICE_ID
#define MQTT_TOPIC_COMMAND MQTT_BASE_TOPIC "/set"
#define MQTT_TOPIC_STATE MQTT_BASE_TOPIC "/state"
#define MQTT_TOPIC_AVAILABILITY MQTT_BASE_TOPIC "/availability"
#define HA_DISCOVERY_PREFIX "homeassistant"

// ============================================================================
// Relay
// ============================================================================
#define RELAY_PIN 4                  // Not a strapping pin (avoid 2, 8, 9) or USB pin (18, 19)
#define RELAY_ACTIVE_LOW false       // true if the relay clicks when the pin is LOW
#define RELAY_ACTIVATION_MS 300      // How long the relay is held closed (button press)

// How long the door takes to fully open or close. Used only to move the
// reported state from opening/closing to open/closed.
#define TRAVEL_TIME_MS 15000

// Used only the very first time the device boots (afterwards the last
// assumed state is restored from flash). "closed" or "open".
#define INITIAL_STATE "closed"

// Commands arriving this soon after (re)subscribing are dropped. PubSubClient
// cannot tell retained messages from live ones, and a stale retained "open"
// replayed at boot would move the door.
#define COMMAND_GRACE_MS 2000

// If MQTT has been unreachable this long, reboot to recover a stuck Wi-Fi stack.
#define MQTT_WATCHDOG_MS 300000
