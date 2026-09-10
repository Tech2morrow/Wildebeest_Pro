#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-ros2}"
case "$TARGET" in
  ros2)
    # shellcheck disable=SC1091
    source /opt/ros/jazzy/setup.bash
    # shellcheck disable=SC1091
    source "$ROOT_DIR/ros2_ws/install/setup.bash"
    exec ros2 launch wildebeest_gz simulation.launch.py
    ;;
  ros1)
    # shellcheck disable=SC1091
    source /opt/ros/noetic/setup.bash
    # shellcheck disable=SC1091
    source "$ROOT_DIR/ros1_ws/devel/setup.bash"
    exec roslaunch wildebeest_simulation demo.launch
    ;;
  *) echo "Usage: $0 {ros2|ros1}" >&2; exit 2 ;;
esac
