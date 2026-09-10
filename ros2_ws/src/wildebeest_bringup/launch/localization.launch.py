"""Launch local encoder/IMU fusion and optional GNSS global fusion."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    share = get_package_share_directory('wildebeest_bringup')

    def config(filename):
        return PathJoinSubstitution([share, 'config', filename])
    use_sim_time = LaunchConfiguration('use_sim_time')
    gps = LaunchConfiguration('enable_gps_fusion')
    common = {'use_sim_time': use_sim_time}

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('enable_gps_fusion', default_value='false'),
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_local_node',
            parameters=[config('ekf_local.yaml'), common],
            remappings=[('odometry/filtered', '/odometry/filtered')],
            output='screen',
        ),
        Node(
            package='robot_localization',
            executable='navsat_transform_node',
            name='navsat_transform',
            condition=IfCondition(gps),
            parameters=[config('navsat_transform.yaml'), common],
            remappings=[
                ('imu/data', '/imu/data_raw'),
                ('gps/fix', '/gps/fix'),
                ('odometry/filtered', '/odometry/filtered'),
                ('odometry/gps', '/odometry/gps'),
            ],
            output='screen',
        ),
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_global_node',
            condition=IfCondition(gps),
            parameters=[config('ekf_global.yaml'), common],
            remappings=[('odometry/filtered', '/odometry/global')],
            output='screen',
        ),
    ])
