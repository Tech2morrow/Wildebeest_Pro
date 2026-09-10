#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STRICT="${WILDEBEEST_STRICT_TOOLS:-0}"
fail_or_skip() {
  if [[ "$STRICT" == "1" ]]; then echo "$1 is required" >&2; return 127; else echo "SKIP: $1 not installed"; fi
}

cd "$ROOT_DIR"
python3 -c 'import yaml' >/dev/null 2>&1 || {
  echo "PyYAML is required: python3 -m pip install -r requirements-ci.txt" >&2
  exit 127
}
python3 -m unittest discover -s tools/tests -v
python3 tools/robot_doctor.py
python3 ros1_ws/tools/run_checks.py
python3 ros2_ws/scripts/validate_workspace.py

if command -v node >/dev/null; then node --test dashboard/test/*.test.mjs; else fail_or_skip node; fi
if command -v mkdocs >/dev/null; then mkdocs build --strict -f docs/mkdocs.yml; else fail_or_skip mkdocs; fi

if command -v pio >/dev/null; then pio run -d firmware/wildebeest_base; else fail_or_skip pio; fi
if command -v colcon >/dev/null && [[ -f /opt/ros/jazzy/setup.bash ]]; then
  (
    # shellcheck disable=SC1091
    source /opt/ros/jazzy/setup.bash
    cd "$ROOT_DIR/ros2_ws"
    colcon build --symlink-install --event-handlers console_direct+
    # shellcheck disable=SC1091
    source install/setup.bash
    colcon test --event-handlers console_direct+
    colcon test-result --verbose
  )
else fail_or_skip colcon; fi

if command -v catkin_make >/dev/null && [[ -f /opt/ros/noetic/setup.bash ]]; then
  (
    # shellcheck disable=SC1091
    source /opt/ros/noetic/setup.bash
    catkin_make -C "$ROOT_DIR/ros1_ws" -DCMAKE_BUILD_TYPE=RelWithDebInfo
    catkin_make -C "$ROOT_DIR/ros1_ws" run_tests
    catkin_test_results "$ROOT_DIR/ros1_ws/build/test_results"
  )
else fail_or_skip catkin_make; fi
