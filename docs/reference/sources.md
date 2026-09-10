# Documentation sources

Project guidance distinguishes upstream facts from robot-specific assumptions. Consult the current upstream page before changing an OS image, ROS distribution, driver, or safety-relevant component.

## ROS and platform sources

- [ROS 1 Noetic end-of-life notice](https://www.ros.org/blog/noetic-eol/) — Noetic/ROS 1 support ended on 31 May 2025.
- [ROS 2 Jazzy Ubuntu installation](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html) — the repository's reference ROS 2 profile uses Jazzy on Ubuntu 24.04.
- [ROS 2 Jazzy release/platform information](https://docs.ros.org/en/jazzy/Releases/Release-Jazzy-Jalisco.html) — authoritative platform and support details.
- [ROS 1 bridge compatibility](https://docs.ros.org/en/humble/p/ros1_bridge/index.html) — co-installation and operating-system constraints.
- [REP-105 coordinate frames](https://www.ros.org/reps/rep-0105.html) — `map`, `odom`, and `base_link` semantics.
- [ROS 2 `diff_drive_controller`](https://control.ros.org/jazzy/doc/ros2_controllers/diff_drive_controller/doc/userdoc.html) — wheel feedback, velocity commands, odometry, limits, and timeout behavior.
- [`robot_localization` documentation](https://docs.ros.org/en/noetic/api/robot_localization/html/index.html) — odometry/IMU fusion and GNSS transformation concepts.
- [NVIDIA JetPack 4.6 archive](https://developer.nvidia.com/embedded/jetpack-sdk-46) — Jetson Nano generation-specific software resources.

## Component evidence required locally

Before hardware commissioning, archive the exact manufacturer's documentation or distributor traceability for:

- Jetson Nano module and carrier board;
- Arduino-compatible board;
- motor and gearbox;
- encoder or KY-040-style module;
- L298N carrier board;
- MPU6050 breakout;
- NEO-6M GNSS breakout and antenna;
- exact LiDAR model;
- exact IMX219 camera module;
- HC-SR04 modules;
- battery cells, holder/pack, BMS/protection board, and charger;
- buck regulator(s), fuse, switch, E-stop, connectors, and wire.

A CAD filename, marketplace title, silkscreen color, or family name is not a datasheet. Record document revision and a local checksum or durable URL in the [configuration record](configuration-record.md).

## Updating this handbook

When an upstream link changes, update the link and the associated compatibility claim in the same pull request. Do not silently change a tested platform profile to follow the newest ROS release; add and validate a new profile first.
