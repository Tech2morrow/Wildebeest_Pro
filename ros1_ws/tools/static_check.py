#!/usr/bin/env python3
"""ROS-independent structural checks for the legacy Noetic workspace."""

import pathlib
import re
import sys
import xml.etree.ElementTree as ET


WORKSPACE = pathlib.Path(__file__).resolve().parents[1]
SOURCE = WORKSPACE / "src"
EXPECTED_PACKAGES = {
    "wildebeest_base",
    "wildebeest_bringup",
    "wildebeest_description",
    "wildebeest_navigation",
    "wildebeest_simulation",
}


def fail(message):
    raise AssertionError(message)


def package_inventory():
    packages = {}
    for manifest in SOURCE.glob("*/package.xml"):
        root = ET.parse(str(manifest)).getroot()
        name = root.findtext("name")
        if not name:
            fail("{} has no package name".format(manifest))
        if root.findtext("version") != "0.1.0":
            fail("{} must use workspace version 0.1.0".format(manifest))
        maintainer = root.find("maintainer")
        if maintainer is None or maintainer.attrib.get("email") != "maintainers@wildebeest-pro.org":
            fail("{} has inconsistent maintainer metadata".format(manifest))
        if name in packages:
            fail("duplicate package name {}".format(name))
        packages[name] = manifest.parent
    if set(packages) != EXPECTED_PACKAGES:
        fail("package set is {}, expected {}".format(sorted(packages), sorted(EXPECTED_PACKAGES)))
    return packages


def validate_xml():
    suffixes = {".xml", ".launch", ".xacro", ".world"}
    checked = 0
    for path in SOURCE.rglob("*"):
        if path.is_file() and path.suffix in suffixes:
            try:
                ET.parse(str(path))
            except ET.ParseError as exc:
                fail("invalid XML in {}: {}".format(path.relative_to(WORKSPACE), exc))
            checked += 1
    if checked < 10:
        fail("unexpectedly few XML files: {}".format(checked))
    return checked


def validate_local_find_references(packages):
    pattern = re.compile(r"\$\(find\s+([A-Za-z0-9_]+)\)/([^'\"\s<]+)")
    checked = 0
    for path in SOURCE.rglob("*"):
        if not path.is_file() or path.suffix not in {".launch", ".xacro"}:
            continue
        text = path.read_text(encoding="utf-8")
        for package, relative in pattern.findall(text):
            if package in packages:
                target = packages[package] / relative
                if not target.exists():
                    fail("{} references missing {}".format(path.relative_to(WORKSPACE), target))
                checked += 1
    return checked


def validate_demo_map():
    pgm = SOURCE / "wildebeest_navigation" / "config" / "maps" / "demo.pgm"
    tokens = []
    for line in pgm.read_text(encoding="ascii").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            tokens.extend(line.split())
    if tokens[0] != "P2":
        fail("demo map must be an ASCII PGM")
    width, height, maximum = map(int, tokens[1:4])
    pixels = list(map(int, tokens[4:]))
    if len(pixels) != width * height:
        fail("demo map has {} pixels, expected {}".format(len(pixels), width * height))
    if maximum != 255 or min(pixels) < 0 or max(pixels) > maximum:
        fail("demo map pixel range is invalid")


def validate_canonical_defaults():
    expected = {
        "wildebeest_base/config/base.yaml": (
            "wheel_radius_m: 0.033622",
            "wheel_width_m: 0.025065",
            "wheel_separation_m: 0.121843",
            "wheelbase_m: 0.117150",
            "encoder_ticks_per_revolution: 600",
            "mcu_watchdog_s: 0.30",
            "require_estop_clear_after_boot: true",
            "max_linear_m_s: 0.45",
            "max_angular_rad_s: 1.80",
            "front_left_wheel_joint",
            "rear_right_wheel_joint",
        ),
        "wildebeest_simulation/config/controllers.yaml": (
            "left_wheel: [front_left_wheel_joint, rear_left_wheel_joint]",
            "right_wheel: [front_right_wheel_joint, rear_right_wheel_joint]",
            "wheel_separation: 0.121843",
            "wheel_radius: 0.033622",
            "max_velocity: 0.45",
            "max_velocity: 1.80",
        ),
        "wildebeest_description/urdf/wildebeest.urdf.xacro": (
            'name="base_length" value="0.257"',
            'name="base_width" value="0.150"',
            'name="base_height" value="0.031"',
            'name="wheel_radius" value="0.033622"',
            'name="wheel_width" value="0.025065"',
            'name="wheel_separation" value="0.121843"',
            'name="wheelbase" value="0.117150"',
            'position="front" side="left"',
            'position="rear" side="left"',
            'position="front" side="right"',
            'position="rear" side="right"',
        ),
        "wildebeest_bringup/config/twist_mux.yaml": (
            "topic: /cmd_vel/remote",
            "timeout: 0.35",
            "priority: 40",
        ),
        "wildebeest_bringup/launch/robot.launch": (
            "arg('localization').lower() != 'true'",
            "arg('navigation').lower() == 'true' and arg('mapping').lower() != 'true'",
        ),
        "wildebeest_simulation/launch/gazebo.launch": (
            'name="z" default="0.035"',
        ),
    }
    for relative, needles in expected.items():
        content = (SOURCE / relative).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in content:
                fail("{} is missing canonical value {!r}".format(relative, needle))

    urdf = (SOURCE / "wildebeest_description/urdf/wildebeest.urdf.xacro").read_text(
        encoding="utf-8"
    )
    if "caster" in urdf.lower():
        fail("four-wheel CAD model must not contain caster links")

    bridge = (SOURCE / "wildebeest_base/scripts/serial_bridge_node.py").read_text(
        encoding="utf-8"
    )
    for joint in (
        "front_left_wheel_joint",
        "rear_left_wheel_joint",
        "front_right_wheel_joint",
        "rear_right_wheel_joint",
    ):
        if joint not in bridge:
            fail("base bridge does not publish {}".format(joint))
    for safety_needle in (
        "FLAG_HARD_ESTOP | FLAG_SOFT_ESTOP",
        "self.controller_stop_latched = True",
        "self._invalidate_motion(now)",
        "controller_boot_is_supported(frame.sequence, identity, version)",
        "self.controller_ready = False",
        "if not self.controller_ready:",
        "self.estop_clear_pending = True",
        "Controller confirmed ESTOP clear; waiting for a fresh cmd_vel",
        'rospy.Subscriber("/cmd_vel"',
        '"/wildebeest/estop", Bool',
    ):
        if safety_needle not in bridge:
            fail("base bridge is missing safety behavior {!r}".format(safety_needle))
    if "self.motion_ready_after = self.last_pong_monotonic" in bridge:
        fail("PONG must never open the motion gate")


def validate_wheel_joint_parity():
    urdf = (SOURCE / "wildebeest_description/urdf/wildebeest.urdf.xacro").read_text(
        encoding="utf-8"
    )
    calls = re.findall(
        r'<xacro:wheel\s+position="(front|rear)"\s+side="(left|right)"', urdf
    )
    urdf_joints = {"{}_{}_wheel_joint".format(position, side) for position, side in calls}
    expected = {
        "front_left_wheel_joint",
        "rear_left_wheel_joint",
        "front_right_wheel_joint",
        "rear_right_wheel_joint",
    }
    if urdf_joints != expected:
        fail("expanded URDF wheel joints are {}, expected {}".format(urdf_joints, expected))

    controller = (
        SOURCE / "wildebeest_simulation/config/controllers.yaml"
    ).read_text(encoding="utf-8")
    controller_joints = set()
    for side in ("left", "right"):
        match = re.search(r"^\s*{}_wheel:\s*\[([^]]+)\]".format(side), controller, re.MULTILINE)
        if not match:
            fail("simulation controller has no {} multi-wheel list".format(side))
        controller_joints.update(name.strip() for name in match.group(1).split(","))
    if controller_joints != expected:
        fail("controller wheel joints do not match the URDF: {}".format(controller_joints))

    base_config = (SOURCE / "wildebeest_base/config/base.yaml").read_text(encoding="utf-8")
    configured_joints = set()
    for side in ("left", "right"):
        match = re.search(
            r"^{}_wheel_joint_names:\s*\[([^]]+)\]".format(side),
            base_config,
            re.MULTILINE,
        )
        if not match:
            fail("base config has no {} wheel joint list".format(side))
        configured_joints.update(name.strip() for name in match.group(1).split(","))
    if configured_joints != expected:
        fail("hardware joint-state names do not match the URDF: {}".format(configured_joints))

    gazebo = (
        SOURCE / "wildebeest_description/urdf/wildebeest.gazebo.xacro"
    ).read_text(encoding="utf-8")
    for joint in expected:
        link = joint.replace("_joint", "_link")
        if link not in gazebo:
            fail("Gazebo properties are missing {}".format(link))


def validate_python_syntax():
    checked = 0
    for path in WORKSPACE.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        try:
            compile(source, str(path), "exec")
        except SyntaxError as exc:
            fail("invalid Python in {}: {}".format(path.relative_to(WORKSPACE), exc))
        checked += 1
    return checked


def main():
    packages = package_inventory()
    xml_count = validate_xml()
    reference_count = validate_local_find_references(packages)
    validate_demo_map()
    validate_canonical_defaults()
    validate_wheel_joint_parity()
    python_count = validate_python_syntax()
    print(
        "Static checks passed: {} packages, {} XML files, {} local references, {} Python files".format(
            len(packages), xml_count, reference_count, python_count
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        sys.exit(1)
