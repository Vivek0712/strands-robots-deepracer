"""The deadman rule, as pure arithmetic with no ROS in it, so the laptop can unit-test it.

Once the car has heard one heartbeat from the laptop it is armed and the tail LED
goes green ("go" on stage). If the next heartbeat is more than 300 ms late, the
deadman trips: it tells the node to send ten zero servo pairs at 20 Hz and to turn
the tail LED red. While tripped, any non-zero ``/webserver_pkg/manual_drive`` that
still arrives (a stream that outlived its heartbeat, a stale console slider) is
answered with another zero burst, so the latch holds against a late command too.
Tripped is latched until heartbeats have been arriving steadily for a full second,
then the car is armed again (LED green). If no heartbeat arrives for 30 s the
deadman goes idle, turns the LED off and does nothing, so a car sitting on the
bench is not shouting red all night (the red LED is the trip indicator and only the
trip indicator). Physics stops the car; this is the one stop that survives the
laptop, the Wi-Fi and the router being pulled, and it runs here, on the car, in
Python 3.8.
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional

GAP_TRIP_S = 0.300
RESUME_S = 1.0
IDLE_AFTER_S = 30.0
ZERO_COUNT = 10
ZERO_RATE_HZ = 20.0

STATE_IDLE = "idle"
STATE_ARMED = "armed"
STATE_TRIPPED = "tripped"

ACTION_ZERO = "zero"
ACTION_LED_RED = "led_red"
ACTION_LED_GREEN = "led_green"
ACTION_LED_OFF = "led_off"
ACTION_PUBLISH_STATE = "publish_state"


def iso_utc(epoch_s: float) -> str:
    """Epoch seconds to ``YYYY-MM-DDTHH:MM:SS.mmmZ``."""
    dt = datetime.datetime.fromtimestamp(epoch_s, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


class DeadmanLogic:
    """CONTRACTS section 3 deadman rule. Feed it heartbeats and ticks; it returns actions.

    ``now`` is any monotonic clock in seconds; ``wall`` is the wall clock used only
    for the ``since`` timestamp in the published state.
    """

    def __init__(self, now: float, wall: Optional[float] = None) -> None:
        self.state = STATE_IDLE
        self.last_heartbeat = None  # type: Optional[float]
        self.resume_start = None  # type: Optional[float]
        self.trips = 0
        self.rezeros = 0  # zero bursts fired at non-zero manual_drive while tripped
        self._since_wall = wall if wall is not None else now
        self._changed_at = now

    # -- inputs ------------------------------------------------------------------

    def on_heartbeat(self, now: float, wall: Optional[float] = None) -> List[str]:
        """A heartbeat arrived. Returns the actions the node must perform."""
        actions = []  # type: List[str]
        previous = self.last_heartbeat
        self.last_heartbeat = now
        if self.state == STATE_IDLE:
            self._set(STATE_ARMED, now, wall)
            actions.append(ACTION_LED_GREEN)
            actions.append(ACTION_PUBLISH_STATE)
        elif self.state == STATE_TRIPPED:
            # Resume needs a steady second: a gap longer than the trip gap restarts the count.
            if self.resume_start is None or previous is None or (now - previous) > GAP_TRIP_S:
                self.resume_start = now
            elif now - self.resume_start >= RESUME_S:
                self.resume_start = None
                self._set(STATE_ARMED, now, wall)
                actions.append(ACTION_LED_GREEN)
                actions.append(ACTION_PUBLISH_STATE)
        return actions

    def on_manual_drive(self, now: float, angle: float, throttle: float) -> List[str]:
        """A ``manual_drive`` message was seen. While tripped, a non-zero one is zeroed again.

        Zero pairs (the node's own, or the laptop's trailing stop) never count, so the
        deadman cannot argue with itself. Armed and idle ignore the message: the laptop
        is in charge then.
        """
        if self.state != STATE_TRIPPED:
            return []
        if angle == 0.0 and throttle == 0.0:
            return []
        self.rezeros += 1
        return [ACTION_ZERO]

    def tick(self, now: float, wall: Optional[float] = None) -> List[str]:
        """Time passed. Returns the actions the node must perform."""
        actions = []  # type: List[str]
        if self.state == STATE_IDLE or self.last_heartbeat is None:
            return actions
        gap = now - self.last_heartbeat
        if gap >= IDLE_AFTER_S:
            # Idle: nothing to zero, and the LED must not stay red (or green) on an unattended car.
            self.resume_start = None
            self._set(STATE_IDLE, now, wall)
            actions.extend([ACTION_LED_OFF, ACTION_PUBLISH_STATE])
            return actions
        if self.state == STATE_ARMED and gap > GAP_TRIP_S:
            self.trips += 1
            self.resume_start = None
            self._set(STATE_TRIPPED, now, wall)
            actions.extend([ACTION_ZERO, ACTION_LED_RED, ACTION_PUBLISH_STATE])
        return actions

    # -- outputs -----------------------------------------------------------------

    def gap_ms(self, now: float) -> int:
        if self.last_heartbeat is None:
            return 0
        return max(0, int(round((now - self.last_heartbeat) * 1000.0)))

    def state_dict(self, now: float) -> Dict[str, object]:
        return {
            "state": self.state,
            "gap_ms": self.gap_ms(now),
            "since": iso_utc(self._since_wall),
            "trips": self.trips,
        }

    def _set(self, state: str, now: float, wall: Optional[float]) -> None:
        self.state = state
        self._changed_at = now
        self._since_wall = wall if wall is not None else now


def zero_servo_fields() -> Dict[str, float]:
    return {"angle": 0.0, "throttle": 0.0}


def red_led_fields(max_pwm: int = 10000000) -> Dict[str, int]:
    return {"red": max_pwm, "green": 0, "blue": 0}


def green_led_fields(max_pwm: int = 10000000) -> Dict[str, int]:
    return {"red": 0, "green": max_pwm, "blue": 0}


def off_led_fields() -> Dict[str, int]:
    return {"red": 0, "green": 0, "blue": 0}
