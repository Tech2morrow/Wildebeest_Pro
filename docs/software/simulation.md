# Simulation

Simulation is the mandatory first integration environment and one layer of testing—not proof that the physical robot is safe. Wildebeest Pro provides progressively richer modes so protocol, ROS graph, geometry, and navigation failures can be isolated.

## Simulation layers

| Layer | Exercises | Does not exercise |
|---|---|---|
| Codec/unit tests | CRC, framing, schema, numeric bounds, odometry math | ROS graph, timing, physics, hardware |
| Mock base | ROS bridge, command timeout, telemetry path, odometry/joint/IMU/range interfaces | Motor/encoder electronics, true dynamics, USB faults |
| Description/RViz | Xacro expansion, joints, frames, visual geometry | Contact, traction, sensor noise, controller dynamics |
| Gazebo Sim | Spawn, differential-drive motion, simulated sensors, `/clock`, navigation integration | Actual inertia/current/thermal/EMI, exact sensor behavior, hard E-stop |
| Bag replay | Real timestamps/data through algorithms | Live actuation and some feedback timing |

A test should name the layer it passed. “Works in simulation” without that context is not an acceptance result.

## Offline protocol tests

These require Python 3 but no ROS installation:

```bash
python3 -m unittest discover -s tools/tests -v
python3 tools/mock_mcu.py --demo --seconds 2
```

The mock controller uses the framed protocol and watchdog semantics. Inject truncation, bad CRC, out-of-range command, dropped telemetry, reset and disconnect in automated tests. It is not a motor-plant model.

## ROS 2 mock bringup

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 launch wildebeest_bringup robot.launch.py use_sim:=true
```

For the base alone:

```bash
ros2 launch wildebeest_base base.launch.py transport:=mock
```

The base-only launch starts with its software E-stop latched. In another
terminal, deliberately clear it; motion still requires a fresh command:

```bash
ros2 service call /base/set_estop std_srvs/srv/SetBool "{data: false}"
```

Verify:

```bash
ros2 topic hz /wheel/odometry
ros2 topic hz /odometry/filtered
ros2 topic echo /joint_states
ros2 topic echo /diagnostics
ros2 run tf2_ros tf2_echo odom base_link
```

For integrated `robot.launch.py`, publish to an input of the velocity
multiplexer. First confirm there is no physical base subscriber:

```bash
ros2 topic info /cmd_vel --verbose
ros2 topic pub --rate 10 /cmd_vel/teleop geometry_msgs/msg/Twist \
  "{linear: {x: 0.1}, angular: {z: 0.0}}"
```

For the base-alone mock, publish directly instead:

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.1}, angular: {z: 0.0}}"
```

Stop the publisher and verify the simulated controller reports watchdog/zero motion within its configured timeout.

## ROS 1 mock bringup

```bash
source /opt/ros/noetic/setup.bash
source ros1_ws/devel/setup.bash
roslaunch wildebeest_bringup robot.launch use_sim:=true
```

For the base alone:

```bash
roslaunch wildebeest_base base.launch mock:=true
```

ROS 1 mock bringup also starts latched. Clear it deliberately before issuing a
fresh test command:

```bash
rosservice call /base/set_estop "data: false"
```

For integrated `robot.launch`, publish through a configured mux input. Inspect
topic ownership before a test command:

```bash
rostopic info /cmd_vel
rostopic pub -r 10 /cmd_vel_keyboard geometry_msgs/Twist \
  '{linear: {x: 0.1}, angular: {z: 0.0}}'
```

For the base-alone mock, publish directly instead:

```bash
rostopic pub -r 10 /cmd_vel geometry_msgs/Twist \
  '{linear: {x: 0.1}, angular: {z: 0.0}}'
```

Terminate publication and verify motion stops. Never run the same command in a shell connected to an energized physical robot.

## Robot description review

=== "ROS 2"

    ```bash
    ros2 launch wildebeest_description display.launch.py
    ```

=== "ROS 1"

    ```bash
    roslaunch wildebeest_description display.launch
    ```

Review both visuals and structure:

- one connected tree rooted at `base_link`, with a fixed ground-projection frame where supplied;
- wheel joint axes and positive rotation correct;
- collision shapes cover the physical envelope without excessive complexity;
- inertial values positive, plausible and expressed in the correct link frame;
- sensors appear at measured origins with correct axes;
- camera optical transform follows ROS convention;
- no absolute mesh paths or dependence on a developer's filesystem;
- no duplicate joint or frame names.

URDF mass/inertia and dimensions begin as placeholders unless backed by measurements. A model that loads successfully can still be physically wrong.

## ROS 2 Gazebo Sim

The ROS 2 simulation package targets Gazebo Harmonic through the Jazzy integration:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 launch wildebeest_gz simulation.launch.py
```

If the launch exposes optional arguments, inspect them from the checkout:

```bash
ros2 launch wildebeest_gz simulation.launch.py --show-args
```

Expected contracts include simulated time, a spawned robot description, wheel motion driven through the selected command path, odometry/TF, joint states, LiDAR scan, and whichever camera/range plugins the current revision declares. Validate actual topics with `ros2 topic list`; do not assume a plugin loaded because its frame exists.

### Clock rule

All nodes participating in Gazebo simulation must use simulated time. A mix of wall clock and `/clock` produces stale-transform and filter failures that can look intermittent:

```bash
ros2 topic echo /clock --once
ros2 param get /robot_state_publisher use_sim_time
```

### Physics sanity checks

- Robot remains at rest with zero command on a level surface.
- Positive linear and angular commands follow the interface convention.
- Left/right wheel joint position and odometry signs agree.
- Collision geometry does not start intersecting the ground or chassis.
- The robot does not tip under configured acceleration on the declared surface.
- Scan and camera orientations agree with visible landmarks.
- Pausing simulation freezes time-dependent nodes cleanly.
- Resetting the world cannot create a huge odometry jump without a reported reset.

Do not tune navigation to compensate for unrealistic mass, friction, inertia, controller latency, or sensor update rates.

## ROS 1 physics simulation

The ROS 1 workspace provides a Gazebo Classic demo as an advanced direct launch:

```bash
roslaunch wildebeest_simulation demo.launch
```

ROS 1 Noetic and Gazebo Classic-era integrations are legacy. Inspect the launch and dependency versions; if the demo is unavailable on the declared image, document that limitation in the test report rather than claiming physics-simulation parity.

The ROS 1 acceptance goal is interface/behavior parity, not identical simulator implementation. Replay the same command and fault scenarios against both stacks.

## Navigation scenarios

Build small, version-controlled worlds with observable pass/fail conditions:

| Scenario | Purpose | Pass evidence |
|---|---|---|
| Empty level world | Command/odometry signs and drift | Plot commanded versus simulated pose |
| Straight corridor | LiDAR alignment, footprint and local planner | No wall collision; centered path within declared tolerance |
| Doorway near footprint limit | Inflation/footprint correctness | Planner refuses unsafe gap or traverses verified safe one |
| Static obstacle | Costmap marking and braking | Obstacle marked; stop distance within test requirement |
| Appearing obstacle | Sensor freshness and controller reaction | No collision; timestamped reaction trace |
| Lost scan | Stale-sensor response | Navigation commands zero/degraded state |
| Command publisher crash | Mux/bridge/MCU timeout analogue | Base returns to zero |
| Localization jump | Recovery behavior | No uncontrolled command; explicit fault/relocalization |

Set speed low and deterministic seeds where supported. Save world, parameters, goal, initial pose, simulator version, logs, and result artifact.

## Bag replay

Record only necessary topics and account for camera/GNSS privacy. Replays must preserve or deliberately remap frames and use simulated time where the consumer expects it.

=== "ROS 2"

    ```bash
    ros2 bag record /tf /tf_static /wheel/odometry /odometry/filtered /joint_states /imu/data_raw /range/front /scan /gps/fix /diagnostics
    ros2 bag info <bag-directory>
    ros2 bag play <bag-directory> --clock
    ```

=== "ROS 1"

    ```bash
    rosbag record /tf /tf_static /wheel/odometry /odometry/filtered /joint_states /imu/data_raw /range/front /scan /gps/fix /diagnostics
    rosbag info <bag-file>
    rosbag play --clock <bag-file>
    ```

Never replay `/cmd_vel` into a live robot graph. Use an isolated domain/master, remap the command topic, or physically disconnect motor power.

## Simulation acceptance

A release passes simulation when:

- workspaces build from a clean dependency environment;
- protocol and mock tests pass;
- URDF is connected and frame ownership is unique;
- zero/nonzero/watchdog/stop/reset scenarios pass;
- Gazebo scenarios pass where that simulator is implemented;
- navigation does not move with stale mandatory sensing;
- results name versions and include machine-readable test output;
- all known model-versus-hardware differences are listed.

Proceed to lifted-wheel hardware testing only after simulation passes. Physical testing then validates everything simulation deliberately omits.
