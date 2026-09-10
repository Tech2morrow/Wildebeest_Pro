# Wildebeest Pro — ROS 1 Noetic compatibility workspace

This catkin workspace provides a complete ROS 1 path for the Wildebeest Pro four-wheel skid-steer robot: a CRC-protected Arduino bridge, side-encoder odometry, MPU6050 and HC-SR04 topics, NEO-6M/LiDAR/IMX219 launches, robot description, `robot_localization`, `move_base`, joystick/keyboard/remote command arbitration, diagnostics, and a Gazebo Classic autonomous demo.

> **Legacy support:** ROS Noetic reached end of life on 31 May 2025. It targets Ubuntu 20.04; the common Jetson Nano JetPack 4 image is Ubuntu 18.04 and cannot use official Noetic binaries directly. Use a maintained Ubuntu 20.04 environment/container or choose the repository's ROS 2 workspace for new deployments. Camera and GPIO access from containers needs host-specific integration.

The nominal wheel/chassis dimensions are CAD-derived: 0.033622 m radius, 0.025065 m wheel width, 0.121843 m left/right centre track, 0.117150 m axle wheelbase, and a 0.257 x 0.150 x approximately 0.031 m shell. They—and all limits, pin mappings, mass properties, covariance values, controller gains, and voltage thresholds—are **unverified commissioning defaults**. Skid-steer scrub means the effective track used by odometry usually differs from the CAD centre track. The software has mock/static tests but has not been validated on the author's physical hardware.

## Packages

| Package | Role |
| --- | --- |
| `wildebeest_base` | Safe serial transport, protocol validation, odometry, IMU/range/battery/diagnostic publication, software e-stop, and deterministic mock MCU |
| `wildebeest_description` | CAD-proportioned four-wheel URDF/Xacro, all sensor frames, four velocity transmissions, RViz model view, and Gazebo sensor hooks |
| `wildebeest_navigation` | Local encoder/IMU EKF, optional GNSS transform/global EKF, AMCL + `move_base`, GMapping, costmaps, and a smoke-test map |
| `wildebeest_bringup` | Hardware sensors, command mux, joystick, diagnostics, udev rules, and a composable robot launch |
| `wildebeest_simulation` | Gazebo Classic arena, `gazebo_ros_control`, four-wheel skid-steer control, sensors, RViz, and integrated navigation demo |

## Build

On an Ubuntu 20.04 machine with ROS Noetic installed:

```bash
cd ros1_ws
bash tools/install_noetic_dependencies.sh
source /opt/ros/noetic/setup.bash
catkin_make -DCMAKE_BUILD_TYPE=Release
source devel/setup.bash
```

Install the Arduino alias rule only after inspecting its VID/PID and adding a serial number if necessary:

```bash
bash tools/install_udev_rule.sh
```

The single source of truth for Arduino firmware is `../firmware/wildebeest_base`. It starts stopped, rejects malformed/out-of-range commands, reports hard/software stop state, and enforces a 300 ms command watchdog.

## Run without hardware

The fastest integration path uses Gazebo:

```bash
roslaunch wildebeest_simulation demo.launch
```

Send an initial pose if AMCL has not converged, then use RViz's **2D Nav Goal** tool. To smoke-test only the hardware graph and exact serial codec with an in-process MCU:

```bash
roslaunch wildebeest_bringup robot.launch use_sim:=true
```

`use_sim:=true` selects the mock base and disables physical sensor/joystick drivers by default; granular arguments may override those choices. BOOT always leaves the base stopped. Deliberately clear it, then send a fresh velocity command:

```bash
rosservice call /base/set_estop "data: false"
```

The mock follows the same wire protocol, watchdog, side-encoder kinematics, and soft-stop path as the serial transport. It is not a physics, exact sensor-timing, or hardware-safety qualification.

## Run on the robot

After wiring, firmware upload, calibration, and raised-wheel safety checks:

```bash
roslaunch wildebeest_bringup robot.launch
```

Useful profiles:

```bash
# Known indoor map: AMCL owns map -> odom
roslaunch wildebeest_bringup robot.launch navigation:=true map:=/absolute/path/site.yaml

# Create a map: GMapping owns map -> odom
roslaunch wildebeest_bringup robot.launch mapping:=true navigation:=false

# Outdoor GNSS fusion: global EKF owns map -> odom
roslaunch wildebeest_bringup robot.launch use_gps_localization:=true navigation:=false mapping:=false
```

`mapping:=true` takes precedence if both legacy mode booleans are supplied, so
GMapping and AMCL can never publish `map -> odom` together. With
`localization:=true` the local EKF owns `odom -> base_link`; with it disabled,
the base bridge becomes the single transform authority.

Never enable AMCL, GMapping, and the global GPS EKF together. The local EKF owns
`odom -> base_link` whenever localization is enabled; otherwise the base bridge
owns it. The MPU6050 has no absolute heading sensor, so the GNSS profile uses
odometry yaw and requires deliberate field validation.

## Stable interfaces

| Direction | Topic/service | Type / purpose |
| --- | --- | --- |
| Input | `/cmd_vel` | `geometry_msgs/Twist`, consumed only by the base bridge |
| Input | `/cmd_vel/remote` | Dashboard/remote `geometry_msgs/Twist` input to the mux; 0.35 s timeout, below local teleoperation |
| Input | `/wildebeest/estop` | `std_msgs/Bool`; locks the mux and latches/releases the MCU software stop |
| Input | `/base/set_estop` | `std_srvs/SetBool` service alternative |
| Input | `/base/reset_odometry` | `std_srvs/Empty`; reset the host-integrated raw odometry origin |
| Output | `/wheel/odometry` | Raw `nav_msgs/Odometry` from encoders |
| Output | `/odometry/filtered` | Local EKF estimate |
| Output | `/imu/data_raw` | Raw MPU6050 acceleration/rate; orientation is explicitly unavailable |
| Output | `/range/front` | `sensor_msgs/Range` from HC-SR04 |
| Output | `/battery_state` | `sensor_msgs/BatteryState` |
| Sensor | `/scan`, `/gps/fix`, `/camera/image_raw` | LiDAR, GNSS, and camera driver outputs |
| Health | `/diagnostics`, `/diagnostics_agg` | Link, heartbeat, watchdog, stop, protocol, battery, IMU, and range status |

Frames are `map -> odom -> base_link`, with `lidar_link`, `imu_link`, `gps_link`, `camera_link`/`camera_optical_frame`, `ultrasonic_front_link`, four wheel links, and a convenience `base_footprint` below `base_link`.

For a legacy consumer that requires `/odom`, set `odom_topic:=/odom` when including `wildebeest_base/launch/base.launch`. Do not expose both names as independently published odometry, and keep `publish_odom_tf:=false` whenever the EKF owns the transform.

Velocity producers publish to `/cmd_vel_nav`, `/cmd_vel/remote`, `/cmd_vel_keyboard`, or `/cmd_vel_joy`; `twist_mux` is the only normal owner of `/cmd_vel`. Priority is navigation < remote < keyboard < joystick, and remote/local teleoperation expires after 0.35 s. The joystick requires a held enable button. Any MCU hard/software-stop flag latches a host stop. After an explicit clear, the bridge waits for clean ODOM stop flags, discards cached velocity again, and requires a fresh command. A hard-wired, normally closed motor-power emergency stop remains required—software topics and the Arduino watchdog are additional layers, not substitutes.

## Tests

No ROS installation is needed for protocol, kinematics, mock-controller, XML, map, reference, and canonical-default checks:

```bash
python3 tools/run_checks.py
```

With Noetic sourced, also run:

```bash
catkin_make run_tests
catkin_test_results
roslaunch wildebeest_description display.launch
```

Before floor operation, calibrate effective wheel radius/track and encoder CPR, confirm all four wheel directions and both side encoder signs, characterize skid-steer scrub and stopping distance, measure serial-disconnect response, calibrate IMU/battery sensing/camera, validate LiDAR/GNSS frame orientation, and replace the demo map. The protocol intentionally treats the front/rear wheels on a side as one coupled drive and mirrors side telemetry into both wheel joints. See the root documentation for the complete evidence-driven commissioning process.
