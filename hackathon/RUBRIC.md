# Selection and shortlisting rubric: Strands Decider 2B hackathon

How we score a submission before the judges do. Part A is pass/fail, Part B mirrors the official
weights, Part C sets shortlist thresholds, Part D is a blank sheet. `scan_submission.py`
automates the evidence hunt in A and the machine-visible half of B.

## Part A: Qualification gates (hard pass/fail)

| Gate | Pass when | Evidence a scanner or judge looks for |
|---|---|---|
| A1 Decider 2B used for a meaningful decision | A Decider 2B answer changes what the agent does at least once per run | `/v1/systemone` or `strands-decider` in code; typed questions `noul`, `choice` or `score`; a branch on the answer that blocks, redirects or confirms an action |
| A2 Paired with Amazon Bedrock | The agent's language model runs on Bedrock | `BedrockModel`, `strands.models.bedrock`, a Bedrock model id (`amazon.nova`, `us.anthropic`, `anthropic.claude`), `bedrock-runtime` |
| A3 Builder Center article present and describes the decision | Published article with a section on what the agent does and the exact question handed to the Decider | Front matter with title, description, five tags, cover; a heading containing "Decider"; the question text and the option set quoted |
| A4 Public repo link | Repo is public and the link is in the article and the submission form | `https://github.com/...` in SUBMISSION.md and the article's "Try it" section; no placeholder left |
| A5 Reusable decision pattern | A stranger can copy one folder into their own Strands agent | `patterns/strands/_client.py`, `tool_call_intervention.py`, `README.md`; a `QUESTIONS` dict; an `InterventionHandler` with `before_tool_call`; a "How to use" note |
| A6 Demo video under 3 minutes | A link that opens, runtime under 3:00 | Video URL in SUBMISSION.md with the runtime stated; the decision visible on screen |
| A7 One declared pattern tag plus `#strands-decider-2b` | Exactly one pattern tag, and the hackathon tag, on article and form | `#strands-decider-2b` and the pattern tag (`#guardrails` for us) in article tags and SUBMISSION.md |
| A8 Original agent | Not published before the hackathon window | Statement in SUBMISSION.md; first public commit date; no earlier article with the same agent |

Failing any gate is out, whatever Part B says.

## Part B: Scored criteria

Each sub-criterion is scored 0 to 5; anchors for 1, 3 and 5, with 2 and 4 between.

### B1 Creativity and cool factor (30)

| Sub-criterion | 1 | 3 | 5 |
|---|---|---|---|
| B1.1 Problem the decision solves | A chatbot classifies text | A real action is gated by a judgement a human used to make | A physical or irreversible action is gated, and the gate is visible to a room |
| B1.2 Surprise and delight | Expected demo | One moment a viewer repeats to a friend | Several moments; the demo has a story arc with a payoff |
| B1.3 Breadth of the Strands stack | Agents only | Agents plus Decider plus one more Strands project, each doing distinct work | Four or more Strands projects, each with a stated reason to be there |
| B1.4 Demo quality | Slides and a terminal | Live or recorded run with the decision on screen | Live run, the decision spoken and shown, a failure case shown on purpose |

### B2 Effective use of Decider 2B with Bedrock (30)

| Sub-criterion | 1 | 3 | 5 |
|---|---|---|---|
| B2.1 Decision design | One yes/no with no stated option set | Typed questions with criteria; thresholds explained | Questions designed around the model's strengths; deterministic checks kept in code; thresholds set from measurement |
| B2.2 Wiring and fail behaviour | Decider called ad hoc from a tool | `InterventionHandler.before_tool_call` returning Proceed, Guide, Confirm or Deny | Same, plus fail-closed on timeout or error, every verdict logged with its latency |
| B2.3 Reusability of the pattern | Code is specific to the demo | `patterns/` folder with client, intervention and README | Drop-in folder mirroring upstream names, QUESTIONS printed as JSON, a notebook that runs it against a fake server |
| B2.4 Measured latency or cost (bonus) | No numbers | Per-question latency measured once | A benchmark file with p50 and p95, memory, model comparison and the method |

### B3 Communication (25)

| Sub-criterion | 1 | 3 | 5 |
|---|---|---|---|
| B3.1 Article clarity | Lists features | Explains what the agent does, then the decision, with one figure | A reader could rebuild the decision from the article; figures, code excerpts and numbers all sourced |
| B3.2 Video | Screen recording with no narration | Under 3 minutes, shows the decision firing | Under 3 minutes, shows a Proceed and a Deny, says why in one sentence each |
| B3.3 README and repo navigation | README is a stub | Title, what it does, quick start, pattern pointer | Hero image, badges, every rubric section, a notebook, LICENSE, contributor guide |
| B3.4 Honesty of claims | Claims without sources | Numbers cited to files | Limits stated plainly (what was not measured, what the model misses) |

### B4 Originality (15)

| Sub-criterion | 1 | 3 | 5 |
|---|---|---|---|
| B4.1 Novelty of the agent | Variation of the quickstart | A new domain for a Decider gate | A domain and a decision shape nobody else submitted |
| B4.2 Own contribution | Uses upstream as-is | Extends upstream in the repo | Upstream contributions merged and cited |
| B4.3 Provenance | No LICENSE or history | LICENSE, clear authorship | LICENSE, commit history inside the window, originality statement |

### Weighting formula

For each bucket: `bucket_score = bucket_weight * (sum of sub-scores) / (5 * number of sub-criteria)`.
Total out of 100 = B1 + B2 + B3 + B4. Example: B1 sub-scores 4,4,5,4 give 30 * 17/20 = 25.5.

## Part C: Shortlist thresholds

### What a top-100 (Gate 1) entry looks like

All eight gates pass on a first read. The Decider and Bedrock names are in code where a scanner
finds them. The article names the question and the options. The README answers "what does it
do" above the fold and `patterns/` is there to open. Scores of 3 across the board: about 60/100.

### What a top-3 (Gate 2) entry looks like

A human panel watches the video and reads the article. The decision gates something that
matters (a motion, a payment, a deletion), the agent explains its verdicts, and a failure case is
shown on purpose. Latency and accuracy are measured, limits stated. The pattern is a drop-in with
upstream file names and a notebook. Several Strands projects, each with a job. Expect 4s and 5s:
85/100 or better.

### Common disqualifiers

- No typed question in code; the Decider is mentioned in the article only.
- Model not on Bedrock, or the Bedrock model is used only for the article's examples.
- Two pattern tags, or the hackathon tag missing.
- Video over 3 minutes, private, or a placeholder link.
- Repo private, or a secret, a tracked `.env`, or a photo of a bystander in the tree.
- Agent published before the window.

### What an AI first-pass scorer most likely keys on

Explicit file names (`patterns/strands/_client.py`, `tool_call_intervention.py`, `README.md`,
`LICENSE`, `notebooks/*.ipynb`), imports (`from strands.interventions import Proceed, Guide,
Deny, Confirm`, `strands.models.bedrock`), API names (`/v1/systemone`, `noul`, `choice`,
`score`, `before_tool_call`, `QUESTIONS`, `YES`), model ids (`StrandsAgents/strands-decider-2B`),
tags (`#strands-decider-2b`, the pattern tag), README headings that match the rubric wording
("The decision handed to Decider 2B", "Reusable pattern", "Hackathon submission"), and the
presence of a video link with a stated runtime. Write for that reader first; the human follows
the same signposts.

## Part D: Self-score sheet

| Item | Score (0-5) | Evidence | Note |
|---|---|---|---|
| A1..A8 gates | pass / fail each | | |
| B1.1 Problem the decision solves | | | |
| B1.2 Surprise and delight | | | |
| B1.3 Breadth of the Strands stack | | | |
| B1.4 Demo quality | | | |
| B2.1 Decision design | | | |
| B2.2 Wiring and fail behaviour | | | |
| B2.3 Reusability of the pattern | | | |
| B2.4 Measured latency or cost | | | |
| B3.1 Article clarity | | | |
| B3.2 Video | | | |
| B3.3 README and repo navigation | | | |
| B3.4 Honesty of claims | | | |
| B4.1 Novelty of the agent | | | |
| B4.2 Own contribution | | | |
| B4.3 Provenance | | | |
| B1 total (/30) | | | |
| B2 total (/30) | | | |
| B3 total (/25) | | | |
| B4 total (/15) | | | |
| Total (/100) | | | |
