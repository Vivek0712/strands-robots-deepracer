"""ros2 launch deepracer_deadman deadman.launch.py  (the systemd unit uses ros2 run; this is for hand runs)."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription(
        [Node(package="deepracer_deadman", executable="deadman_node", name="deepracer_deadman", output="screen")]
    )
