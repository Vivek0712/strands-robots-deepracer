"""The QA harness: a fake DeepRacer you can run on a laptop with no car in the room.

Three stand-ins that speak the real car's protocols, so the agent, the gate and the portal run
end to end before anyone touches hardware: a fake car that serves the rosbridge WebSocket
protocol and emulates the ctrl node's arming rules (`fake_car`), a fake device console that
serves the MJPEG stream and the console JSON API (`fake_console`), and a fake decider that
answers `/v1/systemone` from the frame currently on the fake camera (`fake_decider`).
`stack.SimStack` starts all three. Physics stops the car; the decider explains: nothing here
is the safety layer, it is the place where the safety layer's assumptions get tested.
"""

from __future__ import annotations

CONTROL_PORT = 8092
CONSOLE_PORT = 8090
DECIDER_PORT = 8111
ROSBRIDGE_PORT = 9091

__all__ = ["CONSOLE_PORT", "CONTROL_PORT", "DECIDER_PORT", "ROSBRIDGE_PORT"]
