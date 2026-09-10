# wildebeest_base

`wildebeest_base` is the safety boundary between ROS 2 and the Arduino that
drives the two L298N side channels of the four-wheel skid-steer chassis and
samples the wheel encoders, MPU6050, and front HC-SR04.
It publishes:

* `/wheel/odometry` (`nav_msgs/Odometry`) and optional `odom -> base_link` TF;
* `joint_states` for all four wheels (each side shares its aggregate encoder state);
* `imu/data_raw` (`sensor_msgs/Imu`);
* `range/front` (`sensor_msgs/Range`) and `battery_state`;
* `diagnostics` with link, watchdog, both estops, CRC, faults, and telemetry state.

It subscribes to `/cmd_vel` and the dashboard-safe `/wildebeest/estop`
(`std_msgs/Bool`), and exposes `/base/set_estop` (`std_srvs/SetBool`)
and `/base/reset_odometry` (`std_srvs/Empty`). The command watchdog transmits a
zero target after stale input.  The Arduino must implement an independent
watchdog as the final authority.

## Serial contract

Every line is ASCII:

```text
@TYPE,seq,field...*CRC16\n
```

The complete protocol-v1 frame is limited to 128 bytes including the newline.

`CRC16` is four uppercase hexadecimal digits for CRC-16/CCITT-FALSE over the
bytes between `@` and `*` (polynomial `0x1021`, initial value `0xFFFF`, no
reflection, xor-out `0x0000`).  Sequence numbers are unsigned 16-bit values.

Host commands:

```text
CMD,<seq>,<linear_mm_s>,<angular_mrad_s>
PING,<seq>
ESTOP,<seq>,<0|1>
```

Controller telemetry:

```text
ODOM,<seq>,<left_ticks>,<right_ticks>,<left_mrad_s>,<right_mrad_s>,<battery_mv>,<flags>
IMU,<seq>,<ax_mg>,<ay_mg>,<az_mg>,<gx_mdps>,<gy_mdps>,<gz_mdps>
RANGE,<seq>,<front_mm>
PONG,<seq>
```

`battery_mv` is accepted from `0..20000`; `front_mm` is accepted from
`0..2000`, matching the firmware's two-metre ultrasonic clamp.

The canonical flags are bit 0 watchdog, bit 1 physical hard stop, bit 2
software stop, bit 3 protocol fault, bit 4 IMU fault, bit 5 range timeout, and
bit 6 low battery. `BOOT,<seq>,<identity>,<version>` and
`ERR,<seq>,<code>` provide lifecycle/error feedback. Invalid CRCs, wrong field
counts, non-canonical integers, and out-of-range values are rejected. The
protocol implementation and Arduino firmware must be kept in lockstep.

## Mock mode

```bash
ros2 launch wildebeest_base base.launch.py transport:=mock
```

Mock mode uses the same encoded frames, parser, watchdog, encoder odometry,
and telemetry path as hardware.  It is a functional integration aid, not a
physics or electrical simulation.

## Stable device name

Create a udev rule using the actual UNO attributes from `udevadm info` rather
than relying on `/dev/ttyACM0`.  Example only (replace the serial value):

```udev
SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0043", \
  ATTRS{serial}=="REPLACE_ME", SYMLINK+="wildebeest-base", GROUP="dialout", MODE="0660"
```

Disconnect/reconnect recovery is automatic.  By default shutdown sends zero
velocity and a latched ESTOP before closing the port.  Clear it deliberately:

```bash
ros2 service call /base/set_estop std_srvs/srv/SetBool "{data: false}"
```

The bridge is fail-closed at startup and after every reconnect/reboot. It does
not flush the serial receive buffer and requires the exact
`BOOT,0,WILDEBEEST_BASE,1` identity/version before accepting motion. Physical
bringup remains host-latched after validation until the service above or a
false `/wildebeest/estop` message explicitly releases it. Both engaging and
releasing estop erase command freshness, so a new post-release `/cmd_vel` is
required. The mock `use_sim:=true` smoke path deliberately enables the
`release_estop_on_connect` option.

CAD nominal geometry is radius `0.033622 m`, wheel-center track `0.121843 m`,
wheelbase `0.117150 m`, and effective encoder CPR `600`. Skid-steer scrub makes
the effective track surface-dependent; measure radius and track on the built
robot before localization or autonomous operation.

Do not use software estop as the sole safety control.
