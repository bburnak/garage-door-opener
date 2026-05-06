# Garage Door Opener System

This repository currently contains two separate but complementary garage-door projects:

1. A Raspberry Pi relay controller that acts like a button press when Home Assistant sends an MQTT command.
2. An ESP32-C3 reed-switch sensor that reports the real door state over Wi-Fi and MQTT.

They are designed to work together, but they can also be deployed independently. Today the Raspberry Pi handles actuation and the ESP32-C3 handles sensing. The long-term direction is to replace the Raspberry Pi with an ESP32-based controller so one microcontroller can own both control and state reporting.

Detailed design notes live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). The migration plan lives in [docs/ROADMAP.md](docs/ROADMAP.md).

## Project scope

Current scope:

| Component | Purpose | Works standalone | Current limitation |
| --- | --- | --- | --- |
| Raspberry Pi controller | Pulses a relay across the garage opener button terminals | Yes | It only knows an assumed door state unless a separate sensor is added |
| ESP32-C3 sensor | Reads a magnetic reed switch and publishes the real door state | Yes | It reports state only; it does not actuate the opener |

If you only want remote opening and closing, the Raspberry Pi path is enough. If you want accurate state reporting in Home Assistant, add the ESP32-C3 sensor. If you want both safe actuation and accurate status, run both together.

## Architecture at a glance

Current command path:

```text
Home Assistant -> MQTT broker -> Raspberry Pi -> GPIO17 -> Relay -> Garage button terminals
```

Current state path:

```text
Garage door position -> Reed switch -> ESP32-C3 -> Wi-Fi -> MQTT broker -> Home Assistant
```

Why the system is split today:

- The Raspberry Pi project was built first to solve actuation.
- Its software can only report an assumed state based on the last command it sent.
- The ESP32-C3 project was added to provide sensor truth through a separate MQTT-connected device.
- This keeps the actuator path simple while removing the main reliability gap in status reporting.

## Prerequisites

- Home Assistant with the MQTT integration enabled, or another MQTT broker that your automations can reach.
- A reachable local network for the Raspberry Pi and the ESP32-C3.
- Python 3 on the Raspberry Pi, with permission to access GPIO.
- PlatformIO for building and flashing the ESP32-C3 firmware.
- A garage opener that can be safely triggered by shorting the same dry-contact input used by the wall button or remote button pads.

## Hardware requirements

### Raspberry Pi controller

| Item | Notes |
| --- | --- |
| Raspberry Pi | Any model that can run Python and expose GPIO |
| Relay module | Must be 3.3V logic compatible and used as a dry contact |
| Jumper wires | For Pi-to-relay connections |
| Access to opener button terminals | The relay connects across the existing low-voltage trigger pads |

Controller wiring:

| Raspberry Pi | Relay module |
| --- | --- |
| Pin 1 (3.3V) | VCC |
| Pin 6 (GND) | GND |
| Pin 11 (GPIO17) | IN |

| Relay contact side | Connects to |
| --- | --- |
| COM | Garage button wire A |
| NO | Garage button wire B |
| NC | Unused |

### ESP32-C3 status sensor

| Item | Notes |
| --- | --- |
| ESP32-C3 board | Wi-Fi-capable microcontroller for the reed switch sensor |
| Magnetic reed switch | Detects open or closed door position |
| Magnet | Mounted so the switch reliably changes state with the door |
| USB cable | For flashing and serial debugging |

Sensor wiring:

| Reed switch lead | ESP32-C3 |
| --- | --- |
| Lead 1 | GPIO21 |
| Lead 2 | GND |

The firmware uses the ESP32-C3 internal pull-up, so no external resistor is required for the default design.

## Repository layout

```text
.
├── docs/
│   ├── ARCHITECTURE.md
│   └── ROADMAP.md
├── esp32-c3/
│   ├── README.md
│   ├── platformio.ini
│   └── src/
├── config.example.py
├── config.py
├── garage_door_opener.py
├── requirements.txt
└── README.md
```

## Start here

Choose the path that matches your current goal:

| Goal | Start here |
| --- | --- |
| Trigger the garage door from Home Assistant | Raspberry Pi controller setup below |
| Add a real open or closed sensor | [esp32-c3/README.md](esp32-c3/README.md) |
| Understand how both pieces fit together | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Follow the plan to move to an ESP32-only design | [docs/ROADMAP.md](docs/ROADMAP.md) |

## Raspberry Pi controller setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd garage-door-opener
```

### 2. Create a virtual environment

On Raspberry Pi OS Bookworm and newer, install dependencies inside a virtual environment:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

`RPi.GPIO` installs only on a Raspberry Pi. That is expected.

### 4. Configure the controller

```bash
cp config.example.py config.py
```

Edit `config.py` and set:

- `MQTT_BROKER`
- `MQTT_USERNAME`
- `MQTT_PASSWORD`
- `GPIO_PIN` if you are not using GPIO17
- `RELAY_ACTIVE_LOW` if your relay energizes on a low signal
- `TRAVEL_TIME` so Home Assistant transitions match your real door timing

`config.py` is gitignored so credentials stay local.

### 5. Run the MQTT daemon

```bash
python garage_door_opener.py
```

This starts the controller in daemon mode, publishes Home Assistant MQTT discovery, and listens for commands on the configured command topic.

### 6. Optional manual trigger mode

If you want to pulse the relay directly without MQTT:

```bash
python garage_door_opener.py trigger
python garage_door_opener.py trigger open
python garage_door_opener.py trigger close
python garage_door_opener.py trigger toggle
```

The label changes logging and reported intent, but the relay pulse is always the same physical action.

Do not run `trigger` while the daemon or systemd service is already using the GPIO pin.

### 7. Optional systemd service

Example unit file:

```ini
[Unit]
Description=Garage Door Opener
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=garage
WorkingDirectory=/home/garage/garage-door-opener
ExecStart=/home/garage/garage-door-opener/.venv/bin/python /home/garage/garage-door-opener/garage_door_opener.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable it with:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now garage-door-opener
sudo systemctl status garage-door-opener
journalctl -u garage-door-opener -f
```

## MQTT and Home Assistant behavior

### Raspberry Pi controller topics

These topics are derived from `DEVICE_ID` in `config.py`. With the default `garage_door_pi` value:

| Direction | Topic | Payloads |
| --- | --- | --- |
| Home Assistant to Pi | `garage_door/garage_door_pi/set` | `open`, `close`, `toggle`, `stop` |
| Pi to Home Assistant | `garage_door/garage_door_pi/state` | `open`, `closed`, `opening`, `closing` |
| Pi to Home Assistant | `garage_door/garage_door_pi/availability` | `online`, `offline` |
| Pi to Home Assistant | `homeassistant/cover/garage_door_pi/<unique_id>/config` | MQTT discovery JSON |

The Raspberry Pi publishes a Home Assistant `cover` entity automatically. Without a real sensor, that entity uses assumed state based on the last command it sent.

### ESP32-C3 sensor topics

By default the ESP32-C3 firmware publishes:

| Direction | Topic | Payloads |
| --- | --- | --- |
| ESP32-C3 to Home Assistant | `garage_door/state` | `open`, `closed` |
| ESP32-C3 to Home Assistant | `garage_door/availability` | `online`, `offline` |
| ESP32-C3 to Home Assistant | `homeassistant/binary_sensor/garage_door_sensor/config` | MQTT discovery JSON |

That device appears in Home Assistant as a `binary_sensor` and provides the actual sensor truth.

## ESP32-C3 sensor setup

The ESP32-C3 setup, flash workflow, Windows USB notes, and serial validation steps live in [esp32-c3/README.md](esp32-c3/README.md).

## Future direction

The target architecture is an ESP32-based controller that can do both of the following on one device:

- Read the real garage door position from a sensor.
- Safely actuate the opener through an isolated relay output.

That would remove the Raspberry Pi from the deployment while keeping MQTT and Home Assistant integration intact. The staged plan is documented in [docs/ROADMAP.md](docs/ROADMAP.md).

## Safety

- Use the relay only as a dry contact across the existing garage-button wires.
- Never inject Raspberry Pi or ESP32 supply voltage into the opener button circuit.
- Keep a physical wall button or remote available as a manual override.
- Test automations only when the door path is clear.
- If your opener has safety beam, lockout, or wall-console requirements, preserve them exactly.

## License

MIT
