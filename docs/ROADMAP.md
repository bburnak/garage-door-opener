# ESP32 Migration Roadmap

The long-term goal of this project is to replace the Raspberry Pi relay controller with an ESP32-based controller that can both sense and actuate the garage door.

This roadmap assumes that MQTT and Home Assistant remain the primary integration points throughout the migration.

## Phase 1: Stabilize the current split design

Goal:

- Keep the Raspberry Pi controller usable for actuation.
- Keep the ESP32-C3 sensor usable for accurate state reporting.
- Document the system clearly enough that both parts can be reproduced and maintained.

Exit criteria:

- Root documentation explains the two-project architecture.
- The sensor and controller can be deployed independently.
- State accuracy problems are explicitly documented rather than hidden.

## Phase 2: Harden the ESP32 sensor path

Goal:

- Make the sensor firmware reliable enough to serve as the authoritative door-state source.

Work items:

- Validate reed-switch placement and polarity.
- Confirm reconnect behavior for Wi-Fi and MQTT loss.
- Keep Home Assistant discovery stable.
- Add better troubleshooting notes for field deployment.

Exit criteria:

- The ESP32-C3 sensor reports stable open and closed transitions over long runtimes.
- Availability and reconnect behavior are predictable.

## Phase 3: Prototype ESP32 actuation hardware

Goal:

- Prove that an ESP32 can safely drive the opener through an isolated relay path.

Work items:

- Select a relay or opto-isolated driver suitable for ESP32 GPIO.
- Preserve dry-contact behavior across the opener input.
- Define safe boot-state behavior so the relay never pulses unexpectedly at startup.
- Validate power, grounding, and enclosure constraints.

Exit criteria:

- The ESP32 can pulse the opener safely and repeatably without false triggers.
- Boot and reset behavior are verified.

## Phase 4: Build unified ESP32 firmware

Goal:

- Merge sensing and actuation into one firmware target.

Work items:

- Add relay control logic to the ESP32 project.
- Keep sensor input and relay output independent in code.
- Preserve debouncing and reliable MQTT reconnect behavior.
- Decide whether command and state topics remain backward compatible or move to a new device model.

Exit criteria:

- One ESP32 device can publish real state and accept door commands.
- Relay timing and sensor reporting can operate together without race conditions.

## Phase 5: Home Assistant and MQTT migration

Goal:

- Move from the Raspberry Pi entity model to the unified ESP32 model without breaking users unnecessarily.

Work items:

- Define the Home Assistant entity strategy.
- Preserve or intentionally map existing MQTT topics.
- Decide how to expose both cover control and real position truth.
- Test automations against the new entity layout.

Exit criteria:

- Home Assistant can control the door and show accurate state from the ESP32-only design.
- Existing automations have a documented migration path.

## Phase 6: Retire the Raspberry Pi path

Goal:

- Remove the Raspberry Pi from the normal deployment once the ESP32 replacement is proven.

Work items:

- Update docs so ESP32-only becomes the primary path.
- Keep the Raspberry Pi controller documented as legacy or archive it.
- Remove duplicated deployment guidance that no longer applies.

Exit criteria:

- The ESP32-only architecture is the recommended deployment.
- The Raspberry Pi controller is either deprecated cleanly or retained only as a legacy reference.

## Decision principles

- Safety wins over convenience.
- Real sensor truth wins over optimistic state reporting.
- MQTT and Home Assistant compatibility should be preserved when practical.
- Migration should be incremental rather than a full rewrite.

## Related documents

- System overview: [../README.md](../README.md)
- Current architecture: [ARCHITECTURE.md](ARCHITECTURE.md)
- ESP32 sensor implementation guide: [../esp32-c3/README.md](../esp32-c3/README.md)