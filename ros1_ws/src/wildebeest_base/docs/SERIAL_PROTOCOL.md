# Wildebeest serial protocol v1

The Jetson-to-Arduino link is deliberately small, inspectable, and fail-safe. It is not a replacement for a physical emergency-stop circuit. Use a normally closed, hard-wired switch that removes L298N motor power.

## Framing

Every frame is one bounded ASCII line:

```text
@TYPE,seq,field...*CRC16\n
```

- `TYPE` is uppercase ASCII.
- `seq` is an unsigned 16-bit decimal counter. Wrap from 65535 to 0 is expected.
- `CRC16` is four hexadecimal digits. It is CRC-16/CCITT-FALSE (polynomial `0x1021`, initial value `0xFFFF`, no reflection, final XOR `0x0000`) over bytes strictly between `@` and `*`.
- Protocol v1 frames are at most 128 bytes including `\n`. The firmware's
  128-byte buffer therefore stores at most 127 bytes before the terminator.
  Receivers bound memory, re-synchronize on a new `@`, and discard malformed
  fields, unknown types, bad CRCs, and values outside the ranges below.
- Baud rate is 115200, 8 data bits, no parity, 1 stop bit.

Example vector:

```text
@PING,42*F43D
```

Generate authoritative vectors with `wildebeest_base.protocol.encode_frame`; the unit tests also guard the algorithm against the standard `123456789 -> 0x29B1` CRC check value.

## Host to MCU

| Frame | Fields | Accepted range/meaning |
| --- | --- | --- |
| `CMD` | `linear_mm_s,angular_mrad_s` | `[-450,450]`, `[-1800,1800]`; refreshed at 20 Hz |
| `PING` | none | MCU returns `PONG` with the same sequence |
| `ESTOP` | `0|1` | `1` latches a software stop; either transition zeroes the target and a fresh `CMD` is required |

If no valid `CMD` arrives for 300 ms, the MCU sets the watchdog flag and commands zero motor output. A CRC-valid out-of-range command is still rejected and does not refresh the watchdog.

## MCU to host

| Frame | Fields | Units |
| --- | --- | --- |
| `ODOM` | `left_ticks,right_ticks,left_mrad_s,right_mrad_s,battery_mv,flags` | signed side-aggregate encoder counts, left/right side milliradians/s, battery `0..20000` mV, bit mask |
| `IMU` | `ax_mg,ay_mg,az_mg,gx_mdps,gy_mdps,gz_mdps` | milli-g and millidegrees/s |
| `RANGE` | `front_mm` | `0..2000` mm; firmware normally clamps successful echoes to `20..2000` and omits a sample on timeout |
| `PONG` | none | response uses the `PING` sequence |
| `BOOT` | `WILDEBEEST_BASE,protocol_version` | controller identity and wire-protocol version |
| `ERR` | `TYPE|SCHEMA|RANGE` | a host command was rejected; sequence matches the command when recoverable |

Flag bits are: bit 0 watchdog, bit 1 hard stop, bit 2 software stop, bit 3 protocol error, bit 4 IMU error, bit 5 ultrasonic timeout, and bit 6 low battery. Unassigned bits must be zero in v1.

The four-wheel chassis intentionally retains one left-side and one right-side protocol channel. On ROS 1, each side's reported position and velocity are mirrored to its front and rear URDF joints. This models a mechanically coupled skid-steer side; v1 cannot diagnose or control four independent wheel encoders.

The host admits no motion until it validates the exact handshake `BOOT,0,WILDEBEEST_BASE,1`; `PONG` proves heartbeat only and never unlocks motion. BOOT/reconnect/protocol errors latch a host stop. A valid BOOT is followed by `ESTOP,1`. An operator must explicitly send `ESTOP,0`; the host then waits for an ODOM frame with both stop bits clear, discards its cached velocity again, and requires a fresh `CMD` after that confirmation.

The protocol does not carry raw GPS, camera, or LiDAR data. Those high-bandwidth devices connect directly to the Jetson and use their native ROS drivers.

## Safety and commissioning

1. Raise and restrain the robot; remove the L298N motor supply while checking logic.
2. Confirm CRC vectors and `PING/PONG` with a terminal tool.
3. Verify encoder count sign by turning each wheel forward by hand.
4. Engage the physical e-stop, then verify each motor direction at low PWM.
5. Calibrate wheel radius, separation, encoder ticks/revolution, battery divider, and controller gains.
6. Verify a cable pull stops both motors within the configured watchdog interval before floor testing.

No hardware validation is claimed by this repository.
