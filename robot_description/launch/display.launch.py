import os
import xacro

from launch import LaunchDescription
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    pkg_share = FindPackageShare(
        package="robot_description"
    ).find("robot_description")

    xacro_path = os.path.join(
        pkg_share, "urdf", "robot.urdf.xacro"
    )

    rviz_config_path = os.path.join(
        pkg_share, "rviz", "robot_view.rviz"
    )

    robot_description = xacro.process_file(xacro_path).toxml()

    return LaunchDescription([
        Node(
            package="joint_state_publisher_gui",
            executable="joint_state_publisher_gui",
            name="joint_state_publisher_gui"
        ),
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            parameters=[
                {
                    "robot_description": robot_description
                }
            ]
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen',
            arguments=['-d', rviz_config_path]
        )
    ])