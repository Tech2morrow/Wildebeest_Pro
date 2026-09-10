# Arduino Uno wiring reference

This mirrors the repository-root firmware source of truth in `firmware/wildebeest_base/include/Config.h` and the canonical design in `docs/hardware/wiring.md`. Check both files, the actual PCB, and every component datasheet before applying power; do not treat this installed package copy as authoritative.

| Function | Uno pin | Notes |
| --- | --- | --- |
| Left encoder A / B | D2 / D4 | A uses interrupt 0; inputs use pull-ups |
| Right encoder A / B | D3 / D12 | A uses interrupt 1; inputs use pull-ups |
| L298N ENA / IN1 / IN2 | D5 / D7 / D8 | D5 is PWM; remove ENA jumper |
| L298N ENB / IN3 / IN4 | D6 / D9 / D10 | D6 is PWM; remove ENB jumper |
| HC-SR04 trigger / echo | D11 / A0 | Echo is safe at Uno 5 V, never route it directly to Jetson GPIO |
| Normally closed hard-stop auxiliary loop | A1 | Healthy/released is `LOW`; pressed, unplugged, or broken wire opens the loop and reads `HIGH` through `INPUT_PULLUP` |
| Battery divider output | A2 | 100 kOhm / 47 kOhm default ratio is 3.1277; calibrate and keep A2 at or below 5 V |
| MPU6050 SDA / SCL | A4 / A5 | I2C address `0x68`; confirm module voltage/regulator design |
| Jetson link | USB serial | D0/D1 remain reserved for the USB UART |

The chassis has four driven wheels, but protocol v1 and this Uno pin budget expose one motor command and one effective encoder count per side. Both left motors and both right motors therefore behave as coupled skid-steer sides. Confirm the L298N channel, wiring, connector, fuse, and thermal/current ratings before pairing motors; an L298N may be unsuitable for the measured stall current. If all four encoders must be observed independently, revise the electronics and introduce a versioned protocol rather than silently combining pulses.

The A1 auxiliary contact reports state only. A mechanically linked, normally closed main contact **must independently interrupt motor energy**; never route motor current through A1 or Arduino ground traces. The NEO-6M GPS is expected on a Jetson USB/UART adapter, the 2D LiDAR on USB, and the IMX219 on the Jetson CSI connector. Use a bidirectional level shifter wherever a 5 V signal could reach the Jetson's 3.3 V pins. Join logic grounds, keep motor current out of logic-ground paths, add bulk capacitance at the L298N, and power motors separately from the Jetson regulator.

The included udev rule matches an example Arduino VID/PID and should be narrowed with the board serial number on a multi-robot system.
