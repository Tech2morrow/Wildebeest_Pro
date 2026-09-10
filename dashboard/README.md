# Operator dashboard

This dependency-free web UI connects to ROS 1 or ROS 2 through
[`rosbridge_suite`](https://github.com/RobotWebTools/rosbridge_suite). It shows
odometry, LiDAR, IMU, GPS, range and battery freshness; renders a local scan;
and provides a dead-man joystick plus a latched software stop.

```bash
node dashboard/dev-server.mjs
# Open http://127.0.0.1:8088
```

On the robot, start rosbridge on port 9090 and expose only the network interface
you intend to trust. Browsers require `wss://` when this page is served over
HTTPS. The UI publishes standard `geometry_msgs/Twist` on
`/cmd_vel/remote`, which is routed through the robot's priority and timeout
multiplexer, and `std_msgs/Bool` on `/wildebeest/estop`. Do not remap the
dashboard directly to the base's `/cmd_vel` input because that would bypass
command arbitration.

Pose display prefers fresh `/odometry/filtered` data, then explicitly labels a
fallback to `/wheel/odometry` or simulator `/odom`. The fused-odometry health
row only reports the fused topic itself, so a raw source cannot mask an EKF
failure.

The on-screen stop is not a safety-rated control. The physical E-stop must cut
motor energy independently of the Jetson, Arduino firmware and network.
