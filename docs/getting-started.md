# Readiness and compatibility

Use this page to select a supported deployment and decide whether the robot is ready to assemble. Do not start by installing packages on an unknown Jetson image or connecting a battery to an unverified harness.

## 1. Identify the exact platform

On the Jetson, capture the following before changing the OS:

```bash
cat /etc/os-release
uname -a
test -r /etc/nv_tegra_release && cat /etc/nv_tegra_release
python3 --version
```

Photograph the module and carrier-board labels, then record the RAM variant, carrier revision, storage medium, power-input method, and JetPack/L4T release in the [configuration record](reference/configuration-record.md). Jetson Nano developer kits belong to NVIDIA's JetPack 4 generation; do not assume instructions for newer Orin hardware or JetPack 5/6 apply.

## 2. Select a software profile

| Profile | Host OS | ROS | Use when | Important constraint |
|---|---|---|---|---|
| **ROS 2 workstation / split-compute (reference)** | Ubuntu 24.04 on a supported workstation; Nano retains its validated vendor image | Jazzy | Developing and validating the maintained ROS 2 stack while preserving Nano CSI/GPU support | Hardware transport across the split is integration work; never expose unauthenticated DDS to an untrusted network |
| **ROS 2 native on replacement compute** | Ubuntu 24.04 arm64 on a capable supported SBC | Jazzy | A single-computer ROS 2 robot is more important than retaining Nano-specific hardware | Revalidate power, camera, GPIO/device interfaces, thermals, mounts and performance as a hardware revision |
| **ROS 2 experimental native Nano** | Custom image/build | Jazzy-compatible source environment | A maintainer deliberately owns kernel, camera, GPU and ROS source compatibility | Not a supported baseline; attach complete build and hardware evidence |
| **ROS 1 legacy** | Ubuntu 20.04 | Noetic | Reproducing an existing ROS 1 integration | Noetic is end-of-life; isolate it and plan migration |
| **Simulation/development** | Ubuntu 24.04 workstation | Jazzy | Developing without hardware | Simulation does not validate current draw, wiring, timing, traction, or sensor noise |

!!! warning "Do not force an OS/ROS mismatch"
    ROS 2 Jazzy targets Ubuntu 24.04 on 64-bit ARM and x86-64. ROS 1 Noetic's binary target is Ubuntu 20.04 and it is now end-of-life. A stock Jetson Nano JetPack 4 image uses a legacy Ubuntu base to retain its vendor kernel, CSI camera, and GPU stack; it cannot natively use the repository's supported Jazzy/24.04 profile. Building ROS from source, using containers, or replacing the Jetson image are separate engineering projects with camera, CUDA, kernel, GPIO, and maintenance tradeoffs—not interchangeable install commands.

The official [ROS 2 Jazzy Ubuntu installation page](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html), [ROS 1 end-of-life notice](https://www.ros.org/blog/noetic-eol/), and [NVIDIA JetPack 4.6 archive](https://developer.nvidia.com/embedded/jetpack-sdk-46) provide the upstream constraints. The [ROS 1 bridge compatibility table](https://docs.ros.org/en/humble/p/ros1_bridge/index.html) also explains why bridging modern Ubuntu releases is not a universal migration solution.

## 3. Inventory before purchase or assembly

Confirm all of these with the actual product label and datasheet:

- [ ] Jetson module/carrier revision and supported power-input path
- [ ] Arduino Uno board type and USB interface
- [ ] L298N module schematic, jumper behavior, logic supply arrangement, and terminal labels
- [ ] Motor nominal/stall current, nominal voltage, gearbox ratio, and encoder electrical interface
- [ ] Encoder counts per motor/output-shaft revolution and decoding convention
- [ ] Exact 2D LiDAR model, interface, supply, ROS driver, and scan direction
- [ ] IMX219 module compatibility with the carrier and ribbon orientation
- [ ] MPU6050 breakout input voltage, I²C pull-up voltage, and address
- [ ] NEO-6M breakout input voltage, UART logic level, antenna, and update rate
- [ ] Number and placement of HC-SR04 modules
- [ ] Battery cell provenance, configuration, capacity, protection/BMS, approved charger, connector, fuse, and enclosure
- [ ] Buck regulator input/output range and **continuous** current with thermal margin
- [ ] Latching emergency stop or equivalent motor-power disconnect
- [ ] Wire gauge, connector current rating, strain relief, insulation, and polarity keying

Unknown items stay `TBD`; they are not permission to use a convenient value.

## 4. Host prerequisites

For the selected Ubuntu/ROS combination:

1. Install the ROS distribution using its official instructions.
2. Ensure `git`, the appropriate build tool (`colcon` for ROS 2 or Catkin tools for ROS 1), `rosdep`, and Python 3 are present.
3. Clone this repository without `sudo`.
4. Run the repository bootstrap script only after reviewing it:

    ```bash
    ./scripts/bootstrap.sh ros2   # or ros1
    ./scripts/build.sh ros2       # or ros1
    ```

5. Use a normal user account. Add only the minimum serial-device access needed by your distribution; log out and back in after group changes.
6. Pin the working OS image and dependencies in the configuration record. Keep a restorable storage image once camera, LiDAR, and serial access have been proven.

The bootstrap script prepares repository dependencies; it cannot choose the correct JetPack image, battery protection, LiDAR driver, or camera ribbon orientation for you.

## 5. Readiness gates

| Gate | Pass condition |
|---|---|
| Documentation | All safety-critical TBDs in the configuration record have an owner and evidence |
| Mechanical | Wheels rotate freely; fasteners are retained; wiring cannot contact wheels, gears, fan, or sharp edges |
| Electrical | Unpowered continuity/polarity checks pass; each regulated rail is set and tested with the load disconnected |
| Firmware | Arduino boots with motor outputs disabled; emergency-stop and 300 ms watchdog behavior are bench-proven |
| ROS | Workspace builds; launch has no duplicate TF/topic owners; diagnostics expose every required device |
| Simulation | Command arbitration, odometry, TF, and stop paths pass before real motor power is enabled |
| Physical test | Staged acceptance through lifted-wheel testing is signed off before floor motion |

If any gate fails, stop at that layer. For example, a clean RViz display cannot waive a failed polarity check.

## 6. First-day success criterion

The goal is not autonomous navigation. A successful first session ends with:

- the exact hardware documented;
- software built in simulation;
- the Arduino reporting healthy telemetry with motor power physically disconnected;
- the emergency stop verified by continuity test; and
- a captured test record.

Proceed to [wiring and pinout](hardware/wiring.md) only after that baseline exists.
