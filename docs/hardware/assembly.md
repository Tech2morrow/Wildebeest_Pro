# Mechanical assembly

The repository contains an original SolidWorks assembly and component models. Treat them as a starting point for fit and packaging. Material specifications, tolerances, fastener torque, final mass properties, wiring clearances, and drawing release status are not established by the files alone.

## Assembly sequence

### 1. Review and measure

- Open the top-level assembly and confirm document units.
- Create dimensioned manufacturing drawings for every custom part.
- Compare hole patterns and connector locations with the physical Jetson carrier, Arduino, driver, regulators, sensors, motors, and battery.
- Check the assembled wheel radius, track, and wheelbase against the CAD-derived URDF baselines, but do not edit measurements to make the CAD agree.
- Weigh major components and estimate center of gravity in the fully wired configuration.
- Define service access for fuse, disconnect, E-stop, storage, USB, charge connector, and fasteners.

Record every mismatch as either a CAD change, approved adapter, or rejected part.

### 2. Dry-build the rolling chassis

Assemble without electronics or battery:

1. Install motor mounts loosely, align shafts, then secure using the selected retention method.
2. Install wheels and verify axial/radial clearance through a full rotation.
3. Fit all four wheel and motor assemblies so every tire remains loaded on a level surface and neither diagonal pair rocks.
4. Confirm the frame is not twisted and wheel axes are parallel.
5. Check ground clearance and approach paths at the intended payload.
6. Push the chassis by hand; investigate binding, gear noise, wobble, or asymmetry.

### 3. Fit sensor mounts

| Sensor | Placement rule | Verification |
|---|---|---|
| LiDAR | Scan plane unobstructed; rigid, level, protected without blocking the aperture | Full 360° visualization against known walls; no chassis returns in usable sector unless masked/documented |
| Camera | Rigid mount, lens unobstructed, ribbon within bend limits | Focus, exposure, resolution, optical-frame orientation |
| GNSS antenna | Clear sky view, separated from switching noise and high-current wiring | Cold/warm acquisition and fix stability outdoors |
| IMU | Rigid near chassis body, away from heat/vibration/fields; axes measurable | Stationary bias and known-axis rotation checks |
| Ultrasonic | Faces intended hazard region; no cover lip in beam | Known targets across operating range and angles |
| Encoders | Concentric/secure with no contact or missed motion | Counts are repeatable in both directions |

Measure sensor origins and orientation relative to `base_link`; nominal mount geometry is only an initial estimate for URDF.

### 4. Fit electrical hardware

- Use insulating standoffs; prevent solder joints or terminal screws touching structure.
- Keep exposed power terminals guarded and inaccessible to loose hardware.
- Put the fuse close to the battery branch source and make it serviceable.
- Locate the main disconnect and E-stop where a nearby observer can reach them without entering the robot's path.
- Mount the battery against movement in every axis without crushing or puncturing it.
- Preserve Jetson/fan and regulator airflow; avoid recirculating hot motor-driver air.
- Separate high-current/PWM wiring from encoder, I²C, UART, CSI, and GNSS antenna paths.
- Provide drip loops and environmental protection appropriate to the declared indoor/outdoor scope. The baseline robot is not weatherproof.

### 5. Build and label the harness

Build the harness from the reviewed [wiring and pinout](wiring.md), with the battery absent. Use a consistent labeling scheme at both ends, for example `MTR-L+`, `ENC-R-B`, `5V-SENS`, and `GND-LOGIC`. Crimp with the tool specified for the terminal; pull-test sample crimps. Do not tin stranded wire before screw terminals unless the terminal manufacturer explicitly permits it.

Protect cables from:

- wheel/gear/pinch-point ingress;
- sharp sheet edges and fastener threads;
- repeated flex at connectors;
- hot driver/regulator surfaces;
- antenna or sensor field-of-view obstruction.

### 6. Perform unpowered inspection

- [ ] No battery installed; fuse removed; all switches open
- [ ] Fasteners present and retained; no loose metal inside enclosure
- [ ] All four wheels rotate freely; each same-side pair has matched direction and no binding
- [ ] Board standoffs insulating and structurally secure
- [ ] Polarized connectors match the wiring record
- [ ] Continuity from each source to intended load only
- [ ] No unexpected continuity from any rail to chassis or another rail
- [ ] Emergency stop opens the motor branch and its status contact changes independently
- [ ] Camera ribbon orientation checked at both ends
- [ ] Harness clear of fan, wheels, gearbox, sharp edges, and sensor apertures

Two people should independently inspect battery polarity and motor-branch interruption before first power.

## First-power sequence

1. Place the chassis on a stable stand with wheels clear; keep the battery disconnected.
2. Remove motor outputs or motor-branch fuse.
3. Power one regulator/input path from a current-limited bench supply.
4. Confirm current and all destination voltages; shut down and inspect temperature.
5. Add one load at a time: Arduino, Jetson, then sensors.
6. Verify Arduino boot produces no enable/PWM motion state.
7. Verify serial telemetry and diagnostics with the L298N motor rail still absent.
8. Power the L298N logic only as its module design permits; verify outputs remain safe.
9. Connect one motor at a time and energize the motor branch at the lowest practical current limit.
10. Prove E-stop interruption, watchdog timeout, direction, and encoder sign for every motor before connecting the two same-side pairs.

If a current limit trips, diagnose the cause. Raising the limit is not a diagnostic step.

## Mechanical release checklist

A chassis is released for low-speed floor testing only when:

- as-built photos and measured dimensions exist;
- mass and center-of-gravity behavior are acceptable on the declared slope/acceleration envelope;
- motor, wheel, and battery retention have witness marks or an equivalent inspection method;
- wires remain clear during full wheel rotation and handling;
- all sensor frames have measured transforms;
- guards/enclosure prevent accidental contact with energized terminals and pinch points;
- cooling passes the stationary worst-case thermal test;
- emergency stop is visible, labeled, reachable, and proven under motor load.

Re-run relevant checks after any impact, transport, wheel/motor change, battery change, harness repair, or sensor-mount adjustment.
