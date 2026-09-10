# Hardware limitations and upgrade path

Wildebeest Pro intentionally preserves the components named in the original concept, but several are legacy, underspecified, or unsuitable for unattended/production robotics. This page defines honest support boundaries and the evidence required to change them.

## Limitation matrix

| Component/design choice | What it enables | Principal limitation | Upgrade trigger |
|---|---|---|---|
| Jetson Nano + JetPack 4 | CSI camera and CUDA-era edge compute on the original platform | Legacy vendor OS; does not natively match ROS 2 Jazzy/Ubuntu 24.04; limited compute/memory by modern autonomy standards | Need maintained native Jazzy, higher perception rate, more memory, or current security support |
| Arduino Uno | Simple deterministic 5 V I/O and widely understood tooling | Limited CPU/RAM/timers/interrupt pins; no hardware safety certification; USB serial lacks industrial robustness | Missed encoder edges, timing jitter, more sonar/I/O, current control, CAN/RS-485, or stronger diagnostics needed |
| L298N | Familiar dual brushed-motor bridge | Bipolar voltage drop, heat/inefficiency, limited diagnostics/protection compared with modern MOSFET bridges | Measured stall/continuous current, rail drop, temperature, braking or fault-reporting needs exceed validated envelope |
| Original encoder/KY-040 concept | Basic quadrature odometry | Module name may describe a hand encoder rather than a motor-rated encoder; resolution/output type/max speed unknown | Edge rate, durability, resolution or mounting fails H2/H4 tests |
| MPU6050 | Low-cost acceleration and angular rate | No magnetometer/absolute yaw; bias, drift, vibration and I²C integrity constraints | Need reliable heading, lower drift/noise, temperature calibration, timestamping or higher integrity |
| NEO-6M GNSS | Basic outdoor position/NMEA | No reliable stationary heading; multipath/obstruction; not precision or safety rated | Mission needs robust lane-level/centimetric positioning, heading at rest, integrity monitoring or high update rate |
| Unspecified 2D LiDAR | Planar ranging for mapping/obstacles | Exact driver/performance unknown; one plane misses over/under-plane objects and difficult surfaces | Identification/support unavailable or environment requires 3D/overhang/low-obstacle coverage |
| IMX219 camera | Compact CSI vision | Depends on light/lens/focus/vendor CSI stack; rolling shutter and transport latency may constrain motion | Vision task cannot meet measured accuracy/latency/environment envelope |
| HC-SR04 | Low-cost near-field ranging | Acoustic cone, soft/angled target failures, crosstalk, temperature effects; no-return is ambiguous | Safety/coverage needs reliable near-field detection or environmental sealing |
| 2S Li-ion + adjustable buck module | Compact mobile energy | Exact cells/BMS/charger/regulator are unknown; marketplace specifications and CAD labels are not evidence | Any lack of traceability/protection/margin, or compute/motor transient/thermal failure |
| CAD-derived chassis | Rich original mechanical concept | No released drawings/material/tolerances/load case; source assembly includes vendor/reference parts | Fit, structural, center-of-gravity, service, weather or manufacturability review fails |

## Compute choices

### Preserve the Nano

Keep its validated JetPack image for CSI/GPU/vendor drivers and run the Jazzy graph on an Ubuntu 24.04 workstation. This is a split-compute experiment until sensor transport, time synchronization, network security, bandwidth, disconnect behavior and stop behavior pass acceptance. The Arduino watchdog remains local and independent of the network.

### Experimental container or source build

A community container/source path on the Nano may be useful for research, but it is not the repository's supported baseline. Record base image digest, kernel/L4T, architecture, ROS source revisions, patches, device mounts/privileges, GPU/CSI behavior, time synchronization, performance and update strategy. Never use a privileged container as an unexplained device-access shortcut.

### Replace the compute module

A capable SBC with supported Ubuntu 24.04 arm64 can provide a native Jazzy path. Select it from measured workload and interfaces—not benchmark marketing. Replacing the Nano requires a new hardware revision and repeat of power, transient, thermal, mounting, mass, camera, USB/UART/I²C/GPIO levels, networking, drivers, calibration and acceptance tests.

## Drive electronics

Before retaining the L298N, measure both motors' stall current at the intended motor rail using a safe method, sustained mission current, startup/reversal transients, loaded motor voltage, braking behavior and driver temperature in the closed enclosure. Compare these with the exact module's documented DC/peak/thermal envelope and wiring/connector limits.

A replacement bridge should be selected for:

- verified supply and per-channel continuous/peak current with thermal margin;
- logic compatibility/isolation and boot-safe input behavior;
- current limiting/sensing and hardware fault output where needed;
- braking/coast behavior appropriate to stopping requirements;
- reverse-polarity/transient/overtemperature protections;
- available driver/firmware interface and diagnostic coverage.

Changing the bridge can change direction truth tables, PWM frequency/polarity, deadband, electrical braking, current draw and stop behavior. Treat it as safety-relevant.

## Sensing coverage gaps

No single installed sensor proves free space:

- A 2D scan plane can pass beneath a tabletop or above a low object.
- Ultrasonic sensors can miss angled, soft or narrow targets and interfere with each other.
- Monocular camera depth depends on algorithms, calibration, texture and light.
- Wheel odometry fails under slip/lift.
- IMU yaw drifts without an absolute reference.
- GNSS fails indoors and can be wrong near reflective/obstructing structures.

Define the hazard geometry and environment first, then select complementary sensing and physical barriers. A safety-rated scanner/bumper/controller cannot be replaced by combining several hobby sensors in software.

## Real-time and bandwidth limits

The Uno control loop is 50 Hz and serial telemetry shares a 115200 baud link. Measure utilization and worst-case loop/encoder behavior with ODOM 20 Hz, IMU 50 Hz and RANGE 10 Hz enabled. Increasing rates or adding verbose text can starve control or overflow buffers. High-bandwidth camera, LiDAR and GNSS streams therefore remain off the MCU link.

The Jetson/workstation path must meet end-to-end age requirements, not just average rate. Record CPU/GPU/memory, thermal throttling, USB contention, storage write load, DDS/network bandwidth, drops and worst observed timestamp age under the actual mission workload.

## Environmental limits

Unless a released revision proves otherwise, assume:

- indoor, dry, clean, noncondensing use only;
- level, firm surfaces with physical edge barriers;
- no ingress, impact, chemical, UV or electromagnetic compatibility rating;
- no operation near combustible atmospheres, road traffic or the public;
- no lifting/carrying payload that can harm a person;
- no unattended charging or operation.

Set numeric temperature, humidity, slope, payload, lighting and surface limits from actual component specifications and tests.

## Upgrade decision record

For any upgrade, record:

1. requirement the baseline cannot meet;
2. measured evidence of the limitation;
3. candidate part and exact datasheet/revision;
4. electrical/mechanical/software/interface impact;
5. new failure modes and safety controls;
6. files/configuration/calibration changed;
7. acceptance stages repeated and evidence;
8. fallback/recovery plan.

Do not advertise an upgrade as “drop-in” unless every affected interface and test demonstrates that claim.
