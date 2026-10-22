"""Quick strands-robots check against the real car over rosbridge, then one wheels-off hop.

Uses only upstream strands-robots (``rosbridge_action`` + its command gate). Steps:
  1. status + list_topics (read-only, never gated)
  2. vehicle_state {state: 0} (manual) then enable_state {is_active: true}
  3. publish ServoCtrlMsg {angle 0, throttle T} at 20 Hz for D seconds
  4. ALWAYS publish the zero servo pair afterwards (the car has no watchdog)

Run:  DEEPRACER_HOST=<car-ip> python quick_hop.py [--throttle 0.3] [--duration 0.5] [--dry]
The three command surfaces are pre-granted for this headless run via STRANDS_ROS2_COMMAND_ALLOW,
so no operator prompt appears; every command is still logged to the audit store.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

HOST = os.environ.get("DEEPRACER_HOST", "127.0.0.1")
PORT = int(os.environ.get("DEEPRACER_ROSBRIDGE_PORT", "9090"))
SERVO_TOPIC = "/webserver_pkg/manual_drive"
SERVO_TYPE = "deepracer_interfaces_pkg/ServoCtrlMsg"
VEHICLE_STATE = ("/ctrl_pkg/vehicle_state", "deepracer_interfaces_pkg/ActiveStateSrv")
ENABLE_STATE = ("/ctrl_pkg/enable_state", "deepracer_interfaces_pkg/EnableStateSrv")
RATE = 20.0

# Pre-grant the three command surfaces for this headless script (documented, deliberate).
os.environ.setdefault("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive,/vehicle_state,/enable_state")

from strands_robots._command_gate import gate_command  # noqa: E402
from strands_robots.rosbridge import GATE_TOOL, never_gated, rosbridge_action  # noqa: E402


def gate(kind: str, target: str) -> str | None:
    return gate_command(kind, target, tool_context=None, tool=GATE_TOOL)


def text(r: dict) -> str:
    return " ".join(c.get("text", "") for c in r.get("content", []))[:400]


def call(action: str, **kw) -> dict:
    g = gate if action in ("publish", "service_call") else never_gated
    r = rosbridge_action(action, host=HOST, port=PORT, gate=g, **kw)
    print(f"[{action}] {kw.get('topic') or kw.get('service') or ''} -> {r.get('status')}: {text(r)}")
    return r


def servo(angle: float, throttle: float, count: int) -> dict:
    return call(
        "publish",
        topic=SERVO_TOPIC,
        type=SERVO_TYPE,
        fields={"angle": float(angle), "throttle": float(throttle)},
        count=count,
        rate=RATE,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--throttle", type=float, default=0.3)
    ap.add_argument("--duration", type=float, default=0.5)
    ap.add_argument("--dry", action="store_true", help="read-only: status and topics only")
    a = ap.parse_args()
    if not (0.0 < abs(a.throttle) <= 0.5 and 0.0 < a.duration <= 1.0):
        print("refusing: |throttle| must be in (0, 0.5] and duration in (0, 1] s for a quick hop")
        return 2

    call("status")
    r = call("list_topics", timeout=10)
    if SERVO_TOPIC not in text(r) and "manual_drive" not in json.dumps(r):
        print("WARNING: servo topic not listed yet (rosbridge may not see the DeepRacer graph)")
    if a.dry:
        return 0

    s = call("service_call", service=VEHICLE_STATE[0], type=VEHICLE_STATE[1], fields={"state": 0}, timeout=25)
    e = call(
        "service_call", service=ENABLE_STATE[0], type=ENABLE_STATE[1], fields={"is_active": True}, timeout=25
    )
    if s.get("status") != "success" or e.get("status") != "success":
        print("arming failed; not driving")
        servo(0.0, 0.0, 1)
        return 1

    n = max(1, round(a.duration * RATE))
    print(f"hop: throttle {a.throttle} for {a.duration}s ({n} msgs @ {RATE} Hz) -- wheels OFF the ground")
    t0 = time.monotonic()
    try:
        servo(0.0, a.throttle, n)
    finally:
        z = servo(0.0, 0.0, 1)
        print(f"trailing zero -> {z.get('status')} after {time.monotonic() - t0:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
