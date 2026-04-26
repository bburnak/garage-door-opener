#!/usr/bin/env python3
"""
Garage door opener integration for Home Assistant.

Two modes:
  - daemon  : connect to MQTT, advertise via HA discovery, react to commands.
              (default if no subcommand is given)
  - trigger : pulse the relay once and exit. No MQTT involved.
              Useful from an SSH session.

Examples:
    python garage_door_opener.py
    python garage_door_opener.py daemon
    python garage_door_opener.py trigger
    python garage_door_opener.py trigger open
"""

import argparse
import json
import logging
import sys
import time
from threading import Thread, Lock

try:
    import RPi.GPIO as GPIO
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: Required packages not installed.")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

from config import (
    GPIO_PIN,
    RELAY_ACTIVATION_TIME,
    RELAY_ACTIVE_LOW,
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    DEVICE_ID,
    DEVICE_NAME,
    TRAVEL_TIME,
    INITIAL_STATE,
    MQTT_COMMAND_TOPIC,
    MQTT_STATE_TOPIC,
    MQTT_AVAILABILITY_TOPIC,
    HA_DISCOVERY_PREFIX,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Cover states (match Home Assistant's MQTT cover defaults)
STATE_OPEN = "open"
STATE_CLOSED = "closed"
STATE_OPENING = "opening"
STATE_CLOSING = "closing"

PAYLOAD_AVAILABLE = "online"
PAYLOAD_NOT_AVAILABLE = "offline"


class GarageDoorController:
    def __init__(self):
        self.gpio_pin = GPIO_PIN
        self.relay_active_low = RELAY_ACTIVE_LOW
        self.activation_time = RELAY_ACTIVATION_TIME
        self.travel_time = TRAVEL_TIME

        # Assumed door state. We have no real sensor, so we toggle on each press.
        if INITIAL_STATE not in (STATE_OPEN, STATE_CLOSED):
            raise ValueError(
                f"INITIAL_STATE must be 'open' or 'closed', got {INITIAL_STATE!r}"
            )
        self.assumed_state = INITIAL_STATE
        self._action_lock = Lock()

        self._setup_gpio()

        self.client = mqtt.Client(client_id=DEVICE_ID)
        self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        # LWT: if we drop off the network, the broker will publish "offline".
        self.client.will_set(
            MQTT_AVAILABILITY_TOPIC, PAYLOAD_NOT_AVAILABLE, qos=1, retain=True
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

    # -- GPIO ---------------------------------------------------------------

    def _setup_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.gpio_pin, GPIO.OUT)
        self._relay_off()
        logger.info("GPIO %s initialized", self.gpio_pin)

    def _relay_on(self):
        GPIO.output(self.gpio_pin, GPIO.LOW if self.relay_active_low else GPIO.HIGH)
        logger.debug("Relay ON")

    def _relay_off(self):
        GPIO.output(self.gpio_pin, GPIO.HIGH if self.relay_active_low else GPIO.LOW)
        logger.debug("Relay OFF")

    def _pulse_relay(self):
        """One physical button press."""
        self._relay_on()
        time.sleep(self.activation_time)
        self._relay_off()

    # -- High-level actions -------------------------------------------------

    def trigger_door(self, action="toggle"):
        """
        Pulse the relay once and update assumed state.

        `action` is one of: open, close, toggle. The relay pulse is identical
        in all cases (it just emulates one button press); the label only
        affects which transition we report to Home Assistant.
        """
        if not self._action_lock.acquire(blocking=False):
            logger.warning("Door already moving, ignoring %s", action)
            return

        try:
            if action == "open":
                target = STATE_OPEN
            elif action == "close":
                target = STATE_CLOSED
            else:  # toggle
                target = STATE_CLOSED if self.assumed_state == STATE_OPEN else STATE_OPEN

            transitional = STATE_OPENING if target == STATE_OPEN else STATE_CLOSING
            self.publish_state(transitional)

            logger.info("Pulsing relay (action=%s, target=%s)", action, target)
            self._pulse_relay()

            # Wait for the door to physically finish moving before reporting final state.
            time.sleep(self.travel_time)

            self.assumed_state = target
            self.publish_state(target)
            logger.info("Door is now %s", target)
        except Exception:
            logger.exception("Error triggering door")
            raise
        finally:
            self._action_lock.release()

    # -- MQTT ---------------------------------------------------------------

    def on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            logger.error("MQTT connection failed (rc=%s)", rc)
            return

        logger.info("Connected to MQTT broker %s:%s", MQTT_BROKER, MQTT_PORT)
        client.subscribe(MQTT_COMMAND_TOPIC, qos=1)
        logger.info("Subscribed to %s", MQTT_COMMAND_TOPIC)

        self._publish_discovery()
        client.publish(
            MQTT_AVAILABILITY_TOPIC, PAYLOAD_AVAILABLE, qos=1, retain=True
        )
        # Re-publish current assumed state so HA picks it up immediately.
        self.publish_state(self.assumed_state)

    def on_message(self, client, userdata, msg):
        # Ignore retained command messages: they're stale, left over from a
        # previous session, and replaying them would (re)open the door at boot.
        if msg.retain:
            logger.info(
                "Ignoring retained command on %s: %r",
                msg.topic,
                msg.payload[:64],
            )
            return

        try:
            payload = msg.payload.decode("utf-8").strip().lower()
        except Exception:
            logger.exception("Could not decode MQTT payload")
            return

        logger.info("Received %s on %s", payload, msg.topic)

        if payload in ("open", "close", "toggle"):
            Thread(target=self.trigger_door, args=(payload,), daemon=True).start()
        elif payload == "stop":
            # Real garage openers stop on a second button press while moving.
            Thread(target=self.trigger_door, args=("toggle",), daemon=True).start()
        else:
            logger.warning("Ignoring unknown command: %r", payload)

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning("Unexpected MQTT disconnection (rc=%s); will retry", rc)
        else:
            logger.info("Disconnected from MQTT broker")

    def publish_state(self, state):
        if not self.client.is_connected():
            return
        self.client.publish(MQTT_STATE_TOPIC, state, qos=1, retain=True)
        logger.info("Published state: %s", state)

    def _publish_discovery(self):
        """Tell Home Assistant about this cover via MQTT discovery."""
        unique_id = f"{DEVICE_ID}_cover"
        config_topic = (
            f"{HA_DISCOVERY_PREFIX}/cover/{DEVICE_ID}/{unique_id}/config"
        )
        payload = {
            "name": DEVICE_NAME,
            "unique_id": unique_id,
            "object_id": DEVICE_ID,
            "device_class": "garage",
            "command_topic": MQTT_COMMAND_TOPIC,
            "state_topic": MQTT_STATE_TOPIC,
            "availability_topic": MQTT_AVAILABILITY_TOPIC,
            "payload_available": PAYLOAD_AVAILABLE,
            "payload_not_available": PAYLOAD_NOT_AVAILABLE,
            "payload_open": "open",
            "payload_close": "close",
            "payload_stop": "stop",
            "state_open": STATE_OPEN,
            "state_closed": STATE_CLOSED,
            "state_opening": STATE_OPENING,
            "state_closing": STATE_CLOSING,
            "optimistic": False,
            "qos": 1,
            "retain": False,
            "device": {
                "identifiers": [DEVICE_ID],
                "name": DEVICE_NAME,
                "manufacturer": "DIY",
                "model": "Raspberry Pi + relay",
            },
        }
        self.client.publish(config_topic, json.dumps(payload), qos=1, retain=True)
        logger.info("Published HA discovery config to %s", config_topic)

    # -- Lifecycle ----------------------------------------------------------

    def connect(self):
        logger.info("Connecting to MQTT broker %s:%s ...", MQTT_BROKER, MQTT_PORT)
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

    def start(self):
        try:
            self.connect()
            self.client.loop_forever(retry_first_connection=True)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception:
            logger.exception("Fatal error in MQTT loop")
        finally:
            self.cleanup()

    def cleanup(self):
        try:
            if self.client.is_connected():
                self.client.publish(
                    MQTT_AVAILABILITY_TOPIC,
                    PAYLOAD_NOT_AVAILABLE,
                    qos=1,
                    retain=True,
                )
                self.client.disconnect()
            self._relay_off()
            GPIO.cleanup()
            logger.info("Cleanup complete")
        except Exception:
            logger.exception("Error during cleanup")


def _run_daemon():
    logger.info("Starting Garage Door Opener (MQTT daemon)...")
    GarageDoorController().start()


def _run_trigger(action):
    """Pulse the relay once and exit. Bypasses MQTT entirely."""
    logger.info("Triggering garage door (%s) via CLI...", action)
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(GPIO_PIN, GPIO.OUT)
    try:
        GPIO.output(GPIO_PIN, GPIO.LOW if RELAY_ACTIVE_LOW else GPIO.HIGH)
        time.sleep(RELAY_ACTIVATION_TIME)
    finally:
        GPIO.output(GPIO_PIN, GPIO.HIGH if RELAY_ACTIVE_LOW else GPIO.LOW)
        GPIO.cleanup()
    logger.info("Relay pulse complete")


def main():
    parser = argparse.ArgumentParser(
        description="Garage door opener: MQTT daemon or one-shot CLI trigger."
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "daemon",
        help="Run the MQTT daemon (default if no command is given).",
    )

    trigger_parser = subparsers.add_parser(
        "trigger",
        help="Pulse the relay once and exit (no MQTT). Useful over SSH.",
    )
    trigger_parser.add_argument(
        "action",
        nargs="?",
        default="toggle",
        choices=["open", "close", "toggle"],
        help="Action label for logging (default: toggle). The relay pulse is identical.",
    )

    args = parser.parse_args()

    if args.command == "trigger":
        _run_trigger(args.action)
    else:
        _run_daemon()


if __name__ == "__main__":
    main()
