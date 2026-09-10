# Firmware source of truth

The production Arduino Uno firmware is intentionally maintained once, at the repository root in `firmware/wildebeest_base`. It implements the same serial contract used by this ROS 1 package and the ROS 2 package. Build it with PlatformIO as documented there; do not create a ROS-version-specific firmware fork.

This directory is installed with the catkin package only to make that ownership rule visible in deployed package documentation.

Protocol v1 commands and reports one effective left side and one effective right side. The ROS model has four wheel joints, so the host mirrors each side's telemetry across its front/rear pair. CAD nominal geometry in this ROS 1 workspace must be copied into the firmware configuration and then physically calibrated before driving.
