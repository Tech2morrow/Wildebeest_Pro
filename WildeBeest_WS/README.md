# Workspace migration note

Use [`ros2_ws`](../ros2_ws/) for the primary ROS 2 Jazzy workspace or
[`ros1_ws`](../ros1_ws/) for legacy ROS 1 Noetic compatibility. Keeping each
workspace self-contained prevents accidental ROS environment mixing.

```bash
./scripts/bootstrap.sh ros2
./scripts/build.sh ros2
source ros2_ws/install/setup.bash
ros2 launch wildebeest_bringup robot.launch.py use_sim:=true
```
