"""Launch joystick teleoperation into the command multiplexer."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory('wildebeest_bringup')
    config = PathJoinSubstitution([share, 'config', 'joy_teleop.yaml'])
    return LaunchDescription([
        DeclareLaunchArgument('joy_device_id', default_value='0'),
        Node(
            package='joy',
            executable='joy_node',
            name='joy_node',
            parameters=[config, {'device_id': LaunchConfiguration('joy_device_id')}],
            output='screen',
        ),
        Node(
            package='teleop_twist_joy',
            executable='teleop_node',
            name='teleop_twist_joy_node',
            parameters=[config],
            remappings=[('cmd_vel', '/cmd_vel/teleop')],
            output='screen',
        ),
    ])
