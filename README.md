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

### 2. Create a virtual environment

On Raspberry Pi OS (Bookworm and newer), system-wide `pip install` is blocked by [PEP 668](https://peps.python.org/pep-0668/), so a venv is required:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip
python3 -m venv .venv
source .venv/bin/activate
```

Your shell prompt should now show `(.venv)`. To leave the venv later, run `deactivate`.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `RPi.GPIO` only installs on the Raspberry Pi itself. On other platforms, the install will fail — that's expected.

### 4. Configure

```bash
cp config.example.py config.py
```

Edit `config.py`:

- `MQTT_BROKER` — IP/hostname of your Home Assistant or MQTT broker
- `MQTT_USERNAME` / `MQTT_PASSWORD` — MQTT credentials
- `GPIO_PIN` — defaults to `17` (physical pin 11)
- `RELAY_ACTIVE_LOW` — flip if the relay triggers on LOW

`config.py` is gitignored so credentials stay local.

### 5. Run

Run the MQTT daemon (this is what Home Assistant talks to):

```bash
python garage_door_opener.py
# equivalent to:
python garage_door_opener.py daemon
```

You should see the controller initialize the GPIO pin, connect to MQTT, and subscribe to the command topic.

## Manual trigger over SSH (no MQTT)

If you just want to pulse the relay directly — for example from an SSH session, a cron job, or while the MQTT daemon isn't running — use the `trigger` subcommand:

```bash
cd ~/Documents/garage-door-opener
source .venv/bin/activate
python garage_door_opener.py trigger
# or, with an explicit action label:
python garage_door_opener.py trigger open
python garage_door_opener.py trigger close
python garage_door_opener.py trigger toggle
```

If you don't want to activate the venv every time, call its Python directly:

```bash
~/Documents/garage-door-opener/.venv/bin/python ~/Documents/garage-door-opener/garage_door_opener.py trigger
```

This pulses the relay once for `RELAY_ACTIVATION_TIME` seconds and exits. No MQTT broker is contacted.

The action argument (`open` / `close` / `toggle`) is purely a label for logging — the relay pulse itself is identical, just like pressing the wall button.

> **Note:** Don't run `trigger` while the MQTT daemon (or systemd service) is also running — both will fight for the GPIO pin. Stop the service first (`sudo systemctl stop garage-door-opener`) or just use MQTT.

## MQTT topics

Topics are derived from `DEVICE_ID` in `config.py` (default: `garage_door_pi`):

| Direction       | Topic                                                  | Payloads                                              |
| --------------- | ------------------------------------------------------ | ----------------------------------------------------- |
| HA → Pi (cmd)   | `garage_door/garage_door_pi/set`                       | `open`, `close`, `toggle`, `stop`                     |
| Pi → HA (state) | `garage_door/garage_door_pi/state`                     | `open`, `closed`, `opening`, `closing`                |
| Pi → HA (avail) | `garage_door/garage_door_pi/availability`              | `online` / `offline` (auto + LWT)                     |
| Pi → HA (disc.) | `homeassistant/cover/garage_door_pi/<uid>/config`      | JSON discovery payload (published once on connect)    |

## Home Assistant configuration

### 1. Create an MQTT user for the Pi

In Home Assistant: **Settings → People → Users → Add user**, e.g. username `garage_pi` with a strong password. Tick **Can only log in from the local network**. (You can also reuse an existing MQTT user if you have one.)

Put those credentials in `config.py` on the Pi:

```python
MQTT_BROKER   = "homeassistant.local"
MQTT_USERNAME = "garage_pi"
MQTT_PASSWORD = "<your-password>"
```

### 2. That's it — the entity auto-appears

When you start the daemon, it publishes an [MQTT discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery) payload. Home Assistant creates the entity automatically:

- Entity: `cover.garage_door_pi`
- Friendly name: **Garage Door**
- Device class: `garage` (renders open/close icons in the UI)
- Reports `opening` → `open` (and `closing` → `closed`) using `TRAVEL_TIME` from `config.py`
- Goes **unavailable** automatically if the Pi disconnects (LWT)

No `configuration.yaml` edits are needed. You can verify under **Settings → Devices & services → MQTT → Devices**.

### 3. Tune for your door

In `config.py`:

- `TRAVEL_TIME` — seconds it takes to fully open/close (default 15)
- `INITIAL_STATE` — `"closed"` (default) or `"open"` for the assumed state on first start
- `RELAY_ACTIVATION_TIME` — button press duration (default 0.3s)

> **Note on state accuracy:** Without a real position sensor, the daemon *assumes* the door toggles between open/closed on each press. If someone uses the physical wall button or external remote, HA's state can drift. To fix this properly, add a magnetic reed switch to GPIO and report the real state — not implemented in this version.

## Run as a service (optional)

Create `/etc/systemd/system/garage-door-opener.service`:

```ini
[Unit]
Description=Garage Door Opener
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=baris
WorkingDirectory=/home/baris/Documents/garage-door-opener
ExecStart=/home/baris/Documents/garage-door-opener/.venv/bin/python /home/baris/Documents/garage-door-opener/garage_door_opener.py
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
├── .venv/                  # Python virtual environment (gitignored)
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
