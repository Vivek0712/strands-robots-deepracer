# Voice with real audio, 2026-10-14 (Nova Sonic, no microphone)

Until today the rover's voice path (`strands.bidi` `BidiAgent` on `amazon.nova-2-5-sonic`, push-to-talk,
barge-in to stop) had only run in `--text` mode. This record is the first end-to-end AUDIO run: speech
synthesized by macOS `say` was streamed into Nova Sonic as 16 kHz PCM through the new
`PcmInputStream`, the model transcribed it, called the gated tools against the fake car, spoke back, and
a "stop" said over its narration came back as a `BidiBargeInEvent` that stopped the wheels. Physics stops
the car; the decider explains. Raw files: `voice-audio-2026-10-14/` (`summary.json`, `summary.md`,
`events.jsonl`, `console.log`, the first attempt's `attempt1-*`, the no-cloud `fake-dryrun-summary.md`).
The synthesized WAVs and the rover's spoken audio stay in the session scratch dir, out of git.

## What ran

```
# fake stack on the Intelligence rehearsal ports, started and stopped by the script (--stack)
DEEPRACER_ROSBRIDGE_PORT=9491  DEEPRACER_CONSOLE_URL=http://127.0.0.1:8490
DEEPRACER_SIM_CONTROL_URL=http://127.0.0.1:8492  DECIDER_URL=http://127.0.0.1:8511
DEEPRACER_SIM_SHARED=<out>/shared.json  DEEPRACER_RUN_DIR=<out>/run  DEEPRACER_BODY=sim
AWS_PROFILE=heisenberg  AWS_DEFAULT_REGION=us-east-1
# pre-grant for this headless run (declared here, logged as approval {by: pregrant} per motion):
STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state

.venv/bin/python -m deepracer_agent.voice_rehearsal --stack --out <scratch>/live --audio-dir <scratch>/audio
```

- Utterances: `say -o x.wav --file-format=WAVE --data-format=LEI16@16000 "<text>"` (16 kHz mono 16-bit;
  `say` writes WAV directly, no `afconvert` needed): "Hop forward twenty centimetres" (1.92 s), "Roll
  forward slowly for two seconds and describe the pen" (3.13 s), "stop" (0.53 s). The player appends
  400 ms of silence before each release so Nova's end-pointer sees the word end while the key is down.
- Agent: `make_voice_agent(runtime.tools, DeciderGate, AgentRuntime(body=sim))`, Nova Sonic voice
  `matthew`, beat prompt `red_light`; `VoiceAgent.run_pcm(PcmInputStream, outputs=[AudioSink])`.
  Between presses the stream sends paced silence frames (100 ms), as an open microphone would.
- `--auto-approve` answered the one decider `Confirm` with yes (no operator at a rehearsal); it is logged
  as `approval {decision: approved, by: operator}` and is the only non-default in the run.
- The second attempt is the record below. The first attempt (`attempt1-*`) exposed a sequencing bug in
  the script, not in the voice path: it played the second utterance while the rover was still speaking
  its reply to the first, Nova reported that as a barge-in (`INTERRUPTED`) and `BargeInStop` stopped the
  (already stopped) car; the later "stop" then arrived while the rover was silent (running `look`) and
  was handled as a normal turn (`stop_deepracer`), so no barge-in was measured. The script now waits for
  1.2 s of rover silence before pressing again and for a *new* spoken response before talking over it.

## Transcript (second attempt, verbatim)

```
you> hop forward twenty centimeters.
tool> drive_deepracer {"angular":0,"duration":0.5,"linear":0.4}
rover> I moved forward for half a second.
you> roll forward slowly for two seconds and describe the pen.
tool> drive_deepracer {"angular":0,"duration":2,"linear":0.1}
tool> look {"question":"Describe the pen."}
-- barge-in --
rover> I am rolling forward and I see two faint white lines on a dark background.
you> stop.
tool> stop_deepracer {}
rover> I have stopped.
```

Nova heard "centimeters" for the British spelling in the prompt and dropped nothing else; every
transcript line is a `voice {event: transcript}` row in `events.jsonl` with `t_ms` from the press.

## Numbers

| Quantity | Value |
|---|---|
| Nova Sonic connection open (`BidiConnectionStartEvent`) | 3 ms after `run_pcm` started (4 ms on attempt 1) |
| hop: press to user transcript | 3157 ms (speech 1.92 s + 0.4 s tail, release at 2302 ms, `speech_start` 2811 ms) |
| hop: verdicts | envelope **Confirm** (`|linear| 0.4 > 0.3 m/s`, p=0.05, 5 ms) then frame Proceed (`clear`, p=0.93, 1 ms); approved; `motion start/end` 0.504 s, 10 messages, throttle 0.3 (the cap) |
| roll: press to transcript | 3995 ms (speech 3.13 s, release 3502 ms) |
| roll: verdicts and motion | Proceed/Proceed, `drive_deepracer linear 0.1, 2.0 s`, 40 messages, 2.006 s; then `look` |
| **stop: press to `BidiBargeInEvent`** | **971 ms** voice clock (972 ms wall); the word itself is 0.53 s and the release came at 902 ms, so Nova reported the interruption 69 ms after the key went up |
| **barge-in to `stop_all` returned** | **1 ms** (fake car; on the real car this was 22 ms this evening, `README.md`) |
| press to stop | 971 ms |
| events written | `voice barge_in t_ms 969`, `stop {cause: operator}` by the driver, `stop {cause: barge_in, latency_ms: 1}` by the agent; 315 ms later `stop {cause: deadman}` from the fake car, because `stop_all` turns the heartbeat off (section 8a) |
| rover audio heard | 6.68 s of 16 kHz PCM (saved as `rover.wav` in scratch); PCM in: 216 926 bytes fed over 3 presses, 0 bytes dropped, 70 speech frames, 108 silence frames |

The barge-in arrived **before** the model's transcript of "stop." (`speech_start` at 1252 ms, transcript
at 1467 ms, `stop_deepracer` tool call at 1468 ms): `BargeInStop` had already zeroed the wheels at 971 ms.
That is the Red Light beat's claim, now measured with audio: the hook on `INTERRUPTED` beats the
transcript-and-tool path by about half a second.

## Observations for the booth

- Nova Sonic over-asked on the hop (`linear 0.4` for "twenty centimetres") and the envelope stage caught
  it as **Confirm**. With a marshal at the portal this is the Apology/Marshal moment; headless it was
  auto-approved and the driver still capped the throttle at 0.3 (`Calibration.throttle_at_max_speed`).
  Consider telling the prompt that 0.3 m/s is the ceiling so the question is not asked for a 20 cm hop.
- After a barge-in stop the fake deadman trips 315 ms later because `stop_all` ends the heartbeat; on
  stage the screen will show `tripped` after every Red Light, as it did on the car this evening.
- The interruption is detected by Nova only while the rover's audio is still being generated/streamed.
  A "stop" said after the model has finished speaking (even if the laptop speaker is still playing the
  buffered tail) is a normal turn and goes through `stop_deepracer`. The on-car deadman and the marshal's
  thumb remain the stop; the voice path is the explanation.
- Unit tests: `tests/unit/test_voice_pcm.py` (15) and `tests/unit/test_portal_ws_audio.py` (9) cover the
  stream, the file player with a fake clock, the sink, the portal's binary `/ws/audio` route and the
  adapter's lazy voice; `.venv/bin/pytest -q tests/unit` is green for every file this work touched. The
  errors in `test_fake_car/console/decider` during this session are `OSError: address in use`: other
  engineers' stacks hold the contract ports 8111/9091 right now; those tests bind fixed ports.

## Portal: browser push-to-talk with audio

`WS /ws/audio` accepts binary 16 kHz mono int16 PCM frames (100 ms, 3200 bytes; 64 KiB cap) while the
button or the space bar is held, carries `{"op":"ptt"}` as text frames on the same socket so the press
always lands before its first frame, and streams the rover's PCM back for playback (`{"op":"barge_in"}`
flushes it). The runtime adapter builds the Nova Sonic `VoiceAgent` on the first press (`PORTAL_VOICE=0`
turns it off; `PORTAL_VOICE_IDLE_S`, default 300, ends an idle connection), buffers the first frames
while the connection comes up, and exposes `voice` in `/api/state` `runtime_status`. The Voice panel
shows a 24-bar RMS level meter, mic/link/voice state and the `voice` events. The JSON `audio` op on `/ws`
still works. Not yet exercised with a real browser microphone in this session (no microphone in the
rehearsal); the capture path (`getUserMedia` -> ScriptProcessor -> box-filter decimation -> int16) built
with `npm run build` and the route is unit-tested with a recorder runtime.
