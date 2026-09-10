"""Primary physical/mock robot bringup."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    Command,
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    bringup_share = get_package_share_directory('wildebeest_bringup')
    base_share = get_package_share_directory('wildebeest_base')
    description_share = get_package_share_directory('wildebeest_description')
    xacro_file = PathJoinSubstitution(
        [description_share, 'urdf', 'wildebeest.urdf.xacro']
    )
    use_sim_time = LaunchConfiguration('use_sim_time')
    description = ParameterValue(
        Command(['xacro ', xacro_file, ' use_gazebo:=false']),
        value_type=str,
    )

    arguments = [
        DeclareLaunchArgument('use_sim', default_value='false'),
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument(
            'transport',
            default_value=PythonExpression([
                "'mock' if '", LaunchConfiguration('use_sim'),
                "'.lower() == 'true' else 'serial'",
            ]),
        ),
        DeclareLaunchArgument('serial_port', default_value='/dev/wildebeest-base'),
        DeclareLaunchArgument('start_base', default_value='true'),
        DeclareLaunchArgument('start_localization', default_value='true'),
        DeclareLaunchArgument('enable_gps_fusion', default_value='false'),
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

    robot_state = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        parameters=[{'robot_description': description, 'use_sim_time': use_sim_time}],
        output='screen',
    )
    base = Node(
        package='wildebeest_base',
        executable='serial_bridge',
        name='base_controller',
        condition=IfCondition(LaunchConfiguration('start_base')),
        parameters=[
            PathJoinSubstitution([base_share, 'config', 'base.yaml']),
            {
                'transport': LaunchConfiguration('transport'),
                'port': LaunchConfiguration('serial_port'),
                # EKF normally owns odom->base_link. If it is intentionally
                # disabled, raw base odometry becomes the single authority.
                'publish_odom_tf': ParameterValue(
                    PythonExpression([
                        "'", LaunchConfiguration('start_localization'),
                        "'.lower() != 'true'",
                    ]),
                    value_type=bool,
                ),
                # The mock smoke path deliberately auto-releases its host gate;
                # physical bringup remains latched until an operator releases it.
                'release_estop_on_connect': ParameterValue(
                    PythonExpression([
                        "'", LaunchConfiguration('transport'),
                        "'.lower() == 'mock'",
                    ]),
                    value_type=bool,
                ),
                'use_sim_time': use_sim_time,
            },
        ],
        output='screen',
        emulate_tty=True,
    )
    mux = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        parameters=[
            PathJoinSubstitution([bringup_share, 'config', 'twist_mux.yaml']),
            {'use_sim_time': use_sim_time},
        ],
        remappings=[('cmd_vel_out', '/cmd_vel')],
        output='screen',
    )
    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([bringup_share, 'launch', 'localization.launch.py'])
        ),
        condition=IfCondition(LaunchConfiguration('start_localization')),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'enable_gps_fusion': LaunchConfiguration('enable_gps_fusion'),
        }.items(),
    )
    sensors = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([bringup_share, 'launch', 'sensors.launch.py'])
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'start_camera': LaunchConfiguration('start_camera'),
            'camera_device': LaunchConfiguration('camera_device'),
            'start_gps': LaunchConfiguration('start_gps'),
            'gps_port': LaunchConfiguration('gps_port'),
            'start_lidar': LaunchConfiguration('start_lidar'),
            'lidar_package': LaunchConfiguration('lidar_package'),
            'lidar_executable': LaunchConfiguration('lidar_executable'),
            'lidar_port': LaunchConfiguration('lidar_port'),
            'lidar_baudrate': LaunchConfiguration('lidar_baudrate'),
        }.items(),
    )
    return LaunchDescription(arguments + [robot_state, base, mux, localization, sensors])
