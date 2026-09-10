# wildebeest_gz

This package targets the Gazebo Harmonic pairing shipped for ROS 2 Jazzy.  It
spawns the same Xacro model used by the physical stack and bridges clock,
velocity, odometry, wheel states, lidar, front range, raw IMU, GNSS, and camera
topics. A small range adapter corrects Gazebo's generic bridge output to the
hardware contract: `ULTRASOUND`, frame `ultrasonic_front_link`, 0.26 radian
field of view, and 0.02–2.0 m limits.
The four driven wheels use Gazebo's multi-joint DiffDrive configuration.
The local EKF is always started in this launch profile so it remains the sole
`odom -> base_link` transform authority; the raw Gazebo transform is not
bridged.

```bash
ros2 launch wildebeest_gz simulation.launch.py
ros2 launch wildebeest_navigation navigation.launch.py \
  use_sim_time:=true slam:=true
```

The default `spawn_z:=0.035` places the CAD-radius wheels just above the
ground plane. Override it only when using a modified model or world surface.

Send a teleoperation command through the same mux interface as hardware:

```bash
ros2 topic pub --once /cmd_vel/teleop geometry_msgs/msg/Twist \
  "{linear: {x: 0.2}, angular: {z: 0.3}}"
```

Gazebo DiffDrive itself retains its last target indefinitely. Therefore the
launch inserts `simulation_safety_twist_gate`: it consumes mux `/cmd_vel`,
publishes `/cmd_vel/sim_safe` continuously at 40 Hz, and outputs zero after
250 ms without input or whenever `/wildebeest/estop` is true. Estop release
invalidates the previous target and requires a fresh command.

The arena contains high-contrast obstacles for lidar, front range, camera, costmap, and
planning demonstrations.  Sensor noise and the differential-drive plugin are
useful integration approximations only; they do not model L298N electrical
losses, tire slip, encoder quantization, CSI-camera timing, USB latency, or the
real vehicle's dynamics.  Tune simulation and hardware independently.
