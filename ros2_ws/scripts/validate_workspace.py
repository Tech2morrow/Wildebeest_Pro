#!/usr/bin/env python3
"""Dependency-light structural checks for the Wildebeest ROS 2 workspace."""

import ast
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


WORKSPACE = Path(__file__).resolve().parents[1]
SOURCE = WORKSPACE / 'src'


def validate_python(errors):
    """Parse every Python source file without importing ROS packages."""

    for path in sorted(WORKSPACE.rglob('*.py')):
        try:
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except (SyntaxError, UnicodeError) as exc:
            errors.append(f'{path.relative_to(WORKSPACE)}: {exc}')


def validate_xml(errors):
    """Parse manifests, Xacro, and SDF as namespace-aware XML."""

    extensions = ('*.xml', '*.xacro', '*.sdf')
    for pattern in extensions:
        for path in sorted(WORKSPACE.rglob(pattern)):
            try:
                ET.parse(path)
            except ET.ParseError as exc:
                errors.append(f'{path.relative_to(WORKSPACE)}: {exc}')


def validate_manifests(errors):
    """Ensure every package has a unique, matching manifest name."""

    names = set()
    manifests = sorted(SOURCE.glob('*/package.xml'))
    if not manifests:
        errors.append('no ROS packages found')
    for manifest in manifests:
        root = ET.parse(manifest).getroot()
        name = root.findtext('name')
        if name != manifest.parent.name:
            errors.append(f'{manifest}: package name {name!r} does not match directory')
        if name in names:
            errors.append(f'duplicate package name: {name}')
        names.add(name)

    base_setup = (SOURCE / 'wildebeest_base' / 'setup.py').read_text(
        encoding='utf-8'
    )
    if "tests_require=['pytest']" not in base_setup:
        errors.append('wildebeest_base setup.py must register its pytest suite')


def validate_yaml(errors):
    """Require PyYAML and load every workspace YAML document."""

    try:
        import yaml
    except ImportError:
        errors.append('PyYAML is required for semantic YAML validation')
        return
    if not hasattr(yaml, 'safe_load') or not hasattr(yaml, 'YAMLError'):
        errors.append('the imported yaml module is not a usable PyYAML installation')
        return
    for path in sorted(WORKSPACE.rglob('*.yaml')):
        try:
            yaml.safe_load(path.read_text(encoding='utf-8'))
        except (yaml.YAMLError, UnicodeError) as exc:
            errors.append(f'{path.relative_to(WORKSPACE)}: {exc}')


def validate_map(errors):
    """Check the ASCII example PGM dimensions and sample count."""

    path = SOURCE / 'wildebeest_navigation' / 'maps' / 'example_map.pgm'
    lines = [
        line.strip()
        for line in path.read_text(encoding='ascii').splitlines()
        if line.strip() and not line.lstrip().startswith('#')
    ]
    if not lines or lines[0] != 'P2':
        errors.append('example map must be an ASCII P2 PGM')
        return
    width, height = (int(value) for value in lines[1].split())
    pixels = [int(value) for line in lines[3:] for value in line.split()]
    if len(pixels) != width * height:
        errors.append(
            f'example map declares {width}x{height} but contains {len(pixels)} pixels'
        )
    if any(not 0 <= pixel <= int(lines[2]) for pixel in pixels):
        errors.append('example map contains an out-of-range pixel')


def validate_sensor_materials(errors):
    """Keep sensor visuals distinct without decorating collision geometry."""

    material_path = (
        SOURCE / 'wildebeest_description' / 'urdf' / 'materials.xacro'
    )
    urdf_path = (
        SOURCE / 'wildebeest_description' / 'urdf' / 'wildebeest.urdf.xacro'
    )
    expected = {
        '${prefix}lidar_link': (
            'wildebeest_sensor_lidar_orange', '0.902 0.624 0.000 1.0'
        ),
        '${prefix}imu_link': (
            'wildebeest_sensor_imu_rose', '0.800 0.475 0.655 1.0'
        ),
        '${prefix}gps_link': (
            'wildebeest_sensor_gnss_yellow', '0.941 0.894 0.259 1.0'
        ),
        '${prefix}camera_link': (
            'wildebeest_sensor_camera_sky', '0.337 0.706 0.914 1.0'
        ),
        '${prefix}ultrasonic_front_link': (
            'wildebeest_sensor_ultrasonic_vermillion',
            '0.835 0.369 0.000 1.0',
        ),
    }

    material_root = ET.parse(material_path).getroot()
    definitions = {
        element.get('name'): element.find('color').get('rgba')
        for element in material_root.findall('material')
        if element.get('name') and element.find('color') is not None
    }
    urdf_root = ET.parse(urdf_path).getroot()
    links = {element.get('name'): element for element in urdf_root.findall('link')}
    sensor_materials = {material for material, _ in expected.values()}

    for link_name, (material_name, rgba) in expected.items():
        link = links.get(link_name)
        if link is None:
            errors.append(f'missing sensor link {link_name!r}')
            continue
        visual = link.find('visual')
        material = visual.find('material') if visual is not None else None
        actual_name = material.get('name') if material is not None else None
        if actual_name != material_name:
            errors.append(
                f'{link_name} visual must use {material_name}, got {actual_name!r}'
            )
        if definitions.get(material_name) != rgba:
            errors.append(f'{material_name} must use RGBA {rgba}')
        if any(collision.find('.//material') is not None
               for collision in link.findall('collision')):
            errors.append(f'{link_name} collision geometry must remain uncolored')

    if len(sensor_materials) != len(expected):
        errors.append('every sensor must use a unique named material')
    sensor_colors = {rgba for _, rgba in expected.values()}
    body_colors = {
        rgba for name, rgba in definitions.items() if name not in sensor_materials
    }
    if len(sensor_colors) != len(expected):
        errors.append('every sensor must use a visually unique color')
    if sensor_colors & body_colors:
        errors.append('sensor colors must be distinct from chassis/electronics')
    for link_name, link in links.items():
        if link_name in expected:
            continue
        for material in link.findall('./visual/material'):
            if material.get('name') in sensor_materials:
                errors.append(
                    f'sensor-only material {material.get("name")} reused by {link_name}'
                )


def validate_protocol(errors):
    """Exercise the canonical codec and commissioning command limits."""

    sys.path.insert(0, str(SOURCE / 'wildebeest_base'))
    from wildebeest_base.protocol import (  # pylint: disable=import-outside-toplevel
        ProtocolError,
        crc16_ccitt_false,
        decode_frame,
        encode_cmd,
    )

    if crc16_ccitt_false(b'123456789') != 0x29B1:
        errors.append('CRC-16/CCITT-FALSE check value is incorrect')
    if decode_frame(encode_cmd(1, 0.45, -1.8)).fields != ('450', '-1800'):
        errors.append('canonical command units or limits are incorrect')
    try:
        encode_cmd(2, 0.451, 0.0)
    except ProtocolError:
        pass
    else:
        errors.append('linear commands above 450 mm/s must be rejected')


def validate_robot_contract(errors):
    """Catch geometry, command-routing, readiness, and TF-authority drift."""

    def require(path, fragments):
        text = (WORKSPACE / path).read_text(encoding='utf-8')
        for fragment in fragments:
            if fragment not in text:
                errors.append(f'{path}: missing contract fragment {fragment!r}')
        return text

    urdf = require(
        'src/wildebeest_description/urdf/wildebeest.urdf.xacro',
        [
            'name="wheel_radius" value="0.033622"',
            'name="wheel_width" value="0.025065"',
            'name="wheel_track" value="0.121843"',
            'name="wheelbase" value="0.117150"',
            'name="base_length" value="0.257"',
            'name="base_width" value="0.150"',
            'name="base_height" value="0.031"',
        ],
    )
    if urdf.count('<xacro:drive_wheel ') != 4:
        errors.append('description must instantiate exactly four drive wheels')
    if 'caster' in urdf.lower():
        errors.append('four-wheel skid-steer description must not contain casters')

    gazebo = require(
        'src/wildebeest_description/urdf/wildebeest.gazebo.xacro',
        [
            '<wheel_separation>0.121843</wheel_separation>',
            '<wheel_radius>0.033622</wheel_radius>',
            '<topic>cmd_vel/sim_safe</topic>',
            '<sensor name="wildebeest_front_range" type="gpu_lidar">',
            '<topic>range/front_raw</topic>',
            '<gz_frame_id>${prefix}ultrasonic_front_link</gz_frame_id>',
            '<min_angle>-0.13</min_angle>',
            '<max_angle>0.13</max_angle>',
            '<max>2.0</max>',
        ],
    )
    if gazebo.count('<left_joint>') != 2 or gazebo.count('<right_joint>') != 2:
        errors.append('Gazebo DiffDrive must command two joints on each side')
    if gazebo.count('<joint_name>') != 4:
        errors.append('Gazebo joint-state publisher must cover all four wheels')

    require(
        'src/wildebeest_base/config/base.yaml',
        ['wheel_radius_m: 0.033622', 'wheel_separation_m: 0.121843',
         'left_front_wheel_joint', 'left_rear_wheel_joint',
         'right_front_wheel_joint', 'right_rear_wheel_joint'],
    )
    require(
        'src/wildebeest_bringup/config/twist_mux.yaml',
        ['topic: /cmd_vel/remote'],
    )
    bringup = require(
        'src/wildebeest_bringup/launch/robot.launch.py',
        ["LaunchConfiguration('start_localization')",
         "'publish_odom_tf': ParameterValue",
         "'release_estop_on_connect': ParameterValue"],
    )
    if bringup.count("'publish_odom_tf': ParameterValue") != 1:
        errors.append('bringup must select exactly one raw/EKF odom TF authority')
    if '"\'.lower() == \'mock\'"' not in bringup:
        errors.append('bringup may auto-release E-stop only for the resolved mock transport')
    require(
        'src/wildebeest_bringup/launch/sensors.launch.py',
        ["default_value='rplidar_ros'", "default_value='rplidar_node'",
         "config('rplidar.yaml')"],
    )
    require(
        'src/wildebeest_bringup/package.xml',
        ['<exec_depend>rplidar_ros</exec_depend>'],
    )
    require(
        'src/wildebeest_navigation/config/nav2_params.yaml',
        ['route_server:', 'collision_monitor:', 'docking_server:',
         'cmd_vel_in_topic: cmd_vel_smoothed',
         'cmd_vel_out_topic: /cmd_vel/navigation'],
    )
    navigation_launch = require(
        'src/wildebeest_navigation/launch/navigation.launch.py',
        ["PathJoinSubstitution([nav2_share, 'launch', 'navigation_launch.py'])"],
    )
    if 'SetRemap' in navigation_launch:
        errors.append('Nav2 launch must not bypass its smoother/collision command chain')
    require(
        'src/wildebeest_bringup/config/ekf_local.yaml',
        ['publish_tf: true', 'base_link_frame: base_link'],
    )
    bridge = require(
        'src/wildebeest_gz/config/bridge.yaml',
        ['ros_topic_name: /cmd_vel/sim_safe',
         'ros_topic_name: /range/front_raw',
         'ros_type_name: sensor_msgs/msg/Range'],
    )
    if 'ros_topic_name: /tf' in bridge:
        errors.append('Gazebo bridge must not create a second odom TF authority')
    simulation = require(
        'src/wildebeest_gz/launch/simulation.launch.py',
        ["DeclareLaunchArgument('spawn_z', default_value='0.035')",
         "executable='safety_twist_gate'",
         "executable='range_contract_adapter'"],
    )
    if 'start_localization' in simulation:
        errors.append('Gazebo launch must keep its sole EKF odom TF authority enabled')
    require(
        'src/wildebeest_base/wildebeest_base/serial_bridge_node.py',
        ['validate_controller_boot', 'if not self._controller_ready or self._estopped',
         'def _invalidate_controller(', 'FLAG_PROTOCOL_ERROR'],
    )


def main():
    errors = []
    validate_python(errors)
    validate_xml(errors)
    validate_manifests(errors)
    validate_yaml(errors)
    validate_map(errors)
    validate_sensor_materials(errors)
    validate_protocol(errors)
    validate_robot_contract(errors)
    if errors:
        print('ROS 2 workspace validation failed:')
        for error in errors:
            print(f'  - {error}')
        return 1
    packages = len(list(SOURCE.glob('*/package.xml')))
    print(f'ROS 2 workspace validation passed ({packages} packages).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
