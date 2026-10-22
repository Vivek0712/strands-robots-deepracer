---
inclusion: always
---

# Product: strands-robots-deepracer

## What this is

An agentic AWS DeepRacer. A stock DeepRacer is driven by `strands-robots` over ROS 2
(rosbridge on port 9090). A Strands Agents loop on Amazon Bedrock turns spoken or typed
instructions ("go forward 20 centimetres") into bounded hops of at most 0.3 m/s for at most
2 s. Before every motor command a local Strands Decider 2B
(`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, served with `strands-decider serve
--vision`, `POST /v1/systemone`) answers two typed questions: is the command inside the
briefed envelope (a `noul` yes/no with a probability), and what is in front of the camera
(a `choice` over `clear`, `obstacle_near`, `person_in_frame`, `off_surface`, `unclear`, plus a
`noul` "is a person visible" over the same frame). The answers map to the four Strands
interventions: Proceed, Guide, Confirm, Deny. Strands Bidi gives the rover a push-to-talk
voice through Amazon Nova Sonic. Strands Harness is the race-engineer agent (SSH sandbox to
the car, Cedar policy); it is never the driving loop.

## Who it is for

- The presenter and marshal running the seven live beats (`docs/context/11-final-use-cases.md`):
  Pre-flight, Marshal, Apology, Blindfold, Sign, Red Light, Pull the Plug.
- Builders who want a reusable Strands Decider 2B guardrail pattern for their own agents
  (`patterns/strands/`, the hackathon deliverable; declared pattern: Guardrails,
  tags `#strands-decider-2b` and `#guardrails`).
- Reviewers and judges reading the article (`docs/article/article.md`) and the repo.

## The one line to repeat everywhere

Physics stops the car (pen lip, hop cap, on-car deadman, marshal's thumb); the decider
explains. Never present the decider, the gate or any model as the safety layer. The gate is
the explanation layer: it can refuse a hop and say why, and every verdict is written to the
event log with its latency so "why did you stop?" is answered from the record.

## Facts, not inventions

Numbers come from `docs/results/` (benchmark `decider-benchmark-2026-10-14.md`, calibration
`decider-calibration-2026-10-14.md`) and `docs/article/FACTS.md`. Research and decisions are
in `docs/context/` (read `00`, `11`, `12`, then `06`). Do not re-derive those facts; cite them.
Never invent a measurement, a date or a quote. The demo video is recorded by the author; keep
its placeholder clearly marked and never fabricate it.

## Writing style for anything user-facing

Plain ASCII, no em dashes, first person "I" in the article, no rhetorical questions, no filler
transitions, no "think of it as", no tapestry/landscape/paradigm/synergy/ecosystem/framework,
at most one rule-of-three per passage, no stakes inflation. Headlines may be marketing-toned;
body text is precise.
