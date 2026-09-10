# Bill of materials

This is a functional BOM, not a purchasing guarantee. The original CAD includes recognizable module models, but marketplace modules with the same name often differ electrically and mechanically. Record manufacturer part numbers and verify the actual items before ordering mates, machining parts, or applying power.

## Core compute and control

| Qty | Item | Minimum selection evidence | Status to record |
|---:|---|---|---|
| 1 | NVIDIA Jetson Nano developer kit/module + carrier | Exact module/carrier revision, supported OS/JetPack, power input, CSI connector, cooling | `TBD` |
| 1 | Compatible storage medium | Capacity, endurance, image/backup method | `TBD` |
| 1 | Arduino Uno or pin-compatible 5 V MCU board | Board revision, USB interface, ADC reference behavior, I/O current limits | `TBD` |
| 1 | USB data cable, Jetson to Arduino | Data-capable, locking/strain-relieved where possible | `TBD` |
| 1 | Active cooling solution for Jetson | Supply, control method, clearance, verified airflow | CAD shows an NF-A4x20-class fan; actual part `TBD` |

## Drive and odometry

| Qty | Item | Minimum selection evidence | Notes |
|---:|---|---|---|
| 4 | Brushed DC geared motor | Voltage range, no-load and stall current, gear ratio, shaft, mounting | Matched units; front/rear motors are paired by side |
| 4 | Drive wheel | Measured loaded rolling radius, hub/shaft fit, tire material | CAD nominal radius is `0.033622 m`; verify under load |
| 2 minimum | Quadrature encoder | Supply, output type/level, counts definition, max edge rate | At least one observed wheel per side; repository default `600` counts/rev is a placeholder |
| 1 | L298N dual H-bridge module | Actual schematic, current/thermal behavior, logic arrangement, voltage drop | Each channel carries a same-side motor pair; verify combined stall current or replace the driver |
| 1 set | Motor/encoder connectors and harness | Current rating, keying, strain relief, flex life | Keep encoder wiring away from motor leads |

### L298N limitation

The L298N is an older bipolar-transistor driver with significant voltage drop and heat dissipation compared with modern MOSFET bridges. A red breakout board is not a current rating. Each channel must carry the combined load of two same-side motors in this four-wheel layout. Measure individual and paired stall current, driver temperature, loaded rail voltage, and duty cycle. If the driver cannot meet the verified envelope with margin, replace it with a protected driver sized for the paired load and update firmware polarity, wiring, BOM, tests, and CAD.

## Sensors

| Qty | Item | Interface to target | Evidence required |
|---:|---|---|---|
| 1 | MPU6050 IMU breakout | Arduino I²C | Breakout supply and pull-up topology, address, axis orientation |
| 1 | NEO-6M GNSS breakout + antenna | Jetson via verified USB/UART adapter | Supply and logic level, baud, update rate, antenna requirements |
| 1 | 2D LiDAR | Jetson, normally USB or serial | Exact model, driver, scan rate, supply/current, connector and mount |
| 1 | IMX219 camera + ribbon | Jetson CSI | Carrier compatibility, ribbon pin count/orientation, supported modes |
| 1 default | HC-SR04 ultrasonic module | Arduino trigger/echo | Exact module behavior, min/max useful range, beam and temperature effects |

The firmware reference pinout provides one front ultrasonic channel. More modules require an explicitly designed acquisition schedule and additional I/O or a secondary controller; do not parallel echo outputs.

## Power and protection

| Qty | Item | Selection/verification requirement |
|---:|---|---|
| 1 | Protected 2S Li-ion battery pack | Traceable cells; pack/BMS configuration; continuous/peak current; temperature limits; physical protection |
| 1 | Charger approved for the exact pack chemistry/configuration | Connector/polarity keyed differently from the load where practical |
| 1 | Main service disconnect | Rated for pack fault current and DC interruption |
| 1 | Branch fuse and holder | Rating derived from conductor, connector, driver, and expected load; mounted near energy source |
| 1 | Latching emergency-stop/disconnect assembly | Interrupts motor energy; optionally provides a separate dry contact for MCU status |
| 1+ | DC-DC buck regulator | Input range covers pack envelope; output accuracy, transient response, continuous current, thermal margin |
| as designed | Additional branch fuses/protection | Separate compute/sensor and actuator faults where the design permits |
| 1 | Battery-voltage divider/filter for Arduino A2 | Resistors sized for the **maximum possible pack voltage** and ADC pin limit; documented ratio and tolerance |
| 1 | Fire-resistant battery enclosure/retention | Prevents abrasion, crushing, puncture, shorting, and ejection |

!!! danger "The CAD battery model is not a battery design"
    A cell-holder model or capacity printed in a filename does not prove cell authenticity, safe parallel/series construction, balancing, protection, or charge compatibility. Do not assemble loose cells into a traction pack without the required battery-design competence and equipment. Prefer a professionally assembled, protected pack with traceable documentation.

## Structure and integration

- Base, top and bottom covers
- Motor mounts and encoder supports
- LiDAR, camera, ultrasonic and GNSS mounts
- Correct fasteners, washers, thread retention and spacers
- Insulating standoffs and guards for circuit boards and terminals
- Cable clips, abrasion protection, strain relief and service loops
- Wheel/shaft retention and guards around pinch points
- Clearly labeled main disconnect, emergency stop, charge port and polarity

The source SolidWorks assembly and STEP exports are reference geometry. Before fabrication, check units, material, tolerances, fastener lengths, tool access, cooling clearance, center of gravity, ground clearance, sensor field of view, and cable bend radius.

## Workshop and commissioning equipment

These are part of a safe build even though they remain off-robot:

- current-limited bench supply suitable for each rail;
- calibrated digital multimeter and, ideally, oscilloscope/logic analyzer;
- approved battery charger and fire-conscious charging/storage arrangement;
- insulated hand tools, ferrule/crimp tooling matched to terminals, and wire labels;
- nonconductive robot stand that leaves all four drive wheels free;
- USB isolator only if it is explicitly compatible with the test arrangement;
- tachometer or reliable wheel-revolution reference;
- scale/tape/calipers, level, marked floor course and camera calibration target;
- thermometer or thermal camera for driver/regulator/compute thermal checks.

## Power-budget worksheet

Complete this from datasheets and measurements. Do not size a regulator from typical current alone.

| Load | Rail | Idle | Sustained worst case | Startup/transient | Source evidence |
|---|---:|---:|---:|---:|---|
| Jetson + storage + fan | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| LiDAR | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| Camera | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| Arduino + IMU + sonar | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |
| Left motor | motor rail | `TBD` | `TBD` | stall `TBD` | `TBD` |
| Right motor | motor rail | `TBD` | `TBD` | stall `TBD` | `TBD` |

For each regulator/branch, document:

```text
continuous margin = rated continuous output under installed cooling - measured sustained load
transient margin  = validated transient capability - measured startup/step load
thermal margin    = component limit - worst observed component temperature
```

Ratings require the installed airflow and ambient-temperature envelope. A regulator that works uncovered on a bench may overheat inside the robot.

## Release BOM rule

A reproducible hardware release includes a machine-readable BOM with part number, manufacturer, supplier, quantity, approved substitutes, lifecycle status, datasheet revision, and the robot hardware revision it applies to. Substitutes that affect voltage, logic, geometry, driver software, calibration, or safety are engineering changes—not purchasing equivalents.
