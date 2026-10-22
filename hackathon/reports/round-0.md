# Submission scan

Repo: `~/strands-robots-deepracer`  
Article: `docs/article/article.md`  
Generated: 2026-10-22T15:47:57+05:30  
Result: 8 PASS, 5 WARN, 2 FAIL; heuristic rubric estimate 79.2/100

## Summary

| Check | Status | Weight | Gate | First evidence |
|---|---|---|---|---|
| Decider 2B usage | PASS | 10 | yes | /v1/systemone: 17 hit(s), first beats/kiosk.py:474 |
| InterventionHandler wiring | PASS | 10 | yes | subclass src/deepracer_agent/gate.py:515: class DeciderGate(InterventionHandler): |
| Amazon Bedrock pairing | PASS | 8 | yes | anthropic.claude: 1 hit(s), first src/deepracer_agent/runtime.py:38 |
| Reusable decision pattern folder | FAIL | 10 | yes | present: patterns/strands/_client.py |
| Strands family coverage (informational) | PASS | 3 |  | README mentions 5/6: strands-agents, strands-robots, strands.bidi, Strands Box, strands-decider |
| README structure | PASS | 6 |  | title: True; hero image above first section: True; badges: True |
| LICENSE and contributor guide | FAIL | 3 | yes | LICENSE: missing |
| Walk-through notebook | WARN | 2 |  | notebooks/*.ipynb: none |
| Article front matter | PASS | 8 | yes | title: 115 chars (limit 255) |
| Article body | WARN | 6 |  | byline 'Vivek Raja, AWS AI Hero': True |
| Submission package (hackathon/SUBMISSION.md) | WARN | 6 | yes | tags present: #strands-decider-2b, #guardrails |
| Originality statement | PASS | 3 |  | SUBMISSION.md states originality and prior non-publication: True |
| Secrets scan of tracked files | WARN | 10 | yes | WARN car/connect/env.example:6: password assignment, review |
| People-photo policy (human review) | WARN | 2 | yes | approved event photos: 3 |
| Tests present and collectable | PASS | 4 |  | test files under tests/: 37 |

## Qualification gates

Hard requirements. Any FAIL here is a likely disqualification regardless of score.

- PASS: Decider 2B usage
- PASS: InterventionHandler wiring
- PASS: Amazon Bedrock pairing
- FAIL: Reusable decision pattern folder (Create patterns/strands/README.md mirroring upstream examples/strands/.)
- FAIL: LICENSE and contributor guide (Add a LICENSE file (a public repo without one is not reusable).)
- PASS: Article front matter
- WARN: Submission package (hackathon/SUBMISSION.md) (Replace the repo and video URL placeholders with the real links before submitting.)
- WARN: Secrets scan of tracked files (Review each password assignment and IPv4 literal; move values to env or config.)
- WARN: People-photo policy (human review) (Open each flagged image; keep it only if no real person is shown.)

## Estimated rubric score (heuristic)

This maps check weights onto the official buckets (Creativity 30, Decider 2B 30, Communication 25,
Originality 15). It measures whether the evidence a judge looks for is present, not how good the
work is. Use it to rank rounds against each other, never as a predicted judge score.

| Bucket | Checks | Estimate | Max |
|---|---|---|---|
| creativity | 1 | 30.0 | 30 |
| decider | 5 | 22.9 | 30 |
| communication | 5 | 18.8 | 25 |
| originality | 2 | 7.5 | 15 |
| total | 15 | 79.2 | 100 |

## Fix list (by weight)

- [FAIL, weight 10] Reusable decision pattern folder: Create patterns/strands/README.md mirroring upstream examples/strands/.
- [FAIL, weight 3] LICENSE and contributor guide: Add a LICENSE file (a public repo without one is not reusable).
- [WARN, weight 10] Secrets scan of tracked files: Review each password assignment and IPv4 literal; move values to env or config.
- [WARN, weight 6] Article body: Resolve 4 placeholder(s) in the article before publishing.
- [WARN, weight 6] Submission package (hackathon/SUBMISSION.md): Replace the repo and video URL placeholders with the real links before submitting.
- [WARN, weight 2] Walk-through notebook: Add notebooks/<name>.ipynb that calls the pattern against the fake decider.
- [WARN, weight 2] People-photo policy (human review): Open each flagged image; keep it only if no real person is shown.

## Evidence

### Decider 2B usage (PASS, weight 10, bucket decider)

- /v1/systemone: 17 hit(s), first beats/kiosk.py:474
- strands-decider: 7 hit(s), first harness/fake_decider.py:3
- strands_decider: 2 hit(s), first harness/fake_decider.py:4
- StrandsAgents/strands-decider-2B: not found in .py files
- "noul": 61 hit(s), first beats/kiosk.py:585
- "choice": 45 hit(s), first harness/fake_decider.py:8
- "score": 10 hit(s), first harness/fake_decider.py:9

### InterventionHandler wiring (PASS, weight 10, bucket decider)

- subclass src/deepracer_agent/gate.py:515: class DeciderGate(InterventionHandler):
- before_tool_call src/deepracer_agent/gate.py:594
- imported from strands.interventions: Confirm, Deny, Guide, Proceed

### Amazon Bedrock pairing (PASS, weight 8, bucket decider)

- anthropic.claude: 1 hit(s), first src/deepracer_agent/runtime.py:38
- amazon.nova: 12 hit(s), first src/deepracer_agent/look.py:34
- us.anthropic: 1 hit(s), first src/deepracer_agent/runtime.py:38
- bedrock-runtime: 1 hit(s), first src/deepracer_agent/look.py:88
- nova-sonic: 1 hit(s), first src/deepracer_agent/voice_rehearsal.py:246

### Reusable decision pattern folder (FAIL, weight 10, bucket decider)

- present: patterns/strands/_client.py
- present: patterns/strands/tool_call_intervention.py
- missing: patterns/strands/README.md
- README has a how-to-use / drop-in note: False
- question set shown as JSON (json.dumps(QUESTIONS) or a ```json block): False

### Strands family coverage (informational) (PASS, weight 3, bucket creativity)

- README mentions 5/6: strands-agents, strands-robots, strands.bidi, Strands Box, strands-decider

### README structure (PASS, weight 6, bucket communication)

- title: True; hero image above first section: True; badges: True
- sections present (9/9): What it does, Architecture, Quick start, The decision handed to Decider 2B, Reusable pattern, Safety, Strands stack, Hackathon submission, License

### LICENSE and contributor guide (FAIL, weight 3, bucket originality)

- LICENSE: missing
- CONTRIBUTING/AGENTS: AGENTS.md

### Walk-through notebook (WARN, weight 2, bucket communication)

- notebooks/*.ipynb: none

### Article front matter (PASS, weight 8, bucket communication)

- title: 115 chars (limit 255)
- description: 509 chars (limit 512)
- tags (5): aws-deepracer, strands-agents, strands-decider-2b, amazon-bedrock, guardrails
- cover img/cover.png: 1200x675 (want 1200x675)

### Article body (WARN, weight 6, bucket communication)

- byline 'Vivek Raja, AWS AI Hero': True
- heading containing 'Decider': True
- word count (prose, excluding code blocks and image lines): 3959
- placeholder line 10: < COVER IMAGE >
- placeholder line 234: [TESTIMONIALS
- placeholder line 248: [REPO URL
- placeholder line 256: [REPO URL

### Submission package (hackathon/SUBMISSION.md) (WARN, weight 6, bucket communication)

- tags present: #strands-decider-2b, #guardrails
- declared pattern line: True
- repo URL: placeholder
- video URL: placeholder; mentions 3 min: True

### Originality statement (PASS, weight 3, bucket originality)

- SUBMISSION.md states originality and prior non-publication: True

### Secrets scan of tracked files (WARN, weight 10, bucket gate)

- WARN car/connect/env.example:6: password assignment, review
- WARN docs/context/02-deepracer-ros-http-stack.md:87: password assignment, review
- WARN docs/context/02-deepracer-ros-http-stack.md:91: password assignment, review
- WARN portal/frontend/dist/assets/index-B_10MklX.js:40: IPv4 literal 192.168.1.23
- WARN portal/frontend/src/views/Settings.tsx:143: IPv4 literal 192.168.1.23
- WARN src/deepracer_agent/connect.py:5: IPv4 literal 10.0.0.1
- WARN src/deepracer_agent/connect.py:239: IPv4 literal 10.0.0.1
- WARN src/deepracer_agent/discover.py:104: IPv4 literal 10.0.0.1
- WARN src/deepracer_agent/discover.py:104: IPv4 literal 10.0.1.1
- WARN src/deepracer_agent/discover.py:212: IPv4 literal 192.0.2.1
- WARN src/deepracer_agent/quick_hop.py:9: IPv4 literal 192.168.0.7
- WARN src/deepracer_agent/quick_hop.py:22: IPv4 literal 192.168.0.7
- ... (more omitted)

### People-photo policy (human review) (WARN, weight 2, bucket gate)

- approved event photos: 3
- review: docs/results/portal/04-main-person-deny.png

### Tests present and collectable (PASS, weight 4, bucket decider)

- test files under tests/: 37
- pytest --collect-only tests/unit: 852 tests, exit 0

