# Wildebeest bring-up (ROS 1 Noetic)

Hardware defaults start the Arduino base, LiDAR, NEO-6M, IMX219, local EKF, joystick command mux, and diagnostics:

```bash
roslaunch wildebeest_bringup robot.launch
```

For a hardware-free graph test, use:

```bash
roslaunch wildebeest_bringup robot.launch use_sim:=true
```

Set `navigation:=true map:=/absolute/site.yaml` for mapped autonomy or `mapping:=true navigation:=false` for GMapping. Set `use_gps_localization:=true navigation:=false mapping:=false` for the outdoor GPS profile. Those modes are mutually exclusive owners of `map -> odom`.

`use_sim:=true` selects the protocol-faithful mock base and turns off physical sensor/joystick drivers by default; granular arguments can still override either choice. A valid BOOT intentionally latches the software stop in both serial and mock modes: call `rosservice call /base/set_estop "data: false"`, then issue a fresh command. Use `wildebeest_simulation/demo.launch` when Gazebo physics is wanted.

The joystick requires a held enable button. Keyboard teleoperation can be added in another terminal with `rosrun teleop_twist_keyboard teleop_twist_keyboard.py cmd_vel:=/cmd_vel_keyboard`. The dashboard publishes to `/cmd_vel/remote`, which times out after 0.35 s and has lower priority than keyboard/joystick control. Publish `std_msgs/Bool` on `/wildebeest/estop` or call `/base/set_estop`; the command mux and MCU soft stop both react. `/base/reset_odometry` (`std_srvs/Empty`) resets the host-integrated raw odometry origin. A stop reported by the MCU latches on the host until explicit clear, and the bridge requires a new command after release. A physical hard-stop circuit remains mandatory.
