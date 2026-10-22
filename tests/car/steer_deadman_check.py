"""Steering-only check that the deadman's zeros reach the servo node (throttle 0: no wheel motion).

Run from the repo root with the car env sourced: ``python tests/car/steer_deadman_check.py``.
Streams angle 0.5 for 3 s, cuts the heartbeat at 0.7 s, samples pwm1 on the car; prints JSON.
Results 2026-10-14: docs/results/wheels-off-2026-10-14.md section 10.
"""

import json
import os
import sys
import threading
import time

sys.path.insert(0, os.getcwd())
os.environ.setdefault("STRANDS_ROS2_COMMAND_ALLOW", "/manual_drive,/vehicle_state,/enable_state")
os.environ["DEEPRACER_BODY"] = "car"
from deepracer_agent.driver import DeepRacerRobot
from deepracer_agent.transport import (
    SERVO_TYPE,
    DeadmanMonitor,
    HeartbeatPublisher,
    RosbridgeTransport,
    result_text,
)
from tests.car.pwm_sampler import PwmSampler

MID = 1_450_000
TOPIC = "/webserver_pkg/manual_drive"
t = RosbridgeTransport(timeout=8.0)
robot = DeepRacerRobot(t)
mon = DeadmanMonitor(t)
mon.start()
hb = HeartbeatPublisher(t, "steer-check")
sampler = PwmSampler().start()
sampler.measure_one_way()
out = {}
try:
    r = robot.enable()
    print("handshake:", result_text(r)[:80])
    assert r["status"] == "success"
    hb.start()
    print("armed:", mon.wait_for("armed", 4.0), mon.state)
    m_steer = sampler.mark("steer_start")
    res = {}
    th = threading.Thread(
        target=lambda: res.update(
            t.publish(
                topic=TOPIC, type=SERVO_TYPE, fields={"angle": 0.5, "throttle": 0.0}, count=60, rate=20.0
            )
        )
    )
    th.start()
    time.sleep(0.7)
    m_cut = sampler.mark("hb_cut")
    hb.stop()
    print("tripped:", mon.wait_for("tripped", 2.5), mon.state)
    th.join()
    m_end = sampler.mark("stream_end")
    print("stream:", result_text(res)[:80])
    time.sleep(1.5)
finally:
    t.publish(topic=TOPIC, type=SERVO_TYPE, fields={"angle": 0.0, "throttle": 0.0}, count=1, rate=20.0)
    hb.stop()
    mon.stop()
    samples = sampler.stop()
    t.close()
sampler.wait_mark(m_steer)
sampler.wait_mark(m_cut)
sampler.wait_mark(m_end)
steer = sampler.latency_ms(m_steer, 1, lambda v: v != MID)
out["steer_start_to_pwm1_moves_ms"] = steer
out["pwm1_during_steer_before_cut"] = sorted(
    set(sampler.values_between(m_steer.t_car + 0.25, m_cut.t_car, 1))
)
out["pwm1_after_trip_while_stream_continues"] = sorted(
    set(sampler.values_between(m_cut.t_car + 0.4, m_end.t_car, 1))
)
out["hb_cut_to_first_mid_ms"] = sampler.latency_ms(m_cut, 1, lambda v: v == MID)
out["stream_end_to_mid_ms"] = sampler.latency_ms(m_end, 1, lambda v: v == MID)
out["pwm1_final"] = samples[-1].values[1]
out["pwm0_values_seen"] = sorted(set(s.values[0] for s in samples))
out["trips_state"] = mon.state
print(json.dumps(out, indent=1))
