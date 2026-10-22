#!/usr/bin/env bash
# Runs the deadman node with the Foxy, stock DeepRacer and deadman install spaces sourced.
set +u
source /opt/ros/foxy/setup.bash
[ -f /opt/aws/deepracer/lib/setup.bash ] && source /opt/aws/deepracer/lib/setup.bash
source /opt/deepracer-agent/ws/install/setup.bash
exec ros2 run deepracer_deadman deadman_node
