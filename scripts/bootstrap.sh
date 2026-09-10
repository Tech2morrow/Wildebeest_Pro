#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-ros2}"

case "$TARGET" in
  ros2)
    TARGET_DISTRO="jazzy"
    SETUP="/opt/ros/$TARGET_DISTRO/setup.bash"
    WORKSPACE="$ROOT_DIR/ros2_ws"
    ;;
  ros1)
    TARGET_DISTRO="noetic"
    SETUP="/opt/ros/$TARGET_DISTRO/setup.bash"
    WORKSPACE="$ROOT_DIR/ros1_ws"
    ;;
  *) echo "Usage: $0 {ros2|ros1}" >&2; exit 2 ;;
esac

if [[ -n "${ROS_DISTRO:-}" && "$ROS_DISTRO" != "$TARGET_DISTRO" ]]; then
  echo "This shell has ROS $ROS_DISTRO sourced, but target '$TARGET' requires $TARGET_DISTRO." >&2
  echo "Open a clean shell before bootstrapping a different ROS distribution." >&2
  exit 1
fi

if [[ ! -f "$SETUP" ]]; then
  echo "ROS $TARGET_DISTRO is not installed at $SETUP." >&2
  echo "Use the matching dev container or follow the official ROS installation guide." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$SETUP"
command -v rosdep >/dev/null || { echo "rosdep is required" >&2; exit 1; }
if [[ ! -f /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  sudo rosdep init
fi
rosdep update
rosdep install --from-paths "$WORKSPACE/src" --ignore-src --rosdistro "$TARGET_DISTRO" -r -y
echo "Dependencies for $TARGET are installed. Run ./scripts/build.sh $TARGET"
