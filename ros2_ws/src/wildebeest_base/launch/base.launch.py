"""Launch only the Arduino base bridge."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    package_share = get_package_share_directory('wildebeest_base')
    default_config = PathJoinSubstitution([package_share, 'config', 'base.yaml'])

    declared_arguments = [
        DeclareLaunchArgument('namespace', default_value=''),
        DeclareLaunchArgument('config', default_value=default_config),
        DeclareLaunchArgument('transport', default_value='serial'),
        DeclareLaunchArgument('serial_port', default_value='/dev/wildebeest-base'),
        DeclareLaunchArgument('baudrate', default_value='115200'),
        DeclareLaunchArgument('release_estop_on_connect', default_value='false'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
    ]

    bridge = Node(
        package='wildebeest_base',
        executable='serial_bridge',
        name='base_controller',
        namespace=LaunchConfiguration('namespace'),
        output='screen',
        emulate_tty=True,
        parameters=[
            LaunchConfiguration('config'),
            {
                'transport': LaunchConfiguration('transport'),
                'port': LaunchConfiguration('serial_port'),
                'baudrate': LaunchConfiguration('baudrate'),
                'release_estop_on_connect': ParameterValue(
                    LaunchConfiguration('release_estop_on_connect'), value_type=bool
                ),
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            },
        ],
    )
    return LaunchDescription(declared_arguments + [bridge])
