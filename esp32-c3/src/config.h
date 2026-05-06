#pragma once

// ============================================================================
// WiFi Configuration
// ============================================================================
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"

// ============================================================================
// MQTT Configuration
// ============================================================================
#define MQTT_BROKER "mqtt-broker.local"  // IP or hostname of MQTT broker
#define MQTT_PORT 1883
#define MQTT_USERNAME "your_mqtt_username"    // Leave empty if no auth
#define MQTT_PASSWORD "your_mqtt_password" // Leave empty if no auth

// Device identity
#define DEVICE_ID "garage_door_sensor"
#define DEVICE_NAME "Garage Door Sensor"

// MQTT Topics
#define MQTT_TOPIC_STATE "garage_door/state"
#define MQTT_TOPIC_AVAILABILITY "garage_door/availability"
#define MQTT_TOPIC_HA_DISCOVERY "homeassistant/binary_sensor/" DEVICE_ID "/config"

// Payload strings
#define PAYLOAD_ONLINE "online"
#define PAYLOAD_OFFLINE "offline"

// ============================================================================
// Reed Switch Behavior
// ============================================================================
// Set this according to your physical magnet placement.
// true  => closed switch means door closed
// false => closed switch means door open
#define DOOR_CLOSED_WHEN_SWITCH_CLOSED true

// Pin configuration
#define REED_PIN 21
#define DEBOUNCE_MS 40

// MQTT publish interval (milliseconds) for heartbeat
#define MQTT_HEARTBEAT_INTERVAL_MS 30000
