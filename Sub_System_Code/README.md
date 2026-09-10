# Subsystem code map

The old placeholder has been replaced by maintained, buildable components:

| Subsystem | Location |
| --- | --- |
| Arduino motion/safety controller | [`firmware/wildebeest_base`](../firmware/wildebeest_base) |
| ROS 2 autonomy stack | [`ros2_ws/src`](../ros2_ws/src) |
| ROS 1 compatibility stack | [`ros1_ws/src`](../ros1_ws/src) |
| Protocol simulator and diagnostics | [`tools`](../tools) |
| Browser operator console | [`dashboard`](../dashboard) |

New code should go to the owning package rather than this compatibility index.
