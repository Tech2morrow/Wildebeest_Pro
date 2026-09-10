# wildebeest_description

The model uses REP-103 axes (x forward, y left, z up) and a conventional
mobile-base tree rooted at `base_link`, with a fixed ground-projection
`base_footprint` child. It models four driven skid-steer wheels (no casters),
Jetson and Arduino representations, plus `lidar_link`, `imu_link`,
`gps_link`, `camera_link`, `camera_optical_frame`, and
`ultrasonic_front_link`.

Sensor housings use a high-contrast, color-blind-conscious visual key that is
shared by RViz and Gazebo. These colors are visualization aids only; collision
geometry remains uncolored and unchanged.

| Sensor | Link | Visual color |
| --- | --- | --- |
| 2D LiDAR | `lidar_link` | Orange (`#E69F00`) |
| MPU6050 IMU | `imu_link` | Reddish purple (`#CC79A7`) |
| NEO-6M GNSS | `gps_link` | Yellow (`#F0E442`) |
| IMX219 camera | `camera_link` | Sky blue (`#56B4E9`) |
| HC-SR04 front range | `ultrasonic_front_link` | Vermillion (`#D55E00`) |

Preview it with:

```bash
ros2 launch wildebeest_description display.launch.py
```

Nominal dimensions extracted from the CAD are wheel radius `0.033622 m`, wheel
width `0.025065 m`, wheel-center track `0.121843 m`, wheelbase `0.117150 m`,
and cover envelope `0.257 x 0.150 x ~0.031 m`. Mass, inertia, and sensor
extrinsics remain conservative engineering estimates. Measure the final
machine and calibrate effective rolling radius/skid-steer track before tuning
localization or navigation.

Xacro arguments `prefix` and `use_gazebo` support multi-robot and simulation
use. The physical robot deliberately uses `wildebeest_base`; Gazebo uses the
four-joint DiffDrive system through an independent timeout-protected command
gate.
