# ROS 1 Noetic

ROS 1 support targets **Noetic on Ubuntu 20.04** for legacy and migration use. ROS 1 Noetic reached end of life on 31 May 2025: there are no new official security updates, fixes, or binary releases. Use an isolated, documented environment and prefer ROS 2 Jazzy for new work.

!!! danger "Legacy deployment risk"
    Do not expose an end-of-life ROS 1 master or host to an untrusted network. ROS 1 graph connectivity does not provide modern authentication or authorization. Keep the robot behind a controlled network boundary and maintain a migration plan.

## Package parity

The ROS 1 workspace mirrors the public roles and interface semantics of ROS 2:

| Package | Purpose |
|---|---|
| `wildebeest_description` | URDF/Xacro, meshes, sensor frames and RViz configuration |
| `wildebeest_base` | Arduino serial bridge/mock, odometry/joints/raw IMU/range and diagnostics |
| `wildebeest_bringup` | Description, base, model-specific sensors, state estimation and command arbitration |
| `wildebeest_navigation` | ROS navigation/SLAM configuration and maps |

The shared firmware and [serial protocol](../reference/serial-protocol.md) are the source of truth; a second copy of firmware under a ROS package must not drift from them.

## Install and build

Install Noetic using the archived official ROS instructions appropriate to Ubuntu 20.04, then from the repository root:

```bash
source /opt/ros/noetic/setup.bash
./scripts/bootstrap.sh ros1
./scripts/build.sh ros1
source ros1_ws/devel/setup.bash
```

Manual equivalent:

```bash
source /opt/ros/noetic/setup.bash
rosdep install --from-paths ros1_ws/src --ignore-src -r -y \
  --rosdistro noetic --skip-keys gscam
cd ros1_ws
catkin_make
source devel/setup.bash
catkin_make run_tests
catkin_test_results
```

Use a normal user account and do not mix Python packages from an unrelated virtual environment into ROS nodes unless the environment is deliberately tested. Preserve the apt/package snapshot or a restorable system image because Noetic is EOL.

## Hardware-free bringup

```bash
source /opt/ros/noetic/setup.bash
source ros1_ws/devel/setup.bash
roslaunch wildebeest_bringup robot.launch use_sim:=true
```

For a base-only checkout that exposes the lower-level mock argument:

```bash
roslaunch wildebeest_base base.launch mock:=true
```

Inspect the graph:

```bash
rosnode list
rostopic list
rostopic hz /wheel/odometry
rostopic hz /odometry/filtered
rostopic echo /diagnostics
rosrun tf tf_echo odom base_link
```

Confirm no physical serial process is running before injecting test commands.

## Physical base bringup

Complete H0–H2 and follow the same stable-device and current-limited stand procedure as ROS 2. Then:

```bash
source /opt/ros/noetic/setup.bash
source ros1_ws/devel/setup.bash
roslaunch wildebeest_bringup robot.launch \
  use_sim:=false base_port:=/dev/wildebeest-base sensors:=false joystick:=false
```

This first launch isolates the base. After each model-specific sensor and the selected teleoperation device passes its standalone test, enable only the required components in the full profile.

Inspect the exact launch API in the checkout:

```bash
roslaunch wildebeest_bringup robot.launch --args
```

Do not enable the motor branch until diagnostics, hand-turned encoder sign, reset handling, hard/software stops, and USB-pull watchdog behavior pass.

## Software stop and odometry reset

```bash
# Engage software stop
rosservice call /base/set_estop "data: true"

# Clear only after the physical scene is safe
rosservice call /base/set_estop "data: false"

# Reset host odometry while stationary, where the checked-out profile provides it
rosservice call /base/reset_odometry "{}"
```

`/base/reset_odometry` uses `std_srvs/Empty` and is optional where estimator state is authoritative. Service availability depends on the installed package revision. The physical E-stop is authoritative and cannot be cleared through ROS.

## ROS 1 networking

For a remote workstation, choose one reachable master, set hostnames/IPs consistently, and verify bidirectional connectivity. A common explicit layout is:

```bash
export ROS_MASTER_URI=http://<robot-host>:11311
export ROS_IP=<this-host-ip>
```

Do not set `ROS_HOSTNAME` and `ROS_IP` inconsistently. Test by echoing a small topic from each host, then inspect a high-bandwidth sensor separately. Isolate the network; anyone who can reach the ROS 1 graph may be able to publish motion commands or call services.

## Sensors and navigation

GPS, LiDAR and camera remain model-specific Jetson devices. Install only drivers compatible with Noetic and the exact vendor hardware. Validate each standalone before including it in bringup. `gscam` is not resolved by the current Noetic rosdep index, so the bootstrap deliberately skips it and the camera launch defaults to off. Install and validate a Jetson-compatible `gscam` build separately, then opt in with `camera:=true`; do not enable that launch flag merely because a camera frame exists in the URDF.

For mapping/navigation, prove `/scan`, `odom -> base_link`, URDF transforms, footprint, and stop paths before starting the navigation stack. Store real maps outside generated build directories and record their coordinate origin and environment revision.

The integrated launch makes transform ownership explicit: the local EKF owns
`odom -> base_link` while localization is enabled, and the base bridge owns it
only when localization is disabled. `mapping:=true` takes precedence over
`navigation:=true` if both are supplied, preventing GMapping and AMCL from
publishing `map -> odom` together.

## Migration to ROS 2

Prefer migrating packages and replayable tests over operating a permanent `ros1_bridge`. When a temporary bridge is necessary:

- consult the official compatibility matrix for an OS where both sides can be built;
- bridge only enumerated topics needed for the migration test;
- ensure there is still exactly one `/cmd_vel` and TF owner;
- never bridge software-stop semantics without an end-to-end failure test;
- record serialization, QoS and timestamp behavior;
- remove the bridge when native ROS 2 ownership is complete.

Ubuntu 24.04 does not support ROS 1, so the Jazzy workstation is not a drop-in host for a dynamic bridge.

## Definition of done

ROS 1 support means reproducible Noetic/20.04 builds and tests, protocol parity with firmware, hardware-free operation, and clearly labeled physical evidence. It does not mean ROS 1 is maintained upstream or safe to deploy on an open network.
