# Wildebeest base firmware

The Arduino Uno is the deterministic safety and motion layer. It closes the
wheel-speed loop, counts encoders, samples the MPU-6050 and HC-SR04, monitors
battery voltage, and stops the motors if valid commands disappear for 300 ms.

## Build and upload

```bash
python3 -m pip install --user platformio
pio run -d firmware/wildebeest_base
pio test -d firmware/wildebeest_base -e native
pio run -d firmware/wildebeest_base -t upload
pio device monitor -b 115200
```

An isolated Arduino CLI build is also supported from the repository root:

```bash
arduino-cli core install arduino:avr@1.8.8 --config-file firmware/arduino-cli.yaml
arduino-cli compile --config-file firmware/arduino-cli.yaml \
  --fqbn arduino:avr:uno firmware/wildebeest_base
```

The project-local CLI configuration keeps downloaded board data under the
ignored `.tooling/` directory instead of modifying the source tree.

Disconnect motor power and raise the chassis before the first upload. Confirm
that both wheel sides report the correct sign by turning the four wheels by
hand. Then
test with a current-limited supply and the physical E-stop within reach.

All wiring defaults and tuning constants live in `include/Config.h`. Wheel
radius, wheel separation, effective encoder counts per revolution, motor
polarity, PID values, ADC reference, voltage divider ratio, and battery limits
must be commissioned on the assembled robot.

The optional low-voltage motor cutoff is disabled by default. If explicitly
enabled after battery-divider and pack validation, it latches at or below
`BATTERY_STOP_MV` (`6600 mV` initially) and releases only at
`BATTERY_STOP_MV + BATTERY_STOP_HYSTERESIS_MV` (`6750 mV` initially). Either
transition clears the stored target and command timestamp, so recovery needs a
fresh command. `BATTERY_WARNING_MV` controls diagnostics only and does not set
the motor-stop threshold.

The host protocol is documented in `docs/reference/serial-protocol.md`. Frames
with bad CRC, unknown types, extra fields, or commands beyond configured limits
are rejected. A physical normally-closed E-stop loop on A1 always overrides a
software clear request. Opening that loop also latches the software stop;
after releasing the physical E-stop, deliberately send `ESTOP,0` and then a
fresh zero command before authorizing motion.

> The L298N is an older, inefficient bipolar driver. It is retained because it
> appears in the concept hardware. For a field robot, use a modern current-rated
> MOSFET driver with current sensing and hardware fault output.
