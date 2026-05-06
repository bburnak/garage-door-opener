# Garage Door Opener Architecture

This repository currently implements a split architecture:

- The Raspberry Pi is responsible for actuation.
- The ESP32-C3 is responsible for sensing.

That split is intentional for the current phase of the project. It keeps relay control simple on the Raspberry Pi while adding reliable door-state telemetry through a small Wi-Fi microcontroller.

## Current system responsibilities

| Component | Responsibility | Output |
| --- | --- | --- |
| Home Assistant | User interface, automations, MQTT integration | Commands to MQTT, entities in UI |
| MQTT broker | Message transport | Command, state, availability, and discovery topics |
| Raspberry Pi controller | Pulses relay across garage button terminals | Garage movement commands |
| ESP32-C3 sensor | Reads reed switch and reports real door position | Open or closed state |

## Data flow

### Command flow

```text
Home Assistant -> MQTT broker -> Raspberry Pi controller -> GPIO relay pulse -> Garage opener button input
```

What happens:

1. Home Assistant publishes an MQTT command such as `open`, `close`, `toggle`, or `stop`.
2. The Raspberry Pi daemon subscribes to its command topic.
3. The daemon pulses the relay for `RELAY_ACTIVATION_TIME` seconds.
4. The garage opener sees that pulse as the same event as a wall-button press.

### State flow

```text
Garage door position -> Reed switch -> ESP32-C3 -> MQTT broker -> Home Assistant
```

What happens:

1. The door moves relative to the reed switch and magnet.
2. The ESP32-C3 debounces the GPIO input.
3. The firmware publishes `open` or `closed` over MQTT.
4. Home Assistant updates the binary sensor entity based on the real switch state.

## Why the projects are separate today

The Raspberry Pi controller was built to solve the actuator problem first. That controller can publish a Home Assistant `cover` entity, but it does not read a physical sensor. It therefore reports an assumed door state based on the last command it sent.

That assumption fails in common real-world cases:

- Someone uses the wall button.
- Someone uses a car remote.
- The door is interrupted mid-travel.
- The opener and the software disagree about the starting state.

The ESP32-C3 sensor solves that reliability gap by publishing a separate sensor entity driven by physical hardware rather than inferred state.

## MQTT topic ownership

### Raspberry Pi controller

Default topic family, derived from `DEVICE_ID = garage_door_pi`:

| Topic | Purpose |
| --- | --- |
| `garage_door/garage_door_pi/set` | Command topic consumed by the Raspberry Pi |
| `garage_door/garage_door_pi/state` | Cover state published by the Raspberry Pi |
| `garage_door/garage_door_pi/availability` | Availability published by the Raspberry Pi |
| `homeassistant/cover/garage_door_pi/<unique_id>/config` | Home Assistant MQTT discovery for the cover |

### ESP32-C3 sensor

Default topic family from `src/config.h`:

| Topic | Purpose |
| --- | --- |
| `garage_door/state` | Door sensor state published by the ESP32-C3 |
| `garage_door/availability` | Availability published by the ESP32-C3 |
| `homeassistant/binary_sensor/garage_door_sensor/config` | Home Assistant MQTT discovery for the binary sensor |

## Operational model in Home Assistant

The two projects currently surface as separate Home Assistant entities:

- A `cover` entity created by the Raspberry Pi controller.
- A `binary_sensor` entity created by the ESP32-C3 sensor.

That separation is useful during development because it makes the optimistic controller behavior and the real sensor behavior visible side by side.

## Current limitations

- The Raspberry Pi cover state is optimistic, not sensor-backed.
- The ESP32-C3 sensor cannot trigger the door.
- The default MQTT topic families are adjacent but not yet unified into one logical device model.
- There is no single firmware image yet that owns both sensing and actuation.

## Target architecture

The target end state is an ESP32-based controller with two hardware responsibilities:

- Read the real door position from a sensor input.
- Drive an isolated dry-contact relay output for actuation.

The main design constraint is that actuation must remain as safe and electrically isolated as the current Raspberry Pi relay approach. MQTT and Home Assistant behavior should remain stable enough that the migration does not break existing automations unnecessarily.

## Related documents

- Main overview: [../README.md](../README.md)
- ESP32-C3 setup guide: [../esp32-c3/README.md](../esp32-c3/README.md)
- Migration plan: [ROADMAP.md](ROADMAP.md)