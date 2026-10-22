# Upstream PR: `from_deepracer()` arms the stock car in manual mode

Branch `fix/deepracer-manual-state` is pushed to `Vivek0712/robots` (commit 7fbc9821 on top of
upstream main d504fedd). The project pins it in `pyproject.toml`. Open the PR against
`strands-labs/robots` main with the text below, then rename
`changelog.d/0000-deepracer-manual-state.md` to `changelog.d/<PR>-deepracer-manual-state.md` and
push again (upstream's check refuses the `0000` placeholder).

```
gh pr create --repo strands-labs/robots --head Vivek0712:fix/deepracer-manual-state \
  --title "fix: from_deepracer() arms the stock DeepRacer in manual mode (state 0)" \
  --body-file docs/dev/upstream-pr-manual-state.md
```

---

## Summary

`AckermannRosRobot.from_deepracer()` sent `vehicle_state {state: 1}`. On the stock DeepRacer
`ctrl_pkg`, 1 is **autonomous** mode: the service answers success, the car then runs its on-board
inference loop and drops every `/webserver_pkg/manual_drive` message. The preset now sends
`state: 0` (manual), the only mode in which `ctrl_pkg` relays manual-drive servo messages to the
servo node. `0 = manual, 1 = autonomous, 2 = calibration` is spelled out in the docstring and the
tests.

## Evidence

Verified on a stock car (`aws-deepracer-core` 2.0.113.0 and 2.0.383.0, Ubuntu 20.04, ROS 2 Foxy,
rosbridge 1.3.1): with `state: 0` then `enable_state {is_active: true}`, a 20 Hz
`ServoCtrlMsg{throttle: 0.3}` stream appears on `/ctrl_pkg/servo_msg` and the throttle PWM moves
1446000 ns to 1405500 ns and back on the trailing zero; the wheels turn. With `state: 1` the
handshake "succeeds" and nothing is relayed.

## Changes

- `strands_robots/drivers/ros/ackermann_robot.py`: preset `fields: {"state": 0}`, docstring
  explains the three modes.
- `tests/mesh/test_ackermann_robot.py`: pinned handshake updated; new
  `test_from_deepracer_handshake_selects_manual_mode` fails if the preset ever selects a
  non-manual mode again.
- `changelog.d/<PR>-deepracer-manual-state.md`: Fixed entry.

## Checklist

- [x] changelog.d fragment, `CHANGELOG.md [Unreleased]` untouched
- [x] `pytest tests/mesh/test_ackermann_robot.py` 50 passed; ruff check and format clean
- [x] No behaviour change for non-DeepRacer users (`init_services` overrides still win)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
