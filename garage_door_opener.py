#!/usr/bin/env python3
"""
Garage door opener integration for Home Assistant.
Connects via MQTT and triggers relay on Raspberry Pi GPIO.
"""

import time
import sys
import json
import logging
from threading import Thread

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
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_USERNAME,
    MQTT_PASSWORD,
    MQTT_COMMAND_TOPIC,
    MQTT_STATE_TOPIC,
    RELAY_ACTIVE_LOW,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GarageDoorController:
    def __init__(self):
        self.gpio_pin = GPIO_PIN
        self.relay_active_low = RELAY_ACTIVE_LOW
        self.activation_time = RELAY_ACTIVATION_TIME
        self.state = "idle"
        
        # Setup GPIO
        self._setup_gpio()
        
        # Setup MQTT
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
    def _setup_gpio(self):
        """Initialize GPIO pin for relay control."""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.gpio_pin, GPIO.OUT)
        self._relay_off()
        logger.info(f"GPIO {self.gpio_pin} initialized")
    
    def _relay_on(self):
        """Activate relay (energize the button contact)."""
        if self.relay_active_low:
            GPIO.output(self.gpio_pin, GPIO.LOW)
        else:
            GPIO.output(self.gpio_pin, GPIO.HIGH)
        logger.info("Relay ON")
    
    def _relay_off(self):
        """Deactivate relay."""
        if self.relay_active_low:
            GPIO.output(self.gpio_pin, GPIO.HIGH)
        else:
            GPIO.output(self.gpio_pin, GPIO.LOW)
        logger.info("Relay OFF")
    
    def trigger_door(self, action):
        """Trigger garage door action (open/close)."""
        if self.state == "triggering":
            logger.warning("Already triggering door, ignoring request")
            return
        
        self.state = "triggering"
        logger.info(f"Triggering garage door action: {action}")
        
        try:
            self._relay_on()
            time.sleep(self.activation_time)
            self._relay_off()
            
            self.state = "idle"
            self.publish_state(f"success_{action}")
            logger.info(f"Door action {action} complete")
        except Exception as e:
            logger.error(f"Error triggering door: {e}")
            self.state = "error"
            self.publish_state("error")
    
    def on_connect(self, client, userdata, flags, rc):
        """MQTT on_connect callback."""
        if rc == 0:
            logger.info(f"Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
            # Subscribe to command topic
            client.subscribe(MQTT_COMMAND_TOPIC)
            logger.info(f"Subscribed to {MQTT_COMMAND_TOPIC}")
            self.publish_state("connected")
        else:
            logger.error(f"MQTT connection failed with code {rc}")
    
    def on_message(self, client, userdata, msg):
        """MQTT on_message callback."""
        try:
            payload = msg.payload.decode('utf-8').lower()
            logger.info(f"Received message on {msg.topic}: {payload}")
            
            if payload in ["open", "close", "toggle"]:
                # Run trigger in separate thread to avoid blocking MQTT loop
                thread = Thread(target=self.trigger_door, args=(payload,))
                thread.daemon = True
                thread.start()
            else:
                logger.warning(f"Unknown command: {payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def on_disconnect(self, client, userdata, rc):
        """MQTT on_disconnect callback."""
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection (code {rc})")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def publish_state(self, state):
        """Publish current state to MQTT."""
        try:
            self.client.publish(MQTT_STATE_TOPIC, state, retain=True)
            logger.info(f"Published state: {state}")
        except Exception as e:
            logger.error(f"Error publishing state: {e}")
    
    def connect(self):
        """Connect to MQTT broker."""
        try:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            logger.info("Connecting to MQTT broker...")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            raise
    
    def start(self):
        """Start the controller (blocking call)."""
        try:
            self.connect()
            self.client.loop_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources."""
        try:
            self.client.disconnect()
            self._relay_off()
            GPIO.cleanup()
            logger.info("Cleanup complete")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    logger.info("Starting Garage Door Opener...")
    controller = GarageDoorController()
    controller.start()


if __name__ == "__main__":
    main()
