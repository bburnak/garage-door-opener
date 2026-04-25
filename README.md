# Garage Door Opener — Home Assistant Integration

A small Python application that runs on a Raspberry Pi and lets you trigger a garage door opener from Home Assistant via MQTT. The Pi drives a relay whose dry contacts are wired across the existing remote/wall-button pads, so a command from Home Assistant simulates a single button press.

```
Home Assistant  →  MQTT broker  →  Raspberry Pi  →  GPIO17  →  Relay (COM/NO)  →  Button pads
```

## Hardware

### Wiring

| Raspberry Pi              | Relay module |
| ------------------------- | ------------ |
| Pin 1 (3.3V)              | VCC          |
| Pin 6 (GND)               | GND          |
| Pin 11 (GPIO17)           | IN           |

| Relay contact side | Connects to                          |
| ------------------ | ------------------------------------ |
| COM                | Garage button wire A                 |
| NO                 | Garage button wire B                 |
| NC                 | (unused)                             |

```
Raspberry Pi                          Relay module
---------------                       ----------------------
Pin 1  (3.3V)   --------------------> VCC
Pin 6  (GND)    --------------------> GND
Pin 11 (GPIO17) --------------------> IN

                                      COM ----- Remote button pad 1
                                      NO  ----- Remote button pad 2
                                      NC  ----- (not used)
```

### Notes

- Use a **3.3V-compatible** relay module (or one whose `IN` accepts 3.3V logic).
- The relay must act as a **dry contact** — never feed Pi voltage into the button circuit.
- The application energizes the relay for ~0.3s, mimicking one button tap.
- Many relay boards are **active-LOW**; if yours is, set `RELAY_ACTIVE_LOW = True` in `config.py`.

## Software setup

### 1. Clone

```bash
git clone https://github.com/bburnak/garage-door-opener.git
cd garage-door-opener
```

### 2. Install dependencies

```bash
sudo apt-get update
sudo apt-get install -y python3-pip
pip3 install -r requirements.txt
```

### 3. Configure

```bash
cp config.example.py config.py
```

Edit `config.py`:

- `MQTT_BROKER` — IP/hostname of your Home Assistant or MQTT broker
- `MQTT_USERNAME` / `MQTT_PASSWORD` — MQTT credentials
- `GPIO_PIN` — defaults to `17` (physical pin 11)
- `RELAY_ACTIVE_LOW` — flip if the relay triggers on LOW

`config.py` is gitignored so credentials stay local.

### 4. Run

Run the MQTT daemon (this is what Home Assistant talks to):

```bash
python3 garage_door_opener.py
# equivalent to:
python3 garage_door_opener.py daemon
```

You should see the controller initialize the GPIO pin, connect to MQTT, and subscribe to the command topic.

## Manual trigger over SSH (no MQTT)

If you just want to pulse the relay directly — for example from an SSH session, a cron job, or while the MQTT daemon isn't running — use the `trigger` subcommand:

```bash
python3 garage_door_opener.py trigger
# or, with an explicit action label:
python3 garage_door_opener.py trigger open
python3 garage_door_opener.py trigger close
python3 garage_door_opener.py trigger toggle
```

This pulses the relay once for `RELAY_ACTIVATION_TIME` seconds and exits. No MQTT broker is contacted.

The action argument (`open` / `close` / `toggle`) is purely a label for logging — the relay pulse itself is identical, just like pressing the wall button.

> **Note:** Don't run `trigger` while the MQTT daemon (or systemd service) is also running — both will fight for the GPIO pin. Stop the service first (`sudo systemctl stop garage-door-opener`) or just use MQTT.

## MQTT topics

| Direction       | Topic                            | Payloads                                       |
| --------------- | -------------------------------- | ---------------------------------------------- |
| HA → Pi (cmd)   | `homeassistant/garage/command`   | `open`, `close`, `toggle`                      |
| Pi → HA (state) | `homeassistant/garage/state`     | `connected`, `success_open`, `success_close`, `error` |

## Home Assistant configuration

Minimal `configuration.yaml` snippet:

```yaml
mqtt:
  cover:
    - name: Garage Door
      command_topic: homeassistant/garage/command
      state_topic: homeassistant/garage/state
      payload_open: open
      payload_close: close
      payload_stop: toggle
```

## Run as a service (optional)

Create `/etc/systemd/system/garage-door-opener.service`:

```ini
[Unit]
Description=Garage Door Opener
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/garage-door-opener
ExecStart=/usr/bin/python3 /home/pi/garage-door-opener/garage_door_opener.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now garage-door-opener
sudo systemctl status garage-door-opener
journalctl -u garage-door-opener -f
```

## Troubleshooting

- **Relay never clicks** — toggle `RELAY_ACTIVE_LOW` in `config.py`; verify `GPIO_PIN` matches your wiring.
- **MQTT connection refused** — confirm broker IP, credentials, and that port 1883 is reachable. Test with `mosquitto_sub -h <broker> -u <user> -P <pass> -t 'homeassistant/garage/#' -v`.
- **Door doesn't move** — meter the relay COM/NO contacts while triggering; confirm the relay actually closes across your soldered button wires.

## Project layout

```
.
├── garage_door_opener.py   # Main application (MQTT client + GPIO/relay control)
├── config.example.py       # Template — copy to config.py and fill in
├── config.py               # Local config (gitignored)
├── requirements.txt        # paho-mqtt, RPi.GPIO
├── .gitignore
└── README.md
```

## Safety

- Always use the relay as a dry contact across the existing button wires.
- Never connect Pi 3.3V/5V into the garage button circuit directly.
- Keep the original wall button or remote available as a manual override.
- Test with the door track clear before automating.

## License

MIT
