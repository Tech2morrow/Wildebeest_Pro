"""Spawn Wildebeest Pro in Gazebo Harmonic with ROS topic bridges."""

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = get_package_share_directory('wildebeest_gz')
    description_share = get_package_share_directory('wildebeest_description')
    bringup_share = get_package_share_directory('wildebeest_bringup')
    ros_gz_share = get_package_share_directory('ros_gz_sim')
    world = LaunchConfiguration('world')
    xacro_file = PathJoinSubstitution(
        [description_share, 'urdf', 'wildebeest.urdf.xacro']
    )
    robot_description = ParameterValue(
        Command(['xacro ', xacro_file, ' use_gazebo:=true']),
        value_type=str,
    )

    arguments = [
        DeclareLaunchArgument(
            'world', default_value=PathJoinSubstitution([share, 'worlds', 'test_arena.sdf'])
        ),
        DeclareLaunchArgument('use_rviz', default_value='false'),
        # Wheel centers sit at base_link z=0; add a small spawn clearance.
        DeclareLaunchArgument('spawn_z', default_value='0.035'),
    ]
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([ros_gz_share, 'launch', 'gz_sim.launch.py'])
        ),
        launch_arguments={'gz_args': ['-r -v 3 ', world]}.items(),
    )
    state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description, 'use_sim_time': True}],
        output='screen',
    )
    spawn = TimerAction(
        period=2.0,
        actions=[Node(
            package='ros_gz_sim',
            executable='create',
            arguments=[
                '-name', 'wildebeest_pro',
                '-topic', 'robot_description',
                '-x', '0', '-y', '0', '-z', LaunchConfiguration('spawn_z'),
            ],
            output='screen',
        )],
    )
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='ros_gz_bridge',
        parameters=[{
            'config_file': PathJoinSubstitution([share, 'config', 'bridge.yaml']),
            'use_sim_time': True,
        }],
        output='screen',
    )
    image_bridge = Node(
        package='ros_gz_image',
        executable='image_bridge',
        name='camera_image_bridge',
        arguments=['/camera/image_raw'],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )
    range_adapter = Node(
        package='wildebeest_gz',
        executable='range_contract_adapter',
        name='range_contract_adapter',
        parameters=[{'use_sim_time': True}],
        output='screen',
    )
    safety_gate = Node(
        package='wildebeest_gz',
        executable='safety_twist_gate',
        name='simulation_safety_twist_gate',
        parameters=[{
            'use_sim_time': True,
            'timeout_s': 0.25,
            'publish_rate_hz': 40.0,
        }],
        output='screen',
    )
    mux = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        parameters=[
            PathJoinSubstitution([bringup_share, 'config', 'twist_mux.yaml']),
            {'use_sim_time': True},
        ],
        remappings=[('cmd_vel_out', '/cmd_vel')],
        output='screen',
    )
    localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([bringup_share, 'launch', 'localization.launch.py'])
        ),
        launch_arguments={
            'use_sim_time': 'true',
            'enable_gps_fusion': 'false',
        }.items(),
    )
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        condition=IfCondition(LaunchConfiguration('use_rviz')),
        arguments=[
            '-d',
            PathJoinSubstitution([description_share, 'rviz', 'model.rviz']),
        ],
        parameters=[{'use_sim_time': True}],
        output='screen',
    )
    return LaunchDescription(
        arguments
        + [
            gazebo,
            state_publisher,
            spawn,
            bridge,
            image_bridge,
            range_adapter,
            mux,
            safety_gate,
            localization,
            rviz,
        ]
    )
