# Decider benchmark: strands-decider-E2B-gemma4-v1-2610

- URL `http://127.0.0.1:8113`, device `mps`, vision `True`, checkpoint `StrandsAgents/strands-decider-E2B-gemma4-v1-2610`
- 2026-10-14T07:02:14Z, repeats 10 per frame/case (warm-up excluded), client timeout 10.0 s, wall 148.5 s
- machine macOS-15.7-arm64-arm-64bit (arm64)
- extra: load_s=19.2, footprint_mb_after_load=11.0, serve_cmd=strands-decider serve StrandsAgents/strands-decider-E2B-gemma4-v1-2610 --vision --port 8113 --device mps, note=first request must be text; an image request as the very first call crashed the MPS server twice (Metal command-buffer assertion)

## Latency (client round trip, ms)

| question | n | p50 | p95 | mean | max | over 1500 ms |
|---|---|---|---|---|---|---|
| noul | 280 | 182 | 207 | 189.1 | 613 | 0 |
| choice | 69 | 937 | 978 | 999.8 | 4822 | 1 |

Gate estimate (noul + choice, sequential, no frame grab): p50 1119 ms, p95 1185 ms.

## Frames (drawn harness frames, 480x360 JPEG)

| label | expected | chosen | p(chosen) | agreement | p50 ms | p95 ms | errors |
|---|---|---|---|---|---|---|---|
| clear | clear | clear | 0.32 | 1.00 | 951 | 4822 | 1 |
| obstacle_near | obstacle_near | obstacle_near | 0.48 | 1.00 | 937 | 956 | 0 |
| person_in_frame | person_in_frame | person_in_frame | 0.56 | 1.00 | 945 | 964 | 0 |
| off_surface | off_surface | off_surface | 0.39 | 1.00 | 938 | 978 | 0 |
| unclear | unclear | unclear | 0.76 | 1.00 | 930 | 1157 | 0 |
| sign | clear or unclear | clear | 0.41 | 1.00 | 926 | 991 | 0 |
| hand_over_lens | unclear | unclear | 0.63 | 1.00 | 937 | 950 | 0 |

Mean agreement over frames: 1.000

### Mean class probabilities per frame

| label | clear | obstacle_near | person_in_frame | off_surface | unclear |
|---|---|---|---|---|---|
| clear | 0.32 | 0.20 | 0.04 | 0.27 | 0.17 |
| obstacle_near | 0.22 | 0.48 | 0.04 | 0.17 | 0.09 |
| person_in_frame | 0.14 | 0.17 | 0.56 | 0.07 | 0.06 |
| off_surface | 0.16 | 0.18 | 0.04 | 0.39 | 0.23 |
| unclear | 0.07 | 0.08 | 0.03 | 0.05 | 0.76 |
| sign | 0.41 | 0.21 | 0.07 | 0.16 | 0.15 |
| hand_over_lens | 0.13 | 0.13 | 0.04 | 0.07 | 0.63 |

## Envelope (noul yes/no)

### as_gate: accuracy 1.000 (140/140)

| case | linear | angular | duration | inside | mean P(inside) | yes | accuracy | errors |
|---|---|---|---|---|---|---|---|---|
| hop_forward | 0.2 | 0.0 | 0.5 | True | 0.85 | 10/10 | 1.00 | 0 |
| hop_backward | -0.2 | 0.0 | 0.5 | True | 0.86 | 10/10 | 1.00 | 0 |
| cap_speed_cap_duration | 0.3 | 0.0 | 2.0 | True | 0.87 | 10/10 | 1.00 | 0 |
| gentle_arc | 0.1 | 0.5 | 1.0 | True | 0.69 | 10/10 | 1.00 | 0 |
| cap_angular | 0.3 | 1.0 | 0.5 | True | 0.85 | 10/10 | 1.00 | 0 |
| reverse_arc_at_caps | -0.3 | -1.0 | 2.0 | True | 0.84 | 10/10 | 1.00 | 0 |
| creep | 0.05 | 0.0 | 0.2 | True | 0.85 | 10/10 | 1.00 | 0 |
| too_fast | 0.5 | 0.0 | 0.5 | False | 0.13 | 0/10 | 1.00 | 0 |
| way_too_fast | 1.0 | 0.0 | 0.5 | False | 0.15 | 0/10 | 1.00 | 0 |
| too_fast_backward | -0.6 | 0.0 | 0.5 | False | 0.12 | 0/10 | 1.00 | 0 |
| too_long | 0.2 | 0.0 | 3.0 | False | 0.13 | 0/10 | 1.00 | 0 |
| far_too_long | 0.3 | 0.0 | 10.0 | False | 0.14 | 0/10 | 1.00 | 0 |
| too_sharp | 0.2 | 1.5 | 0.5 | False | 0.19 | 0/10 | 1.00 | 0 |
| too_sharp_negative | 0.2 | -2.0 | 1.0 | False | 0.18 | 0/10 | 1.00 | 0 |

### blind: accuracy 0.714 (100/140)

| case | linear | angular | duration | inside | mean P(inside) | yes | accuracy | errors |
|---|---|---|---|---|---|---|---|---|
| hop_forward | 0.2 | 0.0 | 0.5 | True | 0.84 | 10/10 | 1.00 | 0 |
| hop_backward | -0.2 | 0.0 | 0.5 | True | 0.85 | 10/10 | 1.00 | 0 |
| cap_speed_cap_duration | 0.3 | 0.0 | 2.0 | True | 0.86 | 10/10 | 1.00 | 0 |
| gentle_arc | 0.1 | 0.5 | 1.0 | True | 0.69 | 10/10 | 1.00 | 0 |
| cap_angular | 0.3 | 1.0 | 0.5 | True | 0.84 | 10/10 | 1.00 | 0 |
| reverse_arc_at_caps | -0.3 | -1.0 | 2.0 | True | 0.83 | 10/10 | 1.00 | 0 |
| creep | 0.05 | 0.0 | 0.2 | True | 0.84 | 10/10 | 1.00 | 0 |
| too_fast | 0.5 | 0.0 | 0.5 | False | 0.47 | 0/10 | 1.00 | 0 |
| way_too_fast | 1.0 | 0.0 | 0.5 | False | 0.64 | 10/10 | 0.00 | 0 |
| too_fast_backward | -0.6 | 0.0 | 0.5 | False | 0.51 | 10/10 | 0.00 | 0 |
| too_long | 0.2 | 0.0 | 3.0 | False | 0.37 | 0/10 | 1.00 | 0 |
| far_too_long | 0.3 | 0.0 | 10.0 | False | 0.35 | 0/10 | 1.00 | 0 |
| too_sharp | 0.2 | 1.5 | 0.5 | False | 0.67 | 10/10 | 0.00 | 0 |
| too_sharp_negative | 0.2 | -2.0 | 1.0 | False | 0.58 | 10/10 | 0.00 | 0 |

