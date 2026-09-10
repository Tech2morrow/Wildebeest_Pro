# Serial protocol v1

The Jetson/workstation base bridge and Arduino use a small, bounded ASCII protocol. It is designed to reject malformed motion commands and recover framing after line noise. It is **not** a substitute for the hard-wired motor emergency stop.

Normative implementations are:

- firmware: `firmware/wildebeest_base/include/Protocol.h` and `src/main.cpp`;
- host reference codec: `tools/wildebeest_protocol.py`;
- ROS bridge codecs under each workspace's `wildebeest_base` package.

If those implementations disagree, stop hardware testing and resolve the contract plus cross-language vectors first.

## Physical link

| Property | Value |
|---|---|
| Transport | USB serial to Arduino Uno |
| Format | 115200 baud, 8 data bits, no parity, 1 stop bit (8-N-1) |
| Encoding | 7-bit ASCII fields and hexadecimal CRC; newline terminated |
| Flow control | None |
| Maximum frame | 128 bytes including the terminating `\n` |
| Firmware receive capacity | 128 bytes: at most 127 stored bytes before `\n`, leaving room for the internal null terminator |

Use a stable `/dev/serial/by-id/...` path or a narrowly matched udev symlink. Device enumeration names such as `/dev/ttyACM0` are not stable across reconnects.

The protocol provides integrity against accidental corruption, not authentication or encryption. Treat physical USB access and the host account as privileged control access; do not tunnel the raw port over an untrusted network.

## Frame grammar

```text
@TYPE,sequence[,field...]*CCCC\n
```

- `@` begins and re-synchronizes a frame.
- `TYPE` is the uppercase message type.
- `sequence` is a canonical unsigned decimal integer from `0` through `65535`; wrap to zero is normal.
- Fields are comma-separated canonical decimal integers unless a message says otherwise.
- `*` ends the CRC input.
- `CCCC` is exactly four hexadecimal digits for CRC-16/CCITT-FALSE over the bytes strictly between `@` and `*`.
- `\n` ends the line; receivers may ignore `\r` for CRLF interoperability.

CRC parameters:

| Parameter | Value |
|---|---:|
| Width | 16 bits |
| Polynomial | `0x1021` |
| Initial value | `0xFFFF` |
| Input/output reflection | false |
| Final XOR | `0x0000` |
| Check value for ASCII `123456789` | `0x29B1` |

Known vector:

```text
@PING,42*F43D
```

CRC letters emitted by the firmware are uppercase. Parsers may accept lowercase hex, but generated test vectors use uppercase.

## Host-to-controller messages

### `CMD`

```text
@CMD,<sequence>,<linear_mm_s>,<angular_mrad_s>*<crc>\n
```

| Field | Unit | Firmware v1 accepted range |
|---|---:|---:|
| `linear_mm_s` | mm/s | -450 to +450 |
| `angular_mrad_s` | mrad/s | -1800 to +1800 |

Positive linear velocity is forward. Positive angular velocity is counter-clockwise viewed from above, matching ROS. The controller converts body command to left/right wheel targets using its configured radius and separation.

A valid in-range `CMD` refreshes the firmware watchdog. A bad CRC, bad schema, unknown type, or out-of-range value does not. The host sends commands continuously while motion is authorized; the firmware stops motor output after 300 ms without a valid `CMD`.

Values outside the firmware limits are rejected rather than clamped. ROS-side limits should be equal or more conservative. These firmware values are initial prototype ceilings, not authorization to operate at that speed.

### `PING`

```text
@PING,<sequence>*<crc>\n
```

The controller replies immediately with `PONG` using the same sequence. A successful ping proves framing/round-trip communication, not fresh odometry or safe motor state.

### `ESTOP`

```text
@ESTOP,<sequence>,<state>*<crc>\n
```

`state=1` engages the software stop and zeros requested targets. Either state
transition invalidates the previous motion command. Opening the physical
hard-stop sense loop also engages the software latch, so releasing the physical
button cannot restart a continuously publishing host. Only after the physical
loop is healthy may `state=0` clear the software latch, and a fresh valid `CMD`
is still required for motion. On ROS bridge shutdown, the expected sequence is
zero command followed by software-stop engage, then port close.

Never use this message as the sole emergency stop. USB, Linux, a process, and the MCU can all fail.

## Controller-to-host messages

All telemetry message types share one wrapping 16-bit controller sequence counter. A gap can indicate dropped/corrupt frames, but `PONG` and `ERR` echo host sequences and therefore are not part of that telemetry sequence stream.

### `BOOT`

```text
@BOOT,0,WILDEBEEST_BASE,1*<crc>\n
```

Sent at controller startup. The final field is protocol version `1`. Receiving `BOOT` means counts and controller state may have reset. The host must invalidate stale integration state, keep motion stopped, and require deliberate recovery.

### `ODOM`

```text
@ODOM,<sequence>,<left_ticks>,<right_ticks>,<left_mrad_s>,<right_mrad_s>,<battery_mv>,<flags>*<crc>\n
```

| Field | Meaning |
|---|---|
| `left_ticks`, `right_ticks` | Signed absolute counts since the current MCU boot, using the configured ISR decode mode |
| `left_mrad_s`, `right_mrad_s` | Signed measured output-wheel angular velocities in milliradians/second |
| `battery_mv` | Filtered ADC estimate, accepted from `0` through `20000` mV; meaningful only after divider/reference calibration |
| `flags` | Unsigned status bit mask below |

Default target rate is 20 Hz. Host odometry uses the configured counts/revolution and wheel geometry. A controller reset or implausible tick jump must never become a huge pose increment.

### `IMU`

```text
@IMU,<sequence>,<ax_mg>,<ay_mg>,<az_mg>,<gx_mdps>,<gy_mdps>,<gz_mdps>*<crc>\n
```

Acceleration fields are milli-g; angular-rate fields are millidegrees/second. The host converts to SI. Default target rate is 50 Hz when the MPU6050 compile-time option is enabled and initialization succeeds. The frame carries no calibrated orientation, covariance, temperature, or sensor timestamp; the ROS publisher must represent those limitations honestly.

### `RANGE`

```text
@RANGE,<sequence>,<front_mm>*<crc>\n
```

Hosts accept `front_mm` from `0` through `2000`. Successful physical HC-SR04
measurements are clamped to `20..2000` mm and reported at a target rate of
10 Hz. On echo timeout, firmware sets the range-timeout flag and omits a new
`RANGE` sample. The host must age out the previous range rather than treating
it as current or obstacle-free. A value below the configured ROS sensor minimum
is represented conservatively as negative infinity (object too close), not as
clear space.

### `PONG`

```text
@PONG,<host_sequence>*<crc>\n
```

Echoes the triggering `PING` sequence.

### `ERR`

```text
@ERR,<host_sequence>,<code>*<crc>\n
```

Current codes are:

| Code | Meaning |
|---|---|
| `RANGE` | A `CMD` field was missing, noncanonical, or outside firmware range |
| `SCHEMA` | An `ESTOP` field/count was invalid |
| `TYPE` | The frame type was unknown or otherwise unmatched |

Frames that fail outer framing/CRC may not yield an `ERR`, because their sequence cannot be trusted. A transient protocol-error status flag is set locally.

An `ERR` frame or an `ODOM` frame carrying that protocol-error flag is a
fail-closed event. The host latches its software stop, discards command
freshness, closes the transport, and will not authorize motion until a new
connection supplies the exact supported `BOOT,0,WILDEBEEST_BASE,1` identity.

## Status flags

| Bit | Mask | Name | Effect/meaning |
|---:|---:|---|---|
| 0 | `0x0001` | command watchdog | Blocking: no recent valid `CMD` |
| 1 | `0x0002` | hard E-stop | Blocking: fail-safe A1 sense loop is open/`HIGH` (pressed, unplugged, or broken) |
| 2 | `0x0004` | software E-stop / re-arm latch | Blocking: `ESTOP,1` or a physical hard-stop event latched a deliberate re-arm requirement |
| 3 | `0x0008` | protocol error | A malformed/rejected frame was observed; currently transient |
| 4 | `0x0010` | IMU error | MPU6050 unavailable or read failed |
| 5 | `0x0020` | range timeout | HC-SR04 acquisition timed out |
| 6 | `0x0040` | low battery | ADC estimate is at/below the configured warning threshold |

Bits 0–2 prevent motor motion. Low-voltage motor stopping is compile-time
configurable and is disabled by default until the divider and pack thresholds
are commissioned. If enabled, it uses `BATTERY_STOP_MV`, not the warning flag,
and releases only after `BATTERY_STOP_HYSTERESIS_MV` of recovery. The initial
unverified values are 6600 mV and 150 mV respectively. Either cutoff transition
invalidates command freshness. The electrical BMS/protection remains
authoritative.

Unknown flag bits must be preserved in diagnostics and treated conservatively. They must not be silently masked as healthy.

## Receiver requirements

A compliant receiver:

1. bounds memory use and frame length;
2. drops bytes until `@`, and re-synchronizes if a new `@` appears;
3. verifies the full CRC before parsing fields;
4. rejects unknown type, wrong field count, whitespace/noncanonical integers, overflow, and out-of-range fields;
5. never refreshes the motion watchdog for an invalid message;
6. tracks invalid/dropped frames in diagnostics;
7. detects telemetry gaps, staleness, reset/`BOOT`, and reconnect;
8. converts units only after validation;
9. sends zero and software E-stop during orderly shutdown where the link remains available.

## Compatibility and change control

Protocol v1 is deliberately not self-describing beyond the `BOOT` version. Adding an optional field to an existing message breaks strict parsers. To change a schema or unit:

- increment the protocol version;
- update firmware, tools, both ROS bridges, mock controller, tests, and this page atomically;
- keep golden vectors for every message and invalid boundary;
- verify old/new mismatch fails stopped rather than partially working;
- record the firmware protocol version in diagnostics and bag metadata.

## Bench verification

With motor power physically removed:

```bash
# Pure codec/mock tests; no serial hardware required
python3 -m unittest discover -s tools/tests -v

# Inspect the deterministic demo stream
python3 tools/mock_mcu.py --demo --seconds 2
```

Then use the actual MCU to prove CRC rejection, range rejection, sequence wrap, reset handling, cable removal, 300 ms watchdog, hard/soft stop priority, and recovery. Capture raw serial logs without secrets and link them to the acceptance record.
