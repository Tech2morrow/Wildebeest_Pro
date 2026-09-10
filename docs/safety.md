# Safety case

This safety case states the minimum claims and evidence expected for a research prototype. It does not certify Wildebeest Pro under any machinery, battery, radio, automotive, medical, or functional-safety standard. The person or organization building and operating the robot remains responsible for applicable law, standards, workplace rules, and risk assessment.

## Safety objective

The prototype should remain de-energized or stopped by default, limit the energy and area of supervised tests, detect common stale/faulted states, and provide a hardware means to remove motor energy independent of software.

## Safety claims and current evidence

| ID | Claim | Design mechanism | Repository evidence | Physical evidence required |
|---|---|---|---|---|
| S-01 | Motor energy can be removed independently of software | Rated NC main E-stop contact in motor branch | Wiring requirement only | Continuity and loaded interruption test on as-built harness |
| S-02 | Broken E-stop sense wiring is detected | Separate NC auxiliary contact: A1 `LOW` healthy, open/`HIGH` asserted | Firmware input/pull-up and status flag | Press, unplug and single-wire-break tests |
| S-03 | MCU starts stopped | Watchdog flag initialized; outputs disabled until valid command | Firmware source/tests | Scope/driver-output test across power/reset states |
| S-04 | Lost host commands stop motion | Independent 300 ms MCU command watchdog | Firmware source/protocol tests | USB pull/process kill under load; measured stop timing |
| S-05 | Software stop overrides commands | Latched software-stop state | Firmware/bridge behavior | Service, reconnect and race-condition tests |
| S-06 | Commands are bounded | Firmware rejects commands beyond configured ceilings | Parser/tests | Confirm final limits safe for mass/surface/environment |
| S-07 | Corrupt commands do not actuate | Length/schema/range/CRC validation | Cross-language codec tests | Serial fault injection with outputs observed |
| S-08 | Only one source controls the base | Velocity multiplexer and topic ownership contract | Launch/graph tests | Pre-run graph audit |
| S-09 | Low battery cannot silently corrupt control | Monitoring plus pack protection and stop policy | Monitoring code; stop disabled until calibrated | Divider safety, threshold, BMS and brownout tests |
| S-10 | Stale critical sensing blocks autonomy | Driver diagnostics and navigation configuration requirement | Configuration/tests where implemented | Sensor disconnect tests at operating speed |

“Repository evidence” means design intent or software behavior under test. It does not close the physical claim.

## Hazard register

| Hazard | Causes | Required controls | Residual decision owner |
|---|---|---|---|
| Unexpected/runaway motion | Bad command, reversed feedback, process/USB failure, boot transient, driver fault | Hard motor disconnect, MCU watchdog, boot-safe outputs, command bounds, stand testing, exclusion zone, observer | Test lead |
| Crush/pinch/collision | Wheels, gears, chassis momentum, autonomous planner | Guards, low staged limits, controlled area, reachable E-stop, no people in path | Operator/site owner |
| Fall from edge/stairs | Map/sensor/localization failure | Physical barriers; never rely only on perception/geofence | Site owner |
| Battery fire/venting | Damaged/counterfeit cells, short, wrong charger, overcurrent/temperature | Traceable protected pack, correct charger, fuse, enclosure, inspection, site incident plan | Electrical safety owner |
| Electrical damage/fire | Polarity error, undersized wire, regulator fault, backfeed, loose terminal | Reviewed schematic, branch protection, current-limited first power, rated wiring/connectors, guards, thermal tests | Electrical safety owner |
| Compute brownout/reset | Motor transient, inadequate regulator, wiring drop | Separate/engineered rails, power budget, scope transients, reset-aware host, stopped MCU default | Integration owner |
| Thermal injury/failure | L298N/regulator/Jetson overload, blocked fan | Thermal margin, airflow, limits, shutdown criteria, guarded hot surfaces | Integration owner |
| Sensor-induced unsafe navigation | Blind spot, glare, crosstalk, multipath, stale timestamps | Multi-layer sensing, freshness/quality gates, conservative speed, scenario tests, operator | Autonomy owner |
| Cyber/unintended network command | Open ROS graph, wrong domain/master, compromised host | Isolated trusted network, firewall/security configuration, graph audit, physical stop | System owner |
| Data/privacy exposure | Camera images, GNSS tracks, network/bag logs | Consent, minimization, access/retention controls, redaction | Data owner |
| Mechanical ejection/failure | Loose wheel/battery/fastener, cracked printed part | Retention, inspection marks, material/process evidence, impact checks | Mechanical owner |

Add site-specific hazards. A risk matrix is meaningful only when severity/likelihood definitions and acceptance authority are declared by the operating organization.

## Non-negotiable controls

### Hard emergency stop

- The motor-energy interruption works with Jetson, Arduino and software absent or frozen.
- The main contact is normally closed in the healthy/released state and opens when pressed.
- A mechanically linked, isolated NC auxiliary contact closes A1 to Arduino ground while healthy. Pressed, disconnected, or broken-wire state opens it; `INPUT_PULLUP` reads `HIGH` and firmware inhibits motion.
- The E-stop is latching, visible, labeled, reachable by the observer, and reset does not itself create motion.
- Contact/interrupt ratings and DC behavior are established from the selected device and expected fault current.

If the available button cannot provide the required independent contacts and ratings, use a properly designed contactor/relay/safety device. Do not improvise motor current through a panel switch or GPIO.

### Protection and isolation

- A fuse/overcurrent device is close to the energy source and protects the downstream conductor/connector envelope.
- A service disconnect enables safe maintenance.
- Battery/BMS protection is present but is not used as the normal on/off control.
- Motor return current does not flow through logic boards or signal conductors.
- Regulators are set with loads disconnected and validated for transients/thermal conditions.
- Exposed terminals and rotating/pinch parts are guarded.

### Software defaults

- No motion at MCU boot, reset, serial connect, ROS launch, estimator reset or E-stop reset.
- Commands expire; no “last command forever.”
- Invalid packets are rejected and diagnosed.
- Simulation and hardware drivers cannot both control one base.
- Navigation stops on stale mandatory transform/sensor/odometry data.
- Recovery after a stop is deliberate and requires a fresh command.

## Battery rules

- Use a traceable, professionally assembled protected pack and approved charger.
- Follow manufacturer limits for storage, charge, discharge, temperature, inspection and disposal.
- Never charge unattended or while the robot is operating.
- Do not charge a damaged, swollen, wet, hot, deeply discharged or suspect pack.
- Prevent reverse connection, abrasion, crushing, puncture and conductor shorting.
- Define a site-specific isolation/fire response before bringing the pack into the test area.
- Do not publish generic extinguishing advice as a substitute for the exact pack and facility procedure.

The battery voltage, warning threshold, stop threshold, fuse and wire size remain safety-critical TBDs until supported by the actual pack/load design. Default firmware voltage values and divider components are commissioning aids, not validated pack protection.

## Operating limits

The following must be measured and approved in the configuration record before floor operation:

- maximum linear/angular velocity and acceleration;
- stopping distance on each authorized surface and battery/load condition;
- maximum slope, step/edge exposure and payload;
- minimum sensor freshness/quality and obstacle size/distance;
- compute/motor-driver/regulator temperature and current limits;
- minimum safe radio/network quality where remote commands are used;
- indoor/outdoor, light, dust, moisture and ambient-temperature envelope.

Until then, the robot remains a restrained bench prototype.

## Safety validation

Perform failures rather than assuming them:

- press E-stop and break/unplug the auxiliary sense loop;
- remove USB and kill the base bridge at low speed;
- send truncated, bad-CRC, duplicate, delayed and out-of-range serial frames;
- reset Arduino and Jetson independently;
- disconnect each encoder and critical sensor;
- pause/stall clocks and inject stale timestamps in simulation/replay;
- block the fan and approach thermal thresholds only under a controlled non-damaging test plan;
- introduce motor load/transients with current limiting and scope the compute rail;
- attempt launch with duplicate TF/command publishers and require detection.

For every test, record initial state, stimulus, expected safe state, measured response time, final state, logs, video/instrument trace, versions and result.

## Stop-work conditions

Stop, isolate and label the robot out of service after:

- unexpected motion or failure of any stop layer;
- damaged/swollen/hot battery or unexplained power odor/noise;
- blown fuse without known benign test cause;
- recurring brownout, watchdog, CRC, encoder or sensor freshness faults;
- loose wheel, motor, battery, sensor, board or structural crack;
- temperature/current outside the approved envelope;
- missing configuration provenance or unreviewed safety-critical change.

Do not “temporarily” bypass a fuse, E-stop, watchdog, diagnostic, limit, or sensor gate to finish a demo.

## Known platform limitations

- Jetson Nano/JetPack 4 is a legacy compute platform and does not natively match the repository's supported ROS 2 Jazzy/Ubuntu 24.04 profile.
- ROS 1 Noetic is end-of-life.
- L298N efficiency, voltage drop, heat and lack of modern diagnostics may be unsuitable for the selected motors.
- MPU6050 lacks an absolute-heading magnetometer.
- NEO-6M-class GNSS is not a safety-rated localization/geofence source and is vulnerable to obstruction/multipath.
- HC-SR04 coverage is narrow/material-dependent and timeout does not mean clear space.
- A single 2D LiDAR plane misses obstacles above/below the plane and transparent/specular/absorptive objects can be difficult.
- IMX219 vision depends on light, focus, exposure and compute latency.
- The baseline has no safety-rated bumper, safety scanner, redundant drive cutoff or certified controller.

These limitations constrain use; they are not merely future feature ideas.
