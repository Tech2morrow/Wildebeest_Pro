"""Launch optional Jetson-connected camera, GPS, and 2D lidar drivers."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = get_package_share_directory('wildebeest_bringup')

    def config(filename):
        return PathJoinSubstitution([share, 'config', filename])

    arguments = [
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('start_camera', default_value='false'),
        DeclareLaunchArgument('camera_device', default_value='/dev/video0'),
        DeclareLaunchArgument('start_gps', default_value='false'),
        DeclareLaunchArgument('gps_port', default_value='/dev/wildebeest-gps'),
        DeclareLaunchArgument('start_lidar', default_value='false'),
        DeclareLaunchArgument('lidar_package', default_value='rplidar_ros'),
        DeclareLaunchArgument('lidar_executable', default_value='rplidar_node'),
        DeclareLaunchArgument('lidar_port', default_value='/dev/wildebeest-lidar'),
        DeclareLaunchArgument('lidar_baudrate', default_value='115200'),
    ]

    camera = Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name='v4l2_camera',
        condition=IfCondition(LaunchConfiguration('start_camera')),
        parameters=[
            config('v4l2_camera.yaml'),
            {
                'video_device': LaunchConfiguration('camera_device'),
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            },
        ],
        remappings=[('image_raw', '/camera/image_raw'), ('camera_info', '/camera/camera_info')],
        output='screen',
    )
    gps = Node(
        package='nmea_navsat_driver',
        executable='nmea_serial_driver',
        name='nmea_serial_driver',
        condition=IfCondition(LaunchConfiguration('start_gps')),
        parameters=[
            config('nmea_gps.yaml'),
            {
                'port': LaunchConfiguration('gps_port'),
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            },
        ],
        remappings=[('fix', '/gps/fix'), ('vel', '/gps/vel')],
        output='screen',
    )
    lidar = Node(
        package=LaunchConfiguration('lidar_package'),
        executable=LaunchConfiguration('lidar_executable'),
        name='lidar',
        condition=IfCondition(LaunchConfiguration('start_lidar')),
        parameters=[
            config('rplidar.yaml'),
            {
                'serial_port': LaunchConfiguration('lidar_port'),
                'serial_baudrate': ParameterValue(
                    LaunchConfiguration('lidar_baudrate'), value_type=int
                ),
                'use_sim_time': LaunchConfiguration('use_sim_time'),
            },
        ],
        remappings=[('scan', '/scan')],
        output='screen',
    )
    return LaunchDescription(arguments + [camera, gps, lidar])
