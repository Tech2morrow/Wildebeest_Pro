# Wildebeest Pro ROS 2 workspace

This workspace is the ROS 2 Jazzy implementation for the Wildebeest Pro
four-wheel skid-steer robot (controlled as a differential left/right pair).
It is intentionally self-contained and can be
used in three modes:

* **Mock:** exercises the complete base, odometry, TF, localization, and
  navigation interfaces without attached hardware.
* **Physical:** talks to the Arduino motor/sensor controller over a
  checksummed serial protocol and launches the Jetson-connected sensors.
* **Gazebo Sim:** spawns the robot in Gazebo Harmonic and bridges simulated
  sensors and drive topics to ROS 2.

## Packages

| Package | Purpose |
| --- | --- |
| `wildebeest_base` | Safe Arduino serial bridge, mock controller, odometry, IMU/range publishers, diagnostics |
| `wildebeest_description` | Parameterized four-wheel Xacro model, sensor frames, and Gazebo tags |
| `wildebeest_bringup` | Robot state, physical sensor drivers, command mux, EKF/GPS fusion, teleoperation |
| `wildebeest_navigation` | Nav2, SLAM Toolbox, example map, costmaps and RViz configuration |
| `wildebeest_gz` | Gazebo Harmonic world, spawning, and `ros_gz_bridge` configuration |

## Quick start (Ubuntu 24.04 / ROS 2 Jazzy)

```bash
sudo apt install python3-rosdep python3-colcon-common-extensions
sudo rosdep init  # only once per machine
rosdep update
cd ros2_ws
rosdep install --from-paths src --ignore-src -r -y --rosdistro jazzy
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
```

Run without hardware:

```bash
ros2 launch wildebeest_bringup robot.launch.py use_sim:=true
ros2 topic pub --once /cmd_vel/teleop geometry_msgs/msg/Twist \
  "{linear: {x: 0.15}, angular: {z: 0.2}}"
```

Run the physical base (adapt the device path or create the recommended udev
rule described in `wildebeest_base/README.md`):

```bash
ros2 launch wildebeest_bringup robot.launch.py \
  transport:=serial serial_port:=/dev/wildebeest-base
```

Start mapping or navigation in another terminal:

```bash
ros2 launch wildebeest_navigation navigation.launch.py slam:=true
# or, with the included example/placeholder map:
ros2 launch wildebeest_navigation navigation.launch.py slam:=false
```

The included map only proves configuration wiring; create a real map before
autonomous operation.  Keep the robot on blocks for the first motor test and
verify emergency-stop behavior before allowing ground contact.

## Offline checks

The protocol and mock-controller tests do not need ROS installed:

```bash
python src/wildebeest_base/test/test_protocol.py
python src/wildebeest_base/test/test_mock_controller.py
python src/wildebeest_gz/test/test_safety_gate.py
python scripts/validate_workspace.py
```

On a Jazzy host, run the complete build and tests:

```bash
colcon build --symlink-install
colcon test --event-handlers console_direct+
colcon test-result --verbose
```

See each package README for parameters and hardware integration details.
Nothing in this workspace substitutes for current limiting, fusing, a
physical normally-closed emergency stop, or supervised hardware validation.
