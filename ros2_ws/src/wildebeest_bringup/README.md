# wildebeest_bringup

The primary launch starts the description, command multiplexer, serial/mock
base, local EKF, and any explicitly enabled Jetson-connected sensors:

```bash
ros2 launch wildebeest_bringup robot.launch.py use_sim:=true
ros2 launch wildebeest_bringup robot.launch.py \
  transport:=serial serial_port:=/dev/wildebeest-base \
  start_camera:=true start_gps:=true start_lidar:=true
```

Sensor drivers are disabled by default so a missing camera/GPS/lidar cannot
prevent base commissioning.  The lidar package and executable are launch
arguments because the concept hardware does not identify the final scanner.
The supplied defaults target Jazzy's released `rplidar_ros` package and its
`rplidar_node` executable. Change the baud rate, scan mode, package, and
executable arguments for the installed scanner model.

`use_sim:=true` selects the deterministic in-process Arduino/base mock and is
the dependency-light smoke-test path. For the full Gazebo world, use
`ros2 launch wildebeest_gz simulation.launch.py`. An explicit
`transport:=serial|mock` overrides the common switch for advanced testing.

Commands flow through `twist_mux`:

| Input | Priority | Intended source |
| --- | ---: | --- |
| `/cmd_vel/navigation` | 10 | Nav2 |
| `/cmd_vel/remote` | 40 | web/remote operator |
| `/cmd_vel/teleop` | 50 | local joystick |
| `/wildebeest/estop` | 255 lock | dashboard and safety UI |

The stable output `/cmd_vel` is an unstamped `geometry_msgs/Twist` consumed by
`wildebeest_base`.  The Arduino enforces the final 300 ms command watchdog.

Joystick control is a separate launch so it can run on an operator computer:

```bash
ros2 launch wildebeest_bringup teleop.launch.py
```

Local fusion uses wheel forward velocity and MPU6050 yaw rate; it intentionally
does not fuse the encoder-derived pose again.  GNSS global fusion is opt-in:

```bash
ros2 launch wildebeest_bringup robot.launch.py \
  start_gps:=true enable_gps_fusion:=true
```

The MPU6050 has no magnetometer and NEO-6M does not provide reliable stationary
heading.  The provided navsat configuration uses odometry yaw and therefore
requires a surveyed start pose/heading and field validation.  Do not run its
global `map -> odom` estimator at the same time as AMCL or SLAM.

The supported ROS 2 deployment is Jazzy on Ubuntu 24.04, often as a workstation
or split-compute host.  Stock Jetson Nano JetPack 4 is Ubuntu 18.04 and cannot
natively host this supported Jazzy environment; use a separately maintained
container/upgrade path or run the ROS 2 graph on a compatible machine.
