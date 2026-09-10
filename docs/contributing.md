# Contributing

Contributions are welcome across firmware, ROS 1, ROS 2, simulation, hardware and documentation. This is a physical robotics project: changes that compile can still create motion, battery, thermal or collision hazards. Reviews therefore require scope-appropriate evidence and synchronized contracts.

## Before starting

1. Search existing issues and state the user problem, robot/ROS profile and intended evidence.
2. Separate unrelated changes. A protocol revision, CAD redesign and navigation retune should not arrive as one opaque patch.
3. Identify affected safety claims, interfaces, calibration and acceptance stages.
4. Do not include proprietary CAD libraries, vendor files, personal data, credentials or assets without a compatible redistribution right.

## Development environments

### Tool-only changes

```bash
python3 -m unittest discover -s tools/tests -v
python3 tools/robot_doctor.py
```

### ROS 2 Jazzy

```bash
source /opt/ros/jazzy/setup.bash
./scripts/bootstrap.sh ros2
./scripts/build.sh ros2
cd ros2_ws
colcon test --event-handlers console_direct+
colcon test-result --verbose
```

### ROS 1 Noetic

```bash
source /opt/ros/noetic/setup.bash
./scripts/bootstrap.sh ros1
./scripts/build.sh ros1
cd ros1_ws
catkin_make run_tests
catkin_test_results
```

Noetic is end-of-life; changes must not silently weaken the ROS 2 path to accommodate it.

### Firmware

```bash
pio run -d firmware/wildebeest_base
```

Upload only with motor power removed and the robot restrained. A firmware PR should include host-side tests wherever behavior can be modeled without hardware.

### Documentation

The Material for MkDocs configuration is intentionally inside `docs/`:

```bash
python3 -m pip install mkdocs-material
./scripts/build.sh docs
mkdocs serve -f docs/mkdocs.yml
mkdocs build --strict -f docs/mkdocs.yml
```

Check links, tables, tabs, Mermaid diagrams, admonitions, code wrapping and mobile/dark-mode rendering. Never mark a physical test as passed based on a documentation build.

## Interface stability

The following are public contracts:

- serial frame grammar, CRC, schemas, limits, status bits and watchdog behavior;
- ROS topic/service names, message types, fields, units and signs;
- TF frame/joint names and ownership;
- launch arguments and parameter meanings;
- real/mock/simulation mode selection;
- hardware pin map and fail-safe E-stop sense logic.

A breaking change requires a migration note, protocol/config version strategy, synchronized firmware/tools/ROS 1/ROS 2/simulation/docs changes, and a failure-safe mismatch test.

## Change-specific evidence

| Change | Minimum evidence |
|---|---|
| Protocol/parser | Golden vectors, invalid/boundary/fuzz tests in every implementation, watchdog non-refresh proof |
| Firmware motion/control | Build, unit/model tests, stand logs, boot/stop/reset/fault injection, timing/resource report |
| ROS base bridge | Mock tests, fragmented/reconnect/reset/stale telemetry tests, topic/service/diagnostic contract |
| URDF/Xacro | Parser check, connected tree, screenshots, dimensions/inertias provenance, collision review |
| Sensor driver/config | Exact part/driver version, rate/frame/timestamp/covariance/disconnect evidence |
| Localization/navigation | Bags/worlds, ground-truth method, parameter diff, scenario metrics, stale/fault behavior |
| Electrical design | Schematic, calculations, exact parts, protection/current/thermal tests, reviewed as-built photos |
| Mechanical design | Dimensioned drawing, units/material/tolerances, fit/clearance/load/retention evidence |
| Documentation-only | Strict site build, link check and technical review |

State tests not run and why. Never imply hardware validation from mock data.

## Coding and configuration guidance

- Keep the Arduino control loop nonblocking and bound memory/serial processing.
- Use fixed-width integers and explicit units at boundaries.
- Reject invalid motion input; do not coerce it into a plausible command.
- Keep software stop and watchdog paths simple, observable and independently tested.
- Use SI units in ROS and suffix non-SI protocol/config fields with their units.
- Give one node ownership of each command topic and TF edge.
- Treat parameter examples as uncalibrated until tied to a configuration record.
- Avoid absolute paths, developer usernames, port enumeration assumptions and secrets.
- Log enough identity/state for diagnosis without flooding storage or exposing private data.
- Maintain equivalent behavior in ROS 1/ROS 2 where the interface contract promises it.

## Hardware and CAD contributions

Do not infer dimensions or ratings from rendered images or filenames. Include source and neutral exchange formats where licensing permits, a drawing/revision, units, tolerances, material/process, mass where relevant, and a note identifying measured versus nominal geometry.

Hardware substitutions that affect voltage/current, pinout, logic level, thermals, device identity, driver, sensor origin, mass or calibration require a new hardware revision and affected acceptance tests.

## Documentation language

Use these terms consistently:

- **verified** — supported by linked evidence on the stated revision;
- **implemented** — code/design exists but may not be physically verified;
- **target** — intended integration behavior;
- **placeholder** — example value that must not authorize operation;
- **TBD** — unresolved requirement/value with no implied default;
- **hard E-stop** — independent electrical motor-energy interruption;
- **software stop** — command/state function that cannot replace the hard E-stop.

Write procedures as observable gates. Include warnings immediately before the hazardous action, not only in a general safety page.

## Pull-request checklist

- [ ] Scope and user-visible outcome explained
- [ ] Safety/interface/calibration impact identified
- [ ] Generated and unrelated files excluded
- [ ] Tests added and commands/results reported
- [ ] ROS 1/ROS 2 parity considered
- [ ] Firmware/tools/protocol/docs updated together where required
- [ ] Mock/simulation versus physical evidence clearly labeled
- [ ] New parameters have units, range, default rationale and validation path
- [ ] Hardware claims cite the exact datasheet/revision
- [ ] No secrets, personal/private location data or unlicensed assets included
- [ ] Documentation builds strictly and links resolve
- [ ] Affected acceptance stages listed for re-run

## Review and release

Reviewers should reproduce software tests, challenge unsafe defaults and hidden assumptions, and require physical evidence proportional to risk. A release states supported OS/ROS profiles, protocol version, hardware revisions, known limitations, calibration status, highest acceptance stage passed and unresolved safety-critical issues.

Repository releases do not certify a user's as-built robot.
