# Voice rehearsal (fake, scripted): PASS

pre-grant: `STRANDS_ROS2_COMMAND_ALLOW=/manual_drive,/vehicle_state,/enable_state`; auto-approve: True

## Steps
- [PASS] Nova Sonic connection open: 0 ms
- [PASS] hop utterance streamed while pressed: 24 frames, 2.323 s
- [PASS] hop: rover finished speaking before the next press: 0.0 s heard
- [PASS] hop: user transcript heard: Hop forward twenty centimetres
- [PASS] hop: gated drive produced motion events: 2 motion events, verdicts ['Proceed', 'Proceed'], tools ['drive_deepracer']
- [PASS] roll: the rover called a tool for the roll: drive_deepracer
- [PASS] roll: rover is narrating (new spoken response): audio starts 1 -> 2, 0.0 s heard
- [PASS] stop: BidiBargeInEvent reached BargeInStop: press -> barge-in 604 ms (voice clock), BargeInStop {'t_ms': 603, 'stop_t_ms': 604, 'latency_ms': 0, 'error': None}
- [PASS] stop: stop event with cause barge_in logged: {"request_id": null, "cause": "barge_in", "latency_ms": 0}

## Transcript
    you> Hop forward twenty centimetres
    rover> Hopping forward. hopped linear=0.3 angular=0.0 for 0.5s (dry run)
    you> Roll forward slowly for two seconds and describe the pen
    rover> Hopping forward. hopped linear=0.3 angular=0.0 for 0.5s (dry run)
    you> stop
    rover> Stopped. stopped (dry run)

## Red Light latencies
- press -> BidiBargeInEvent: 604 ms (voice clock), 606 ms (wall)
- barge-in -> stop_all returned: 0 ms
- press -> stop: 604 ms
