# Voice rehearsal (nova-sonic, amazon.nova-2-5-sonic): PASS

pre-grant: `STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`; auto-approve: True

## Steps
- [PASS] Nova Sonic connection open: 3 ms
- [PASS] preflight (arms the heartbeat): go
- [PASS] hop utterance streamed while pressed: 24 frames, 2.323 s
- [PASS] hop: rover finished speaking before the next press: 1.68 s heard
- [PASS] hop: user transcript heard: hop forward twenty centimeters.
- [PASS] hop: gated drive produced motion events: 2 motion events, verdicts ['Confirm', 'Proceed'], tools ['drive_deepracer']
- [PASS] roll: the rover called a tool for the roll: drive_deepracer
- [PASS] roll: rover is narrating (new spoken response): audio starts 1 -> 2, 1.84 s heard
- [PASS] stop: BidiBargeInEvent reached BargeInStop: press -> barge-in 971 ms (voice clock), BargeInStop {'t_ms': 969, 'stop_t_ms': 971, 'latency_ms': 1, 'error': None}
- [PASS] stop: stop event with cause barge_in logged: {"request_id": null, "cause": "barge_in", "latency_ms": 1}

## Transcript
    you> hop forward twenty centimeters.
    rover> I moved forward for half a second.
    you> roll forward slowly for two seconds and describe the pen.
    rover> I am rolling forward and I see two faint white lines on a dark background.
    you> stop.
    rover> I have stopped.

## Red Light latencies
- press -> BidiBargeInEvent: 971 ms (voice clock), 972 ms (wall)
- barge-in -> stop_all returned: 1 ms
- press -> stop: 971 ms
