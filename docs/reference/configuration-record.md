# Configuration record

Create one copy of this record per physical robot and released hardware/software combination. `TBD` means the robot has not passed commissioning for the affected function.

## Identity and provenance

| Field | Value |
|---|---|
| Robot ID / asset number | `TBD` |
| Hardware revision | `TBD` |
| Assembly date / technician | `TBD` |
| Repository commit/tag | `TBD` |
| Firmware build ID and compile-time options | `TBD` |
| ROS profile and distribution | `TBD` |
| Jetson module/carrier revision | `TBD` |
| JetPack/L4T and Ubuntu version | `TBD` |
| Storage image checksum/backup location | `TBD` |

## Safety and power

| Field | Value / evidence |
|---|---|
| Battery manufacturer/part/serial | `TBD` |
| Cell chemistry/configuration | 2S Li-ion stated by concept; exact pack `TBD` |
| BMS/protection specifications | `TBD` |
| Approved charger | `TBD` |
| Main fuse type/rating/rationale | `TBD` |
| Wire/connector rating rationale | `TBD` |
| Hard E-stop part and motor-energy interruption diagram | `TBD` |
| Compute rail voltage/current/transient/thermal validation | `TBD` |
| Motor rail envelope and peak current | `TBD` |
| Battery-divider values, tolerance analysis and scale factor | `TBD` |
| Undervoltage warning/stop thresholds and pack evidence | `TBD` |
| Maximum component/ambient temperature criteria | `TBD` |

## Geometry and drive

| Field | Repository initial value | Measured value / uncertainty / method |
|---|---:|---|
| Left effective wheel radius | 0.033622 m CAD baseline | `TBD` |
| Right effective wheel radius | 0.033622 m CAD baseline | `TBD` |
| Geometric wheel separation | 0.121843 m CAD baseline | `TBD` |
| Effective skid-steer separation | 0.121843 m initial setting | `TBD` |
| Front/rear wheelbase | 0.117150 m CAD baseline | `TBD` |
| Left counts/output revolution | 600 placeholder | `TBD` |
| Right counts/output revolution | 600 placeholder | `TBD` |
| Quadrature decode mode | `TBD` | `TBD` |
| Motor polarity | `TBD` | `TBD` |
| Encoder polarity | `TBD` | `TBD` |
| Total operating mass / payload | `TBD` | `TBD` |
| Center-of-gravity validation | `TBD` | `TBD` |
| Ground clearance | `TBD` | `TBD` |

## Software safety limits

| Field | Initial contract | Validated setting / evidence |
|---|---:|---|
| MCU command watchdog | 300 ms | `TBD` |
| MCU control target | 50 Hz | `TBD` |
| Maximum linear velocity | none implied | `TBD` |
| Maximum angular velocity | none implied | `TBD` |
| Linear/angular acceleration limits | none implied | `TBD` |
| Command-source timeouts/priorities | configuration-dependent | `TBD` |
| Motor current/temperature stop policy | hardware-dependent | `TBD` |
| Sensor freshness thresholds | sensor-dependent | `TBD` |

## Sensors

For every sensor, attach the exact datasheet and record supply, interface, identifier/device path, driver/version, update rate, frame, measured transform, calibration file/checksum, covariance basis, freshness threshold, and known degraded behavior.

| Sensor | Exact part | Interface/device | Frame | Calibration/evidence |
|---|---|---|---|---|
| Left encoder | `TBD` | D2/D4 default | wheel joint | `TBD` |
| Right encoder | `TBD` | D3/D12 default | wheel joint | `TBD` |
| MPU6050 breakout | `TBD` | A4/A5 I²C default | `imu_link` | `TBD` |
| Front HC-SR04 | `TBD` | D11/A0 default | `ultrasonic_front_link` | `TBD` |
| 2D LiDAR | `TBD` | Jetson direct, `TBD` | `lidar_link` | `TBD` |
| IMX219 camera/lens | `TBD` | Jetson CSI | `camera_optical_frame` | `TBD` |
| NEO-6M breakout/antenna | `TBD` | Jetson direct, `TBD` | `gps_link` | `TBD` |

## Network and operations

| Field | Value |
|---|---|
| Robot hostname | `TBD` |
| Network trust boundary | `TBD` |
| Time synchronization source and measured offset | `TBD` |
| ROS 1 master URI/network settings, if used | `TBD` |
| ROS 2 domain ID/RMW/discovery policy, if used | `TBD` |
| Log/bag retention location and capacity | `TBD` |
| Operator, spotter and test-zone requirements | `TBD` |
| Authorized operating surface/slope/weather/light | `TBD` |
| Startup/shutdown checklist revision | `TBD` |

Do not store Wi-Fi passwords, access tokens, private keys, or personal data in this repository. Reference the approved secret-management location instead.

## Acceptance sign-off

| Stage | Result | Date | Evidence link | Reviewer |
|---|---|---|---|---|
| H0 Documentation/design review | `NOT RUN` | | | |
| H1 Unpowered/rail validation | `NOT RUN` | | | |
| H2 Firmware and sensor bench | `NOT RUN` | | | |
| H3 Lifted-wheel motion | `NOT RUN` | | | |
| H4 Low-speed manual floor test | `NOT RUN` | | | |
| H5 Localization | `NOT RUN` | | | |
| H6 Simulation regression | `NOT RUN` | | | |
| H7 Supervised autonomous mission | `NOT RUN` | | | |
| H8 Endurance/thermal test | `NOT RUN` | | | |

Any safety-relevant hardware, firmware, calibration, limit, or launch change invalidates the affected sign-offs until regression tests are repeated.
