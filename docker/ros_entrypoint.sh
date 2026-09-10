#!/usr/bin/env bash
set -e
if [[ -f /opt/ros/jazzy/setup.bash ]]; then
  source /opt/ros/jazzy/setup.bash
  [[ -f /wildebeest/ros2_ws/install/setup.bash ]] && source /wildebeest/ros2_ws/install/setup.bash
elif [[ -f /opt/ros/noetic/setup.bash ]]; then
  source /opt/ros/noetic/setup.bash
  [[ -f /wildebeest/ros1_ws/devel/setup.bash ]] && source /wildebeest/ros1_ws/devel/setup.bash
fi
exec "$@"
