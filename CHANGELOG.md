# Changelog

All notable changes are recorded here. The project follows semantic versioning
once the hardware interface reaches 1.0.

## [Unreleased]

### Added

- Complete ROS 2 Jazzy autonomy workspace and ROS 1 Noetic compatibility workspace.
- CRC-protected Arduino base firmware with command watchdog and E-stop monitoring.
- Differential-drive model, localization/navigation configuration and simulation.
- Offline-capable rosbridge operator dashboard.
- Hardware BOM/commissioning workbook, safety manual and test procedures.
- Reproducible container, dev-container, CI and repository-quality tooling.

### Safety

- Added independent physical motor-power E-stop architecture and low-voltage guidance.
- Reclassified KY-040 modules as unsuitable for dependable wheel odometry.
