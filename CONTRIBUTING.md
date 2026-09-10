# Contributing

Wildebeest Pro welcomes focused fixes, hardware measurements, new sensor
profiles and reproducible test results. Safety-related changes receive the
highest scrutiny.

## Before opening a change

1. Open an issue for changes to wiring, frames, protocol fields or safety
   behavior. Describe the failure mode and how you tested it.
2. Keep ROS 1 and ROS 2 behavior aligned where their APIs permit it. ROS 2 is
   the primary implementation; ROS 1 is frozen legacy compatibility.
3. Never replace a commissioning placeholder with an assumed measurement.
   Include the instrument, method, units, load condition and uncertainty.
4. Do not commit secrets, maps of private locations, recorded camera data or
   ROS bags containing personal information.

## Local checks

```bash
make test
python3 tools/robot_doctor.py
./scripts/build.sh ros2
./scripts/build.sh firmware
```

Use conventional commit subjects where practical (`feat:`, `fix:`, `docs:`,
`test:`). A pull request should state the platform, ROS distribution, sensor
models, test commands and whether physical hardware was involved. Hardware
tests must begin with the wheels raised and a current-limited supply.

## Definition of done

- New behavior has a deterministic simulation or unit test.
- Topic names, frames, parameters and protocol changes are documented.
- Faults produce a stopped or bounded state.
- No claim exceeds the evidence: simulation, bench, raised-wheel, or floor test.
- Relevant ROS 1/ROS 2 configs remain synchronized.
