#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include "config.h"

// ============================================================================
// Global State
// ============================================================================

static int last_raw = HIGH;
static int stable_raw = HIGH;
static uint32_t last_change_ms = 0;
static uint32_t last_publish_ms = 0;

static WiFiClient wifi_client;
static PubSubClient mqtt_client(wifi_client);

static bool mqtt_connected = false;
static bool wifi_connected = false;

// ============================================================================
// Helper Functions
// ============================================================================

static const char *door_state_from_raw(int raw)
{
    const bool switch_closed = (raw == LOW);
    const bool door_closed = DOOR_CLOSED_WHEN_SWITCH_CLOSED ? switch_closed : !switch_closed;
    return door_closed ? "closed" : "open";
}

static void print_state(const char *prefix, int raw)
{
    Serial.print(prefix);
    Serial.print(" raw=");
    Serial.print(raw == LOW ? "LOW" : "HIGH");
    Serial.print(" door=");
    Serial.println(door_state_from_raw(raw));
}

// ============================================================================
// WiFi
// ============================================================================

static void setup_wifi()
{
    Serial.print("Connecting to WiFi: ");
    Serial.println(WIFI_SSID);

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start) < 20000)
    {
        delay(500);
        Serial.print(".");
    }

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println();
        Serial.print("WiFi connected. IP: ");
        Serial.println(WiFi.localIP());
        wifi_connected = true;
    }
    else
    {
        Serial.println();
        Serial.println("WiFi failed.");
        wifi_connected = false;
    }
}

static void maintain_wifi()
{
    if (WiFi.status() == WL_CONNECTED)
    {
        if (!wifi_connected)
        {
            Serial.println("WiFi reconnected.");
            wifi_connected = true;
        }
    }
    else
    {
        if (wifi_connected)
        {
            Serial.println("WiFi disconnected.");
            wifi_connected = false;
            mqtt_connected = false;
        }
    }
}

// ============================================================================
// MQTT
// ============================================================================

static void publish_discovery()
{
    // Home Assistant MQTT Discovery for binary_sensor
    const char *payload = "{"
        "\"name\":\"" DEVICE_NAME "\","
        "\"unique_id\":\"" DEVICE_ID "_door\","
        "\"device_class\":\"door\","
        "\"state_topic\":\"" MQTT_TOPIC_STATE "\","
        "\"payload_on\":\"open\","
        "\"payload_off\":\"closed\","
        "\"availability_topic\":\"" MQTT_TOPIC_AVAILABILITY "\","
        "\"payload_available\":\"" PAYLOAD_ONLINE "\","
        "\"payload_not_available\":\"" PAYLOAD_OFFLINE "\","
        "\"device\":{"
            "\"identifiers\":[\"" DEVICE_ID "\"],"
            "\"name\":\"" DEVICE_NAME "\","
            "\"manufacturer\":\"DIY\","
            "\"model\":\"ESP32-C3 Reed Switch Sensor\""
        "}"
        "}";

    if (mqtt_client.publish(MQTT_TOPIC_HA_DISCOVERY, payload, true))
    {
        Serial.println("HA discovery published");
    }
    else
    {
        Serial.println("HA discovery failed");
    }
}

static void on_mqtt_message(char *topic, byte *payload, unsigned int length)
{
    // Not subscribing to any topics yet, but this is the handler
    Serial.print("MQTT message on ");
    Serial.println(topic);
}

static void setup_mqtt()
{
    mqtt_client.setServer(MQTT_BROKER, MQTT_PORT);
    mqtt_client.setCallback(on_mqtt_message);
    mqtt_client.setBufferSize(512);
    Serial.print("MQTT buffer size: ");
    Serial.println(mqtt_client.getBufferSize());
}

static void reconnect_mqtt()
{
    if (!wifi_connected || mqtt_client.connected())
    {
        return;
    }

    Serial.print("MQTT connecting to ");
    Serial.print(MQTT_BROKER);
    Serial.print(":");
    Serial.println(MQTT_PORT);

    const char *client_id = DEVICE_ID;
    const char *user = (strlen(MQTT_USERNAME) > 0) ? MQTT_USERNAME : nullptr;
    const char *pass = (strlen(MQTT_PASSWORD) > 0) ? MQTT_PASSWORD : nullptr;

    if (mqtt_client.connect(client_id, user, pass, MQTT_TOPIC_AVAILABILITY, 1, true, PAYLOAD_OFFLINE))
    {
        Serial.println("MQTT connected");
        mqtt_connected = true;

        // Announce we are online
        mqtt_client.publish(MQTT_TOPIC_AVAILABILITY, PAYLOAD_ONLINE, true);

        // Publish discovery config
        publish_discovery();

        // Publish current state
        mqtt_client.publish(MQTT_TOPIC_STATE, door_state_from_raw(stable_raw), true);
        Serial.print("Published initial state: ");
        Serial.println(door_state_from_raw(stable_raw));
    }
    else
    {
        Serial.print("MQTT failed, rc=");
        Serial.println(mqtt_client.state());
        mqtt_connected = false;
    }
}

static void maintain_mqtt()
{
    if (!wifi_connected)
    {
        if (mqtt_connected)
        {
            Serial.println("MQTT disconnected (WiFi lost)");
            mqtt_connected = false;
        }
        return;
    }

    if (!mqtt_client.connected())
    {
        if (mqtt_connected)
        {
            Serial.println("MQTT connection lost");
            mqtt_connected = false;
        }

        // Try to reconnect every 10 seconds
        static uint32_t last_reconnect = 0;
        if ((millis() - last_reconnect) > 10000)
        {
            last_reconnect = millis();
            reconnect_mqtt();
        }
    }
    else
    {
        // Process MQTT messages
        mqtt_client.loop();
    }
}

static void publish_state_change(int raw)
{
    const char *state = door_state_from_raw(raw);

    if (mqtt_connected)
    {
        if (mqtt_client.publish(MQTT_TOPIC_STATE, state, true))
        {
            Serial.print("MQTT published: ");
            Serial.println(state);
        }
        else
        {
            Serial.println("MQTT publish failed");
        }
    }
    else
    {
        Serial.print("State change but MQTT not connected: ");
        Serial.println(state);
    }

    last_publish_ms = millis();
}

// ============================================================================
// Setup
// ============================================================================

void setup()
{
    pinMode(REED_PIN, INPUT_PULLUP);

    Serial.begin(115200);
    delay(300);
    Serial.println();
    Serial.println("ESP32-C3 garage door sensor (with MQTT)");

    stable_raw = digitalRead(REED_PIN);
    last_raw = stable_raw;
    last_change_ms = millis();
    last_publish_ms = millis();

    print_state("boot", stable_raw);

    // Connect to WiFi
    setup_wifi();

    // Setup MQTT
    setup_mqtt();
}

// ============================================================================
// Loop
// ============================================================================

void loop()
{
    // Read reed switch with debounce
    const int raw = digitalRead(REED_PIN);
    const uint32_t now = millis();

    if (raw != last_raw)
    {
        last_raw = raw;
        last_change_ms = now;
    }

    if (raw != stable_raw && (now - last_change_ms) >= DEBOUNCE_MS)
    {
        stable_raw = raw;
        print_state("change", stable_raw);
        publish_state_change(stable_raw);
    }

    // Maintain WiFi connection
    maintain_wifi();

    // Maintain MQTT connection and publish heartbeat
    maintain_mqtt();

    if (mqtt_connected && (now - last_publish_ms) > MQTT_HEARTBEAT_INTERVAL_MS)
    {
        // Periodic heartbeat to confirm we're still alive
        mqtt_client.publish(MQTT_TOPIC_STATE, door_state_from_raw(stable_raw), true);
        last_publish_ms = now;
    }

    delay(5);
}
