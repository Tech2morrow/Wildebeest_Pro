# ROS 2 Jazzy

The maintained ROS 2 profile targets **ROS 2 Jazzy on Ubuntu 24.04**. For Wildebeest Pro's Jetson Nano generation, treat this as a workstation/split-compute reference: a stock JetPack 4 Nano image cannot natively provide the supported Jazzy/24.04 environment. Hardware deployment requires a separately validated transport and device-driver architecture.

!!! warning "Support boundary"
    The ROS graph, mock controller, description, and simulation can be validated on a supported workstation. That does not validate a particular Jetson image, CSI camera path, LiDAR model, serial permissions, Arduino harness, or motor system. Do not replace the Nano OS merely to make an install command pass without a recovery image and camera/GPU validation plan.

## Packages

| Package | Contents |
|---|---|
| `wildebeest_description` | Xacro/URDF, meshes, sensor and wheel frames, RViz configuration |
| `wildebeest_base` | Checksummed Arduino bridge, mock transport, wheel odometry, joint/IMU/range topics, diagnostics and stop services |
| `wildebeest_bringup` | Integrated description/base/sensor/localization/teleop/twist-mux launch |
| `wildebeest_navigation` | Nav2, SLAM Toolbox, maps and navigation RViz configuration |
| `wildebeest_gz` | Gazebo Sim/Harmonic world, spawn and ROS bridges |

## Install the ROS environment

Install Jazzy using the official [Ubuntu deb-package instructions](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html). Confirm the host reports Ubuntu 24.04 and source the ROS environment:

```bash
source /opt/ros/jazzy/setup.bash
printenv ROS_DISTRO
```

The result must be `jazzy`. Do not source ROS 1 and ROS 2 environments into the same shell unless deliberately building a supported bridge environment.

## Bootstrap and build

From the repository root:

```bash
./scripts/bootstrap.sh ros2
./scripts/build.sh ros2
source ros2_ws/install/setup.bash
```

The bootstrap script resolves declared dependencies; review it before allowing package installation. To reproduce the underlying build manually:

```bash
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths ros2_ws/src --ignore-src -r -y --rosdistro jazzy
cd ros2_ws
colcon build --symlink-install
source install/setup.bash
colcon test --event-handlers console_direct+
colcon test-result --verbose
```

Do not run `colcon` or the workspace as root. If a package is unavailable, record the exact OS architecture, repository sources, and `rosdep` error; do not substitute a package for another ROS distribution.

## Hardware-free bringup

Use mock mode before connecting the Arduino:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 launch wildebeest_bringup robot.launch.py use_sim:=true
```

If the integrated launch exposes transport directly in the checked-out revision, the equivalent base-only smoke test is:

```bash
ros2 launch wildebeest_base base.launch.py transport:=mock
```

In another terminal:

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 node list
ros2 topic list
ros2 topic hz /wheel/odometry
ros2 topic hz /odometry/filtered
ros2 topic echo /diagnostics
ros2 run tf2_ros tf2_echo odom base_link
```

Before publishing a nonzero command, confirm mock/simulation mode and that no physical base bridge owns `/cmd_vel`.

## Physical base bringup

Complete hardware acceptance stages H0–H2 first. Lift and restrain the robot, remove or open the motor-power branch, and keep the hard E-stop asserted.

### Stable serial identity

Inspect the actual device:

```bash
ls -l /dev/serial/by-id/
udevadm info --attribute-walk --name=<actual-tty-device>
```

Create a udev rule only from attributes unique to the installed Arduino. A generic vendor/product rule may capture another board. A narrowly matched example is shown in the `wildebeest_base` package README; replace every placeholder and review the resulting permissions. Prefer group access such as `dialout`, not world-writable devices.

### Launch

```bash
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
ros2 launch wildebeest_bringup robot.launch.py \
  use_sim:=false transport:=serial serial_port:=/dev/wildebeest-base
```

Launch arguments are revision-controlled API. Use `--show-args` to inspect the checkout:

```bash
ros2 launch wildebeest_bringup robot.launch.py --show-args
```

Keep motor power disconnected until all of these are true:

- `BOOT`/protocol version accepted;
- base diagnostics identify a live controller with watchdog active;
- encoder ticks change with correct sign when wheels are turned by hand;
- IMU axes and range timeout behavior are plausible;
- battery sensing is either physically absent/disabled or calibrated and safe;
- TF has one owner per edge;
- software-stop service engages, and clearing it does not create motion;
- pulling USB leaves outputs stopped by the 300 ms MCU watchdog.

## Services

The base package exposes deliberate control services:

```bash
# Engage software stop
ros2 service call /base/set_estop std_srvs/srv/SetBool "{data: true}"

# Clear software stop only after the physical scene is safe
ros2 service call /base/set_estop std_srvs/srv/SetBool "{data: false}"

# Reset host-integrated odometry while stationary
ros2 service call /base/reset_odometry std_srvs/srv/Empty "{}"
```

The reset service is optional in profiles where estimator state is authoritative; check `ros2 service list -t`. The hard E-stop is never cleared through ROS. After any stop/reset, require a fresh command source and verify diagnostics before motion.

## Sensor integration

GPS, LiDAR, and camera connect to the Jetson/sensor computer, not the Arduino protocol. Their launch is model-specific and should be disabled by default until exact drivers and device parameters are configured.

For each driver:

1. launch it alone;
2. verify device identity and permissions;
3. inspect rate, timestamp age, frame, units, covariance and disconnect behavior;
4. validate its static transform;
5. then enable it in `wildebeest_bringup`.

An IMX219 on Jetson normally depends on NVIDIA's CSI/Argus stack rather than a generic USB-camera assumption. Preserve the working JetPack camera pipeline on the Nano and bridge images only through a measured, explicitly designed method if ROS 2 runs on another computer.

## Localization

Start with encoder/IMU local odometry. The base publishes raw IMU data; configure the estimator only for measurements truly present. The MPU6050 does not provide absolute yaw. Validate covariances and TF ownership before adding LiDAR SLAM or GNSS.

In integrated bringup, the local EKF is the single `odom -> base_link` owner.
If `start_localization:=false` is deliberately selected, the base bridge
automatically becomes the single owner instead; do not start a second source.

GNSS integration typically requires `/gps/fix`, a local odometry estimate, and a valid earth-referenced heading strategy. A stationary NEO-6M fix plus gyro integration does not meet that requirement by itself.

## Mapping and navigation

With base, TF, `/scan`, and safety behavior proven:

```bash
# Create a map
ros2 launch wildebeest_navigation navigation.launch.py slam:=true

# Localize/navigate using a reviewed real map
ros2 launch wildebeest_navigation navigation.launch.py slam:=false \
  map:=<absolute-path-to-map-yaml>
```

Any included map is a configuration example, not a valid map of the user's environment. Before enabling Nav2 motion, validate footprint, inflation radius, transform tolerances, sensor range/clearing behavior, velocity/acceleration limits, recovery behaviors, and command-multiplexer priority.

## ROS 2 network hygiene

- Set a project-specific `ROS_DOMAIN_ID` to avoid unintended discovery on shared networks.
- Keep robot networks trusted and firewalled; default DDS discovery is not an authorization system.
- Use synchronized clocks and record observed offset between computers.
- Bind or configure discovery deliberately on multi-interface hosts.
- Do not put credentials in launch files, bags, diagnostics, or repository history.
- Measure bandwidth and message age for images/scans; “topic visible” does not mean timely.

## Common environment mistakes

```bash
echo "$ROS_DISTRO"             # must be jazzy
which ros2
ros2 pkg prefix wildebeest_base
printenv | grep -E 'ROS|RMW|AMENT|COLCON'
```

Use a fresh shell when uncertain. Source order is `/opt/ros/jazzy/setup.bash` and then `ros2_ws/install/setup.bash`.

## Definition of done

ROS 2 support is accepted only when the workspace builds/tests on a declared Jazzy/24.04 platform, mock and Gazebo tests pass, interfaces match the contract, and physical integration stages explicitly identify what was and was not exercised. A green workstation CI build alone is not “Jetson Nano supported.”
