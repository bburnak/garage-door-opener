// ESP32-C3 garage door controller.
//
// Drop-in replacement for garage_door_opener.py on the Raspberry Pi: same
// device ID, same MQTT topics, same Home Assistant cover entity. It pulses a
// relay across the opener's button terminals and reports an *assumed* state
// (the separate ESP32-C3 reed-switch sensor provides the real door state).

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Preferences.h>
#include "config.h"

#define PAYLOAD_ONLINE "online"
#define PAYLOAD_OFFLINE "offline"

enum DoorState { DOOR_OPEN, DOOR_CLOSED, DOOR_OPENING, DOOR_CLOSING };

static const char *state_name(DoorState s)
{
    switch (s)
    {
    case DOOR_OPEN:    return "open";
    case DOOR_CLOSED:  return "closed";
    case DOOR_OPENING: return "opening";
    default:           return "closing";
    }
}

static WiFiClient wifi_client;
static PubSubClient mqtt_client(wifi_client);
static Preferences prefs;

static bool wifi_connected = false;
static bool mqtt_connected = false;
static uint32_t last_mqtt_ok_ms = 0;
static uint32_t subscribed_at_ms = 0;

// Door / relay state machine (all non-blocking so MQTT keeps running).
static DoorState assumed_state = DOOR_CLOSED;  // only ever OPEN or CLOSED at rest
static DoorState target_state = DOOR_CLOSED;
static bool relay_on = false;
static uint32_t relay_off_at_ms = 0;
static bool moving = false;
static uint32_t travel_done_at_ms = 0;

// ============================================================================
// Relay
// ============================================================================

static void relay_write(bool on)
{
    digitalWrite(RELAY_PIN, (on != (bool)RELAY_ACTIVE_LOW) ? HIGH : LOW);
    relay_on = on;
}

static void start_pulse()
{
    relay_write(true);
    relay_off_at_ms = millis() + RELAY_ACTIVATION_MS;
}

// ============================================================================
// MQTT publishing
// ============================================================================

static void publish_state(DoorState s)
{
    if (!mqtt_connected)
        return;
    mqtt_client.publish(MQTT_TOPIC_STATE, state_name(s), true);
    Serial.print("Published state: ");
    Serial.println(state_name(s));
}

static void publish_discovery()
{
    static const char topic[] =
        HA_DISCOVERY_PREFIX "/cover/" DEVICE_ID "/" DEVICE_ID "_cover/config";
    static const char payload[] = "{"
        "\"name\":\"" DEVICE_NAME "\","
        "\"unique_id\":\"" DEVICE_ID "_cover\","
        "\"object_id\":\"" DEVICE_ID "\","
        "\"device_class\":\"garage\","
        "\"command_topic\":\"" MQTT_TOPIC_COMMAND "\","
        "\"state_topic\":\"" MQTT_TOPIC_STATE "\","
        "\"availability_topic\":\"" MQTT_TOPIC_AVAILABILITY "\","
        "\"payload_available\":\"" PAYLOAD_ONLINE "\","
        "\"payload_not_available\":\"" PAYLOAD_OFFLINE "\","
        "\"payload_open\":\"open\","
        "\"payload_close\":\"close\","
        "\"payload_stop\":\"stop\","
        "\"state_open\":\"open\","
        "\"state_closed\":\"closed\","
        "\"state_opening\":\"opening\","
        "\"state_closing\":\"closing\","
        "\"optimistic\":false,"
        "\"qos\":1,"
        "\"retain\":false,"
        "\"device\":{"
            "\"identifiers\":[\"" DEVICE_ID "\"],"
            "\"name\":\"" DEVICE_NAME "\","
            "\"manufacturer\":\"DIY\","
            "\"model\":\"ESP32-C3 + relay\""
        "}}";

    Serial.println(mqtt_client.publish(topic, payload, true)
                       ? "HA discovery published"
                       : "HA discovery failed");
}

// ============================================================================
// Door actions
// ============================================================================

static void save_state()
{
    prefs.putUChar("state", assumed_state == DOOR_OPEN ? 1 : 0);
}

static void trigger_door(const char *action)
{
    if (moving)
    {
        Serial.print("Door already moving, ignoring ");
        Serial.println(action);
        return;
    }

    if (strcmp(action, "open") == 0)
        target_state = DOOR_OPEN;
    else if (strcmp(action, "close") == 0)
        target_state = DOOR_CLOSED;
    else  // toggle
        target_state = (assumed_state == DOOR_OPEN) ? DOOR_CLOSED : DOOR_OPEN;

    Serial.print("Pulsing relay (action=");
    Serial.print(action);
    Serial.print(", target=");
    Serial.print(state_name(target_state));
    Serial.println(")");

    moving = true;
    travel_done_at_ms = millis() + RELAY_ACTIVATION_MS + TRAVEL_TIME_MS;
    publish_state(target_state == DOOR_OPEN ? DOOR_OPENING : DOOR_CLOSING);
    start_pulse();
}

static void on_mqtt_message(char *topic, byte *payload, unsigned int length)
{
    if ((millis() - subscribed_at_ms) < COMMAND_GRACE_MS)
    {
        Serial.println("Ignoring command inside post-subscribe grace window (possible retained message)");
        return;
    }

    char cmd[16];
    unsigned int n = length < sizeof(cmd) - 1 ? length : sizeof(cmd) - 1;
    for (unsigned int i = 0; i < n; i++)
        cmd[i] = tolower((char)payload[i]);
    cmd[n] = '\0';

    Serial.print("Received command: ");
    Serial.println(cmd);

    if (!strcmp(cmd, "open") || !strcmp(cmd, "close") || !strcmp(cmd, "toggle"))
    {
        trigger_door(cmd);
    }
    else if (!strcmp(cmd, "stop"))
    {
        if (moving && !relay_on)
        {
            // A second button press halts a moving door. A halted door is
            // partly open, so report "open" (never "closed").
            Serial.println("Stop: pulsing relay to halt door");
            start_pulse();
            moving = false;
            assumed_state = DOOR_OPEN;
            save_state();
            publish_state(assumed_state);
        }
        else
        {
            Serial.println("Stop ignored: door not moving");
        }
    }
    else
    {
        Serial.println("Ignoring unknown command");
    }
}

// ============================================================================
// WiFi / MQTT connection management
// ============================================================================

static void setup_wifi()
{
    Serial.print("Connecting to WiFi: ");
    Serial.println(WIFI_SSID);

    WiFi.mode(WIFI_STA);
    // Many ESP32-C3 Mini boards fail to associate at full TX power (weak
    // antenna / supply). Override in config.h if you need a different level.
#ifndef WIFI_TX_POWER
#define WIFI_TX_POWER WIFI_POWER_8_5dBm
#endif
    WiFi.setTxPower(WIFI_TX_POWER);
    WiFi.setSleep(false);  // modem sleep off: commands arrive immediately instead of waiting for the next beacon
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start) < 20000)
    {
        delay(250);
        Serial.print(".");
    }
    Serial.println();

    wifi_connected = (WiFi.status() == WL_CONNECTED);
    if (wifi_connected)
    {
        Serial.print("WiFi connected. IP: ");
        Serial.println(WiFi.localIP());
    }
    else
    {
        Serial.print("WiFi failed (will keep retrying). status=");
        Serial.print((int)WiFi.status());
        Serial.println(" (1=SSID not found, 4=connect failed/wrong password, 6=disconnected)");

        Serial.println("Scanning for 2.4 GHz networks...");
        WiFi.disconnect();  // a scan during a pending connect returns nothing
        delay(200);
        int n = WiFi.scanNetworks();
        for (int i = 0; i < n; i++)
        {
            Serial.print("  ");
            Serial.print(WiFi.SSID(i));
            Serial.print("  rssi=");
            Serial.print(WiFi.RSSI(i));
            Serial.print("  ch=");
            Serial.println(WiFi.channel(i));
        }
        if (n <= 0)
            Serial.println("  (no networks found)");
        WiFi.scanDelete();
    }
}

static void maintain_wifi()
{
    if (WiFi.status() == WL_CONNECTED)
    {
        if (!wifi_connected)
        {
            Serial.print("WiFi reconnected. IP: ");
            Serial.println(WiFi.localIP());
            wifi_connected = true;
        }
        return;
    }

    if (wifi_connected)
    {
        Serial.println("WiFi disconnected.");
        wifi_connected = false;
        mqtt_connected = false;
    }

    static uint32_t last_attempt_ms = 0;
    if ((millis() - last_attempt_ms) > 30000)
    {
        last_attempt_ms = millis();
        Serial.println("WiFi: retrying connection...");
        WiFi.disconnect(true);
        WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    }
}

static void reconnect_mqtt()
{
    Serial.print("MQTT connecting to ");
    Serial.print(MQTT_BROKER);
    Serial.print(":");
    Serial.println(MQTT_PORT);

    const char *user = (strlen(MQTT_USERNAME) > 0) ? MQTT_USERNAME : nullptr;
    const char *pass = (strlen(MQTT_PASSWORD) > 0) ? MQTT_PASSWORD : nullptr;

    if (mqtt_client.connect(DEVICE_ID, user, pass, MQTT_TOPIC_AVAILABILITY, 1, true, PAYLOAD_OFFLINE))
    {
        Serial.println("MQTT connected");
        mqtt_connected = true;
        last_mqtt_ok_ms = millis();

        subscribed_at_ms = millis();
        mqtt_client.subscribe(MQTT_TOPIC_COMMAND, 1);

        publish_discovery();
        mqtt_client.publish(MQTT_TOPIC_AVAILABILITY, PAYLOAD_ONLINE, true);
        publish_state(moving ? (target_state == DOOR_OPEN ? DOOR_OPENING : DOOR_CLOSING)
                             : assumed_state);
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
        mqtt_connected = false;
        return;
    }

    if (mqtt_client.connected())
    {
        mqtt_connected = true;
        last_mqtt_ok_ms = millis();
        mqtt_client.loop();
        return;
    }

    if (mqtt_connected)
    {
        Serial.println("MQTT connection lost");
        mqtt_connected = false;
    }

    static uint32_t last_reconnect_ms = 0;
    if ((millis() - last_reconnect_ms) > 10000)
    {
        last_reconnect_ms = millis();
        reconnect_mqtt();
    }
}

// ============================================================================
// Arduino entry points
// ============================================================================

void setup()
{
    // First thing: drive the relay to its inactive level.
    pinMode(RELAY_PIN, OUTPUT);
    relay_write(false);

    Serial.begin(115200);
    delay(300);
    Serial.println();
    Serial.println("ESP32-C3 garage door controller");

    prefs.begin("garage", false);
    uint8_t saved = prefs.getUChar("state", strcmp(INITIAL_STATE, "open") == 0 ? 1 : 0);
    assumed_state = saved ? DOOR_OPEN : DOOR_CLOSED;
    Serial.print("Assumed state: ");
    Serial.println(state_name(assumed_state));

    setup_wifi();

    mqtt_client.setServer(MQTT_BROKER, MQTT_PORT);
    mqtt_client.setCallback(on_mqtt_message);
    mqtt_client.setBufferSize(1024);
    last_mqtt_ok_ms = millis();
}

void loop()
{
    const uint32_t now = millis();

    // End of relay pulse.
    if (relay_on && (int32_t)(now - relay_off_at_ms) >= 0)
    {
        relay_write(false);
        Serial.println("Relay released");
    }

    // End of door travel.
    if (moving && !relay_on && (int32_t)(now - travel_done_at_ms) >= 0)
    {
        moving = false;
        assumed_state = target_state;
        save_state();
        publish_state(assumed_state);
        Serial.print("Door is now ");
        Serial.println(state_name(assumed_state));
    }

    maintain_wifi();
    maintain_mqtt();

    // Reboot to recover from a stuck network stack, but never mid-move.
    if (!mqtt_connected && !moving && (now - last_mqtt_ok_ms) > MQTT_WATCHDOG_MS)
    {
        Serial.println("MQTT offline too long, restarting...");
        delay(100);
        ESP.restart();
    }

    delay(5);
}
