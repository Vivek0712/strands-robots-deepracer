"""rclpy wrapper around DeadmanLogic for ROS 2 Foxy on the stock DeepRacer (Python 3.8).

Subscribes to ``/deepracer_agent/heartbeat`` (std_msgs/Header), ticks the rule at
50 Hz, and when it trips publishes ten zero ``ServoCtrlMsg`` at 20 Hz on BOTH
``/ctrl_pkg/servo_msg`` (straight to the servo node) and ``/webserver_pkg/manual_drive``
(the gated path, so the ctrl node's own copy is zero too). It also listens on
``/webserver_pkg/manual_drive``: while tripped, every non-zero command it hears there
restarts the zero burst, so a stream that outlived its heartbeat cannot win the race
against the latch. State goes out on ``/deepracer_agent/deadman_state`` as JSON at
2 Hz and on every change. The LED goes green when the deadman arms, red on a trip,
green again when heartbeats resume and off when the deadman goes idle, all through
``/servo_pkg/set_led_state``, best effort, never blocking the zeros. Physics stops the car; this node is the part of physics that
lives in software, and it must run as root so FastRTPS shared memory lets it see
the stock nodes.
"""

from __future__ import annotations

import json
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile
from std_msgs.msg import Header, String

from deepracer_deadman.deadman_logic import (
    ACTION_LED_GREEN,
    ACTION_LED_OFF,
    ACTION_LED_RED,
    ACTION_PUBLISH_STATE,
    ACTION_ZERO,
    ZERO_COUNT,
    ZERO_RATE_HZ,
    DeadmanLogic,
    green_led_fields,
    off_led_fields,
    red_led_fields,
)

try:
    from deepracer_interfaces_pkg.msg import ServoCtrlMsg
    from deepracer_interfaces_pkg.srv import SetLedCtrlSrv
except ImportError:  # pragma: no cover - only on a machine without the stock stack
    ServoCtrlMsg = None
    SetLedCtrlSrv = None

HEARTBEAT_TOPIC = "/deepracer_agent/heartbeat"
STATE_TOPIC = "/deepracer_agent/deadman_state"
SERVO_TOPIC = "/ctrl_pkg/servo_msg"
MANUAL_DRIVE_TOPIC = "/webserver_pkg/manual_drive"
LED_SERVICE = "/servo_pkg/set_led_state"
TICK_HZ = 50.0
STATE_HZ = 2.0
LED_TIMEOUT_S = 1.0


class DeadmanNode(Node):
    def __init__(self) -> None:
        super().__init__("deepracer_deadman")
        if ServoCtrlMsg is None:
            raise RuntimeError("deepracer_interfaces_pkg not importable; source /opt/aws/deepracer/lib/setup.bash")
        self.logic = DeadmanLogic(time.monotonic(), time.time())
        qos = QoSProfile(depth=1)
        self._servo_pub = self.create_publisher(ServoCtrlMsg, SERVO_TOPIC, qos)
        self._manual_pub = self.create_publisher(ServoCtrlMsg, MANUAL_DRIVE_TOPIC, qos)
        self._state_pub = self.create_publisher(String, STATE_TOPIC, QoSProfile(depth=5))
        self._hb_sub = self.create_subscription(Header, HEARTBEAT_TOPIC, self._on_heartbeat, QoSProfile(depth=10))
        self._drive_sub = self.create_subscription(
            ServoCtrlMsg, MANUAL_DRIVE_TOPIC, self._on_manual_drive, QoSProfile(depth=10)
        )
        self._led_cli = self.create_client(SetLedCtrlSrv, LED_SERVICE)
        self._led_future = None
        self._led_sent_at = None
        self._zero_remaining = 0
        self._zero_timer = None
        self.create_timer(1.0 / TICK_HZ, self._tick)
        self.create_timer(1.0 / STATE_HZ, self._publish_state)
        self.get_logger().info(
            "deadman up: trip after 300 ms without %s, zeros on %s and %s" % (HEARTBEAT_TOPIC, SERVO_TOPIC, MANUAL_DRIVE_TOPIC)
        )

    # -- inputs ------------------------------------------------------------------

    def _on_heartbeat(self, _msg: Header) -> None:
        self._apply(self.logic.on_heartbeat(time.monotonic(), time.time()))

    def _on_manual_drive(self, msg) -> None:
        # Our own zeros come back here too; the logic ignores zero pairs, so no feedback loop.
        actions = self.logic.on_manual_drive(time.monotonic(), float(msg.angle), float(msg.throttle))
        if actions:
            self.get_logger().warn(
                "tripped and still commanded (angle %.2f throttle %.2f): re-zeroing (%d)"
                % (msg.angle, msg.throttle, self.logic.rezeros)
            )
            self._apply(actions)

    def _tick(self) -> None:
        self._apply(self.logic.tick(time.monotonic(), time.time()))
        self._poll_led()

    # -- actions -----------------------------------------------------------------

    def _apply(self, actions) -> None:
        for action in actions:
            if action == ACTION_ZERO:
                self._start_zero_burst()
            elif action == ACTION_LED_RED:
                self._set_led(red_led_fields())
            elif action == ACTION_LED_GREEN:
                self._set_led(green_led_fields())
            elif action == ACTION_LED_OFF:
                self._set_led(off_led_fields())
            elif action == ACTION_PUBLISH_STATE:
                self._publish_state()
                self.get_logger().warn("deadman -> %s" % self.logic.state) if self.logic.state == "tripped" else self.get_logger().info(
                    "deadman -> %s" % self.logic.state
                )

    def _start_zero_burst(self) -> None:
        self._zero_remaining = ZERO_COUNT
        self._publish_zero()  # the first zero goes out immediately, not a period later
        if self._zero_timer is None:  # a burst already running keeps its timer; only the count is topped up
            self._zero_timer = self.create_timer(1.0 / ZERO_RATE_HZ, self._zero_step)

    def _zero_step(self) -> None:
        if self._zero_remaining <= 0:
            if self._zero_timer is not None:
                self._zero_timer.cancel()
                self._zero_timer = None
            return
        self._publish_zero()

    def _publish_zero(self) -> None:
        msg = ServoCtrlMsg()
        msg.angle = 0.0
        msg.throttle = 0.0
        self._servo_pub.publish(msg)
        self._manual_pub.publish(msg)
        self._zero_remaining -= 1

    def _publish_state(self) -> None:
        msg = String()
        msg.data = json.dumps(self.logic.state_dict(time.monotonic()), separators=(",", ":"))
        self._state_pub.publish(msg)

    def _set_led(self, fields) -> None:
        """Best effort: never waits on the service, never blocks the zero publish."""
        if not self._led_cli.service_is_ready():
            self.get_logger().warn("LED service %s not ready; skipping" % LED_SERVICE)
            return
        req = SetLedCtrlSrv.Request()
        req.red = int(fields["red"])
        req.green = int(fields["green"])
        req.blue = int(fields["blue"])
        self._led_future = self._led_cli.call_async(req)
        self._led_sent_at = time.monotonic()

    def _poll_led(self) -> None:
        if self._led_future is None:
            return
        if self._led_future.done():
            self._led_future = None
        elif time.monotonic() - self._led_sent_at > LED_TIMEOUT_S:
            self.get_logger().warn("LED service call timed out after %.1fs (ignored)" % LED_TIMEOUT_S)
            self._led_future = None


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DeadmanNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
