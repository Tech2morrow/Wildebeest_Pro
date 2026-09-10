# Robot description

The maintained Xacro, RViz configuration and simulation models are versioned as
ROS packages:

- [`ros2_ws/src/wildebeest_description`](../ros2_ws/src/wildebeest_description)
- [`ros1_ws/src/wildebeest_description`](../ros1_ws/src/wildebeest_description)

Their geometry is intentionally parametric and uses conservative primitives
until manufacturable mesh exports are produced from the SolidWorks assembly.
Do not copy the files back here; update both package variants and the canonical
measurements in [`config/robot.toml`](../config/robot.toml).
