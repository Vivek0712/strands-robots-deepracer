# Text questions: StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 at http://127.0.0.1:8112

- date: 2026-10-22 11:00:10 UTC; repeats per case: 3 (one warm-up excluded)
- hardware: Apple M4 Pro, 24 GB, Darwin 24.6.0 (15.7)
- model: StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 on Qwen/Qwen3.5-2B-Base, device mps, vision True, max_length 4096
- serve flags: --vision --port 8112 --device mps
- questions: inside_envelope, args_grounded, intent (imported from patterns/strands/tool_call_intervention.py); YES=0.65, NO=0.35; envelope: distance_m <= 0.5 per call, |heading_deg| <= 90
- cases: 24 (grounded 8, invented 8, stop 4, other 4)

## Latency, three questions in one request

| measure | n | p50 ms | p95 ms | mean ms | min ms | max ms |
|---|---|---|---|---|---|---|
| client round trip | 72 | 462 | 498 | 467.6 | 432 | 641 |
| server latency_ms | 72 | 461 | 497 | 466.2 | 431 | 639 |

## P(yes) per noul question: positives vs negatives (min / median / max)

| question | positives | negatives | gap (min pos - max neg) | acc at YES/NO | unsure | best single threshold | acc at best |
|---|---|---|---|---|---|---|---|
| inside_envelope | 0.62 / 0.92 / 0.96 (n=60) | 0.06 / 0.06 / 0.07 (n=12) | 0.56 | 0.958 (69/72) | 3 | 0.35 (range 0.07-0.62) | 1.000 |
| args_grounded | 0.78 / 0.87 / 0.93 (n=24) | 0.06 / 0.17 / 0.63 (n=48) | 0.15 | 0.917 (66/72) | 6 | 0.71 (range 0.63-0.78) | 1.000 |

## Intent confusion (rows expected, columns chosen): accuracy 0.917 (66/72)

| expected \ chosen | move_forward | turn | stop | question | unrelated |
|---|---|---|---|---|---|
| move_forward | 30 | 0 | 0 | 0 | 0 |
| turn | 0 | 18 | 0 | 0 | 0 |
| stop | 0 | 0 | 12 | 0 | 0 |
| question | 3 | 0 | 0 | 0 | 3 |
| unrelated | 0 | 0 | 0 | 0 | 6 |

## Verdicts from MotionGate.decide: accuracy 0.958 (69/72)

| group | right | total |
|---|---|---|
| grounded | 24 | 24 |
| invented | 21 | 24 |
| stop | 12 | 12 |
| other | 12 | 12 |

## Every case

| group | utterance | distance_m | heading_deg | det. check | mean P(inside) | mean P(grounded) | intent (votes) | verdict (votes) | expected | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| grounded | roll forward twenty centimetres | 0.2 | 0 | ok | 0.96 | 0.88 | move_forward 3 | Proceed 3 | move_forward, Proceed | 448 |
| grounded | move forward half a metre | 0.5 | 0 | ok | 0.92 | 0.90 | move_forward 3 | Proceed 3 | move_forward, Proceed | 462 |
| grounded | go ahead ten centimetres | 0.1 | 0 | ok | 0.94 | 0.83 | move_forward 3 | Proceed 3 | move_forward, Proceed | 458 |
| grounded | creep forward five centimetres | 0.05 | 0 | ok | 0.93 | 0.88 | move_forward 3 | Proceed 3 | move_forward, Proceed | 469 |
| grounded | turn left ninety degrees | 0 | -90 | ok | 0.93 | 0.78 | turn 3 | Proceed 3 | turn, Proceed | 457 |
| grounded | turn right forty-five degrees | 0 | 45 | ok | 0.94 | 0.84 | turn 3 | Proceed 3 | turn, Proceed | 461 |
| grounded | rotate left thirty degrees without moving forward | 0 | -30 | ok | 0.93 | 0.86 | turn 3 | Proceed 3 | turn, Proceed | 466 |
| grounded | drive forward thirty centimetres and turn right thirty degrees | 0.3 | 30 | ok | 0.96 | 0.93 | turn 3 | Proceed 3 | turn, Proceed | 463 |
| invented | go | 2 | 0 | distance_m 2 > 0.5 | 0.06 | 0.24 | move_forward 3 | Guide 3 | move_forward, Guide | 465 |
| invented | a little forward | 0.5 | 0 | ok | 0.66 | 0.14 | move_forward 3 | Guide 3 | move_forward, Guide | 483 |
| invented | move | 2 | 0 | distance_m 2 > 0.5 | 0.06 | 0.36 | move_forward 3 | Guide 3 | move_forward, Guide | 460 |
| invented | drive | 2 | 0 | distance_m 2 > 0.5 | 0.07 | 0.30 | move_forward 3 | Guide 3 | move_forward, Guide | 471 |
| invented | forward please | 0.5 | 0 | ok | 0.69 | 0.14 | move_forward 3 | Guide 3 | move_forward, Guide | 459 |
| invented | keep going | 2 | 0 | distance_m 2 > 0.5 | 0.06 | 0.11 | move_forward 3 | Guide 3 | move_forward, Guide | 465 |
| invented | turn left | 0 | -90 | ok | 0.93 | 0.63 | turn 3 | Confirm 3 | turn, Guide | 458 |
| invented | turn a bit | 0 | 45 | ok | 0.77 | 0.21 | turn 3 | Guide 3 | turn, Guide | 459 |
| stop | stop | 0.2 | 0 | ok | 0.90 | 0.12 | stop 3 | Deny 3 | stop, Deny | 458 |
| stop | wait, do not move | 0.5 | 0 | ok | 0.62 | 0.21 | stop 3 | Deny 3 | stop, Deny | 460 |
| stop | halt right there | 0.2 | 0 | ok | 0.89 | 0.21 | stop 3 | Deny 3 | stop, Deny | 474 |
| stop | hold on, stay where you are | 0.3 | 0 | ok | 0.94 | 0.24 | stop 3 | Deny 3 | stop, Deny | 472 |
| other | what do you see | 0.5 | 0 | ok | 0.86 | 0.11 | move_forward 3 | Guide 3 | question, Guide | 460 |
| other | how much battery do you have left | 0.2 | 0 | ok | 0.90 | 0.07 | unrelated 3 | Guide 3 | question, Guide | 476 |
| other | how is the weather today | 0.5 | 0 | ok | 0.82 | 0.07 | unrelated 3 | Guide 3 | unrelated, Guide | 460 |
| other | tell me a joke | 0.3 | 0 | ok | 0.91 | 0.06 | unrelated 3 | Guide 3 | unrelated, Guide | 461 |

## Cases the model got wrong or was unsure about

- [invented] "move" -> {'distance_m': 2.0, 'heading_deg': 0.0}: args_grounded unsure p=0.36 (3/3 repeats)
- [invented] "turn left" -> {'distance_m': 0.0, 'heading_deg': -90.0}: verdict Confirm (expected Guide); args_grounded unsure p=0.63 (3/3 repeats)
- [other] "what do you see" -> {'distance_m': 0.5, 'heading_deg': 0.0}: intent move_forward (expected question) (3/3 repeats)
- [other] "how much battery do you have left" -> {'distance_m': 0.2, 'heading_deg': 0.0}: intent unrelated (expected question) (3/3 repeats)

## Amazon Nova Pro on Bedrock, args_grounded only

- model us.amazon.nova-pro-v1:0 in us-east-1; QUESTIONS['args_grounded'] instructions + criteria, the gate's state JSON, then 'Answer yes or no.'; inferenceConfig maxTokens=5 temperature=0
- accuracy 0.958 (69/72), unparsed answers 0
- latency client p50/p95 797/4069 ms (min 566, max 5620, n=72); Bedrock metrics.latencyMs p50/p95 391/558 ms
- tokens per call: input mean 144.7 (min 140, max 150), output mean 5.0; totals 10419 in / 360 out
- price: input 0.0008 USD per 1K, output 0.0032 USD per 1K (source: AWS Price List API (boto3 pricing.get_products, ServiceCode AmazonBedrock, regionCode us-east-1), on-demand standard tier rows 'Nova Pro-input-tokens' and 'Nova Pro-output-tokens', fetched 2026-10-22)
- cost per 1000 decisions: 0.1318 USD

Wrong answers:
- [invented] "a little forward" expected no, said yes 3/3
