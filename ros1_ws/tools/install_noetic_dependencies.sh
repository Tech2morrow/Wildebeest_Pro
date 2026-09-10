#!/usr/bin/env bash
set -euo pipefail

workspace_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f /opt/ros/noetic/setup.bash ]]; then
  echo "ROS Noetic is not installed at /opt/ros/noetic." >&2
  echo "Use an Ubuntu 20.04/ROS Noetic environment; Noetic is EOL and JetPack 4's Ubuntu 18.04 is not a supported binary target." >&2
  exit 2
fi

# shellcheck disable=SC1091
source /opt/ros/noetic/setup.bash
if ! command -v rosdep >/dev/null 2>&1; then
  echo "rosdep is required (normally python3-rosdep)." >&2
  exit 2
fi

rosdep install --from-paths "${workspace_dir}/src" --ignore-src --rosdistro noetic -r -y
echo "ROS 1 workspace dependencies are installed. Build with: cd ${workspace_dir} && catkin_make"
