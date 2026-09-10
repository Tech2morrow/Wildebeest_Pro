# ROS interface contract

This is the stable, version-neutral contract between Wildebeest Pro packages. ROS 1 uses `package/Message`; ROS 2 uses `package/msg/Message`, but field semantics, units, frames, and ownership remain the same.

## Command path

| Interface | Type | Publisher | Subscriber | Contract |
|---|---|---|---|---|
| `/cmd_vel` | `geometry_msgs/Twist` | velocity multiplexer | `wildebeest_base` | Selected base command; only `linear.x` and `angular.z` are supported |
| Raw teleop input | `geometry_msgs/Twist` | joystick/keyboard teleop | velocity multiplexer | Topic name is launch-configured; must not bypass arbitration |
| Raw navigation input | `geometry_msgs/Twist` | navigation controller | velocity multiplexer | Topic name is launch-configured; stale input times out |
| `/wildebeest/estop` | `std_msgs/Bool` | dashboard/safety UI | velocity multiplexer and base bridge | `true` engages/locks the software stop; `false` is only a release request |

The public `/cmd_vel` owner is the multiplexer. A launch configuration without a multiplexer may connect a single test source directly, but that mode must be conspicuously named and must retain the MCU watchdog. Unsupported Twist axes are ignored, never mapped to another behavior.

Control services use `/base/set_estop` (`std_srvs/SetBool`) and, where implemented, `/base/reset_odometry` (`std_srvs/Empty`). Reset odometry only while stationary. Software topic/service controls never release the physical E-stop and resetting a latch must not itself create motion.

## Base feedback

| Interface | Type | Frame(s) | Nominal source |
|---|---|---|---|
| `/wheel/odometry` | `nav_msgs/Odometry` | header `odom`, child `base_link` | `wildebeest_base`; raw encoder integration |
| `/odometry/filtered` | `nav_msgs/Odometry` | header `odom`, child `base_link` | designated local encoder/IMU estimator |
| `/joint_states` | `sensor_msgs/JointState` | joint names from URDF | `wildebeest_base` |
| `/battery_state` | `sensor_msgs/BatteryState` | n/a | `wildebeest_base`; meaningful only after ADC calibration |
| `/tf` | `tf2_msgs/TFMessage` | dynamic `odom -> base_link` | exactly one configured owner, normally the local estimator |
| `/diagnostics` | `diagnostic_msgs/DiagnosticArray` | n/a | base and sensor drivers |

`/odom` is reserved as an optional compatibility or simulator remap. It is not canonical and must never create a second odometry/TF owner. Raw and filtered odometry are continuous but may drift; they must not jump when a global localization correction arrives. Covariance values must be measured/tuned; arrays of all zeros falsely claim perfect certainty.

## Sensor topics

| Interface | Type | Required frame | Notes |
|---|---|---|---|
| `/imu/data_raw` | `sensor_msgs/Imu` | `imu_link` | Raw angular velocity and linear acceleration; orientation covariance starts with `-1` when no orientation estimate exists |
| `/range/front` | `sensor_msgs/Range` | `ultrasonic_front_link` | Radiation type, field of view, min/max range come from the exact module characterization |
| `/scan` | `sensor_msgs/LaserScan` | `lidar_link` | Model-specific driver; verify scan order, zero angle, range limits, and timestamp |
| `/camera/image_raw` | `sensor_msgs/Image` | `camera_optical_frame` | Use image transport where available |
| `/camera/camera_info` | `sensor_msgs/CameraInfo` | same optical frame | Must match resolution and calibration of the image stream |
| `/gps/fix` | `sensor_msgs/NavSatFix` | `gps_link` | Preserve driver status and covariance; no fix is not zero latitude/longitude |

Additional ultrasonic sensors use explicit location names such as `/range/left`; each requires a matching fixed frame and a documented crosstalk schedule.

## Fused-state topics

Canonical names are:

- `/wheel/odometry` — raw encoder-integrated odometry from the base bridge;
- `/odometry/filtered` — local encoder/IMU estimate;
- `/odometry/gps` — GNSS transformed into the world frame when configured;
- `/imu/data` — filtered/estimated orientation only if a component truly produces it.

Do not feed the same physical measurement twice—for example, both wheel odometry pose and a twist derived from those same ticks—without accounting for their correlation. GNSS fusion requires a valid heading strategy and plausible covariance. The `robot_localization` package can fuse odometry and IMU and transform GNSS fixes, but its configuration is not self-calibrating.

## Topic ownership rules

At runtime, audit the graph against these invariants:

1. Exactly one selected `/cmd_vel` publisher feeds the base.
2. Exactly one node owns `odom -> base_link`.
3. Exactly one node owns `map -> odom`.
4. One `robot_state_publisher` owns fixed robot transforms.
5. Each wheel joint appears once in `/joint_states`.
6. Every sensor message has a frame reachable from `base_link`.
7. Simulation and hardware drivers are mutually exclusive for a given interface.

Useful checks:

=== "ROS 2"

    ```bash
    ros2 topic info /cmd_vel --verbose
    ros2 topic info /wheel/odometry --verbose
    ros2 topic hz /wheel/odometry
    ros2 topic hz /odometry/filtered
    ros2 run tf2_tools view_frames
    ros2 run tf2_ros tf2_echo odom base_link
    ```

=== "ROS 1"

    ```bash
    rostopic info /cmd_vel
    rostopic info /wheel/odometry
    rostopic hz /wheel/odometry
    rostopic hz /odometry/filtered
    rosrun tf2_tools view_frames.py
    rosrun tf tf_echo odom base_link
    ```

## ROS 2 QoS policy

Default QoS must match the producer and consumer. As a starting contract:

| Data class | Reliability | Durability | Queue intent |
|---|---|---|---|
| Velocity command | reliable | volatile | shallow; latest command matters |
| Odometry/joints/IMU | best effort or reliable by measured link quality | volatile | bounded, small |
| LiDAR/camera | sensor-data profile (typically best effort) | volatile | avoid accumulating stale frames |
| Robot description/static metadata | reliable | transient local where the component expects it | late joiners receive state |
| Diagnostics | reliable | volatile | bounded |

Do not change reliability simply to hide packet loss. Measure resource use and end-to-end age, particularly over Wi-Fi.

## Parameters that must be recorded

| Parameter | Unit | Initial repository value | Commissioning requirement |
|---|---:|---:|---|
| Wheel radius | m | `0.033622` | CAD-derived starting value; measure under operating load |
| Effective wheel separation | m | `0.121843` | CAD geometric track; tune skid-steer behavior from repeated turns |
| Wheelbase | m | `0.117150` | CAD-derived front/rear wheel-centre spacing; verify physically |
| Encoder counts/revolution | counts/output-shaft revolution | `600` | Placeholder; identify decode mode and measure |
| Command watchdog | ms | `300` | Verify with scope/video and timestamped logs |
| Firmware control rate | Hz | `50` | Verify under maximum telemetry load |
| Odom publication target | Hz | `20` | Verify observed rate/jitter |
| IMU publication target | Hz | `50` | Optional at compile time; verify if enabled |
| Range publication target | Hz | `10` | Verify no ultrasonic crosstalk |

Robot-specific velocity, acceleration, jerk, current, voltage, and temperature limits are intentionally `TBD`. Set them from component evidence and controlled testing, not from example robot values.

## Namespaces and multi-robot use

For a single robot, the absolute topic names above keep examples simple. Multi-robot deployments must namespace topics and frame IDs consistently (for example `wb01/...`) while preserving REP-105 topology. Never put two robots on one ROS graph with both publishing unprefixed `odom -> base_link`.

## Compatibility promise

A change is interface-breaking if it changes a topic name, message type, unit, sign convention, frame, joint name, serial field meaning, or watchdog behavior. Such a change requires:

- a documented migration note;
- synchronized ROS 1, ROS 2, firmware, simulation, and documentation updates;
- new protocol/version handling where applicable; and
- replay or integration tests covering the old failure mode.
