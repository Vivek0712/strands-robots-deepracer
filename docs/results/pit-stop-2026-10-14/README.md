# Pit Stop on the stand, 2026-10-14: the race engineer over SSH under the Cedar leash

The pre-recorded beat (council verdict, report 11): the harness SSHes into the car, finds a
6 PWM steering offset against remembered calibration, asks permission under a Cedar policy, fixes
it, drives straight. This folder is the terminal side of that recording, run on the real car on the
stand (wheels off) with `ops/race_engineer.py`: one `create_harness` call with an `SshSandbox` to the
car and `CedarAuthorization` over `ops/pit_stop.cedar`. Model `us.amazon.nova-pro-v1:0` on Bedrock
(`AWS_PROFILE=heisenberg`). The harness is the mechanic, never the driving loop. Nothing here
publishes to a motion topic.

| File | What happened |
|---|---|
| `01-calibration-review.txt` | First review: `read /opt/aws/deepracer/calibration.json` over SSH worked (Motor 1603500 / 1446000 / 1311000 polarity -1; Servo 1700000 / 1450000 / 1200000 polarity 1). `search_memory` was **denied** by the leash, so it could not compare with what it remembered. Finding: the policy only permitted read, web_fetch, shell, write, edit; the engineer's notebook tools were missing. |
| `02-refused-write.txt` | Asked to "fix" the steering mid to 1456000 with the operator NOT confirmed (`DEEPRACER_OPERATOR_CONFIRMED` unset): the `edit` tool call was **refused by Cedar**, the engineer proposed the change and waited. The file on the car was checked afterwards: still `mid 1450000`. |
| `03-calibration-review-with-memory.txt` | After `search_memory`, `retrieve_context` and `todo_write` were permitted (pinned by a new unit test): the engineer reads the file, recalls the expected values from memory and reports the 6000 ns steering offset "without making any changes". |

The "remembered" 1456000 is the staged premise of the beat: it entered the engineer's memory through
the refused-write request in step 2, exactly as a presenter would seed it before the show. It is not
a measured calibration; the car's real steering centre is 1450000 and was not touched.

## Not done here, on purpose

The confirmed path (`DEEPRACER_OPERATOR_CONFIRMED=1`, the edit is allowed, the car drives straight)
writes calibration on the car. That is an operator decision (CLAUDE.md: never write calibration
without asking), so it is left for the recording session with the operator at the keyboard:

```
set -a; . ~/.config/deepracer/env; set +a
AWS_PROFILE=heisenberg AWS_DEFAULT_REGION=us-east-1 DEEPRACER_OPERATOR_CONFIRMED=1 \
  .venv/bin/python -m ops.race_engineer --model us.amazon.nova-pro-v1:0 \
  "Fix the steering mid in /opt/aws/deepracer/calibration.json to the value you remember, then tell me what to check."
```

Restore afterwards with the console's calibration page or by editing the file back to 1450000.
Film it per `docs/results/filming-protocol.md` with the portal's audit panel beside the terminal.

## Fixes that came out of this run

- `SshSandbox` rejects raw `-o` flags: `ssh_options` takes bare `Option=value` strings and
  `allow_unknown_hosts` covers host keys. The unit tests never built the sandbox, so this surfaced
  only on the stand.
- `DEEPRACER_HOST=auto` is resolved by `deepracer_agent.discover` in the race engineer too.
- Cedar: the engineer's notebook actions (`search_memory`, `retrieve_context`, `todo_write`) are
  permitted without confirmation; they never touch the car.
