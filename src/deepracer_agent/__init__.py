"""Agentic AWS DeepRacer on strands-robots: the laptop side of the car.

Everything here talks to a stock DeepRacer over rosbridge from a Mac with no ROS
installed: a gated Ackermann driver, a heartbeat the on-car deadman listens for,
camera, battery and LED tools, a preflight check and the agent runtime the Pit
Wall portal and the voice agent drive. Physics stops the car; the decider explains.
"""

from __future__ import annotations

__all__ = ["__version__"]
__version__ = "0.1.0"
