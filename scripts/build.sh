#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-all}"

build_ros2() (
  [[ -f /opt/ros/jazzy/setup.bash ]] || { echo "ROS 2 Jazzy is required" >&2; return 127; }
  if [[ -n "${ROS_DISTRO:-}" && "$ROS_DISTRO" != "jazzy" ]]; then
    echo "Open a clean shell: ROS $ROS_DISTRO is already sourced, but this target requires Jazzy." >&2
    return 1
  fi
  # shellcheck disable=SC1091
  source /opt/ros/jazzy/setup.bash
  command -v colcon >/dev/null || { echo "colcon is required" >&2; return 127; }
  cd "$ROOT_DIR/ros2_ws"
  colcon build --symlink-install --event-handlers console_direct+
)

build_ros1() (
  [[ -f /opt/ros/noetic/setup.bash ]] || { echo "ROS 1 Noetic is required" >&2; return 127; }
  if [[ -n "${ROS_DISTRO:-}" && "$ROS_DISTRO" != "noetic" ]]; then
    echo "Open a clean shell: ROS $ROS_DISTRO is already sourced, but this target requires Noetic." >&2
    return 1
  fi
  # shellcheck disable=SC1091
  source /opt/ros/noetic/setup.bash
  command -v catkin_make >/dev/null || { echo "catkin_make is required" >&2; return 127; }
  catkin_make -C "$ROOT_DIR/ros1_ws" -DCMAKE_BUILD_TYPE=RelWithDebInfo
)

build_firmware() {
  command -v pio >/dev/null || { echo "PlatformIO Core is required: python3 -m pip install --user platformio" >&2; return 127; }
  pio run -d "$ROOT_DIR/firmware/wildebeest_base"
}

build_docs() {
  command -v mkdocs >/dev/null || { echo "MkDocs Material is required: python3 -m pip install --user mkdocs-material" >&2; return 127; }
  mkdocs build --strict -f "$ROOT_DIR/docs/mkdocs.yml"
}

case "$TARGET" in
  ros2) build_ros2 ;;
  ros1) build_ros1 ;;
  firmware) build_firmware ;;
  docs) build_docs ;;
  all) build_firmware; build_ros2; build_ros1; build_docs ;;
  *) echo "Usage: $0 {ros2|ros1|firmware|docs|all}" >&2; exit 2 ;;
esac
