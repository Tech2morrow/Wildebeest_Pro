# Security and safety policy

## Reporting

Use GitHub's private security-advisory form for vulnerabilities involving
remote command, rosbridge exposure, malformed serial input, denial of service,
unsafe motion, credentials or private sensor data. Do not include exploit
details or real-world location/camera data in a public issue.

For an immediate physical hazard, disconnect motor power and the battery before
collecting logs. Software emergency stops are not safety-rated controls.

## Supported versions

The current `main` branch receives fixes. ROS 2 Jazzy is the primary target.
ROS 1 Noetic is maintained only as best-effort legacy compatibility because the
upstream ROS 1 project is end-of-life.

## Deployment baseline

- Keep rosbridge and DDS/ROS master traffic on a trusted, firewalled network.
- Do not expose port 9090 or the ROS 1 master directly to the Internet.
- Run the robot process without root privileges and grant only serial/video
  device access it needs.
- Use a physical contactor/switch to remove motor energy independently.
- Treat maps, bags, images, GPS fixes and diagnostics as potentially sensitive.
