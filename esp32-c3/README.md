# ESP32-C3 Garage Door Status Sensor

This folder contains the sensing half of the current garage-door system. It runs on an ESP32-C3, reads a magnetic reed switch on GPIO21, and publishes the real door state to MQTT for Home Assistant.

Project context:

- The Raspberry Pi project in the repository handles actuation through a relay.
- This ESP32-C3 project handles physical state sensing.
- They can run independently, but they are designed to complement each other.
- The long-term goal is to move both responsibilities onto an ESP32-based controller.

For the system overview, see [../README.md](../README.md). For the architecture split, see [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md). For the migration plan, see [../docs/ROADMAP.md](../docs/ROADMAP.md).

## Scope

Current firmware behavior:

- Read a reed switch on GPIO21 using the internal pull-up resistor
- Debounce signal changes
- Connect to Wi-Fi
- Publish `open` or `closed` state to MQTT
- Publish Home Assistant MQTT discovery for a binary sensor
- Emit serial debug output for troubleshooting

## 1. Hardware wiring

Reed switch connections:

- Reed leg 1 -> `GPIO21`
- Reed leg 2 -> `GND`

Why this works:

- Firmware enables `INPUT_PULLUP` on GPIO21
- Switch closed -> pin is pulled to GND (`LOW`)
- Switch open -> pull-up keeps pin at `HIGH`

## 2. Windows USB stability notes

During setup, USB reconnect loops were observed. The commands below disabled USB selective suspend and improved stability:

```powershell
powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /setdcvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0
powercfg /setactive SCHEME_CURRENT
```

Verify:

```powershell
powercfg /query SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226
```

Expected: AC and DC indexes both `0x00000000` (Disabled).

## 3. Confirm ESP32-C3 COM port

```powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Name, PNPDeviceID
```

Expected:

- `USB\VID_303A&PID_1001...`
- COM port such as `COM3`

## 4. Configure Wi-Fi and MQTT credentials

1. Open `src/config.h`
2. Fill in your values:

```c
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define MQTT_BROKER "mqtt-broker.local"
#define MQTT_USERNAME "your_mqtt_username"
#define MQTT_PASSWORD "your_mqtt_password"
```

**MQTT Broker:**
- If using Home Assistant with MQTT: Use the IP/hostname of your Home Assistant or MQTT broker
- Port default: `1883`
- Authentication: Leave empty strings if not using username/password

## 5. Build and flash firmware (PlatformIO)

From repository root:

```powershell
cd esp32-c3
```

Activate venv if needed:

```powershell
..\..\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m platformio run
```

Upload (replace COM3 if needed):

```powershell
python -m platformio run --target upload --upload-port COM3
```

## 6. Monitor serial output

Use the robust serial monitor script:

```powershell
@'
import serial
import sys
import time

port = "COM3"
baud = 115200
print(f"Watching {port} at {baud}")

while True:
    try:
        ser = serial.Serial(port, baud, timeout=0.2)
        ser.dtr = False
        ser.rts = False
        print("CONNECTED")

        while True:
            try:
                chunk = ser.read(ser.in_waiting or 1)
                if chunk:
                    sys.stdout.write(chunk.decode("utf-8", errors="replace"))
                    sys.stdout.flush()
            except Exception as ex:
                print(f"\nRX_ERR {ex}")
                break

        ser.close()
    except Exception as ex:
        print(f"OPEN_ERR {ex}")

    time.sleep(0.7)
'@ | ..\..\.venv\Scripts\python.exe -
```

## 7. Expected serial output

On boot (with Wi-Fi and MQTT):

```
ESP32-C3 garage door sensor (with MQTT)
boot raw=HIGH door=open
Connecting to WiFi: YOUR_SSID
.....
WiFi connected. IP: 192.168.1.50
MQTT connecting to 192.168.1.100:1883
MQTT connected
HA discovery published
Published initial state: open
```

When door state changes:

```
change raw=LOW door=closed
MQTT published: closed
```

Periodic heartbeat:

```
[heartbeat message every 30 seconds if no state change]
```

**If Wi-Fi/MQTT fails:**

- Check `src/config.h` credentials (SSID, password, broker IP)
- Verify MQTT broker is running and reachable
- Serial output will show `WiFi failed` or `MQTT failed`
- Device will retry automatically

## 8. Home Assistant integration

Once the ESP32 connects to MQTT:

1. Home Assistant will auto-discover the device under **Settings → Devices & Services → MQTT → Devices**
2. Entity appears as `binary_sensor.garage_door_sensor`
3. Device class: `door` (renders open/close icons)
4. Payload: `open` or `closed` (configurable via `src/config.h`)

If auto-discovery does not appear:

- Verify the MQTT broker is correctly connected to Home Assistant
- Check Home Assistant MQTT integration is enabled
- Restart Home Assistant or manually publish state to trigger discovery

## 9. MQTT Topics

| Direction | Topic | Payload |
| --- | --- | --- |
| ESP → MQTT | `garage_door/state` | `open` or `closed` |
| ESP → MQTT | `garage_door/availability` | `online` or `offline` |
| ESP → MQTT | `homeassistant/binary_sensor/garage_door_sensor/config` | HA Discovery JSON |

## 10. Customization

Edit `src/config.h` to:

- Change reed switch logic: `DOOR_CLOSED_WHEN_SWITCH_CLOSED`
- Change MQTT topics: `MQTT_TOPIC_*`
- Change pin: `REED_PIN`
- Change debounce: `DEBOUNCE_MS`
- Change heartbeat interval: `MQTT_HEARTBEAT_INTERVAL_MS`

## 11. Files in this folder

- `platformio.ini` - Build and upload config
- `src/main.cpp` - Sensor + WiFi + MQTT firmware
- `src/config.h` - Configuration template (edit with your credentials)

## 12. Relationship to the Raspberry Pi controller

This firmware does not trigger the door opener. It only reports the sensor state.

In the current overall system:

- The Raspberry Pi publishes a Home Assistant `cover` entity for door control.
- This ESP32-C3 publishes a Home Assistant `binary_sensor` entity for real door status.
- Running both together gives you remote control plus sensor truth.

The planned next step is not tighter coupling to the Raspberry Pi. The planned direction is to replace the Raspberry Pi controller with an ESP32-based controller once relay hardware and firmware parity are proven. See [../docs/ROADMAP.md](../docs/ROADMAP.md).

## 13. Validation record (2026-05-05)

Validated on Windows with ESP32-C3 connected over USB.

Successful checks:
1. Device detected as `USB\VID_303A&PID_1001` on `COM3`
2. Serial output confirmed (reed switch + boot logs)
3. Magnet sensitivity verified (works at useful distance with proper orientation)
4. Build succeeds with WiFi + MQTT libraries

Reproducible build sequence:

```powershell
cd esp32-c3
python -m platformio run --target upload --upload-port COM3
```
