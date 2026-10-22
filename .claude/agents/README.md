# Reviewer subagents for the hackathon round

Seven read-only Claude Code subagents, one per review angle. Each has `tools: Read, Grep,
Glob, Bash` (Bash for the scanner, tests, `json.tool`, `curl -sI` only) and `model: sonnet`.
None edits a file or commits; each returns a findings table (Severity, File:line, Finding,
Why it matters for the rubric, Suggested fix) and 0-5 scores for the sub-criteria it owns.

| Agent | Owns |
|---|---|
| `hackathon-criteria-reviewer` | qualification gates G1-G8 and the four rubric criteria for the whole submission |
| `hackathon-code-reviewer` | correctness and clarity of `patterns/`, `gate.py`, `decider_client.py`; fail-open hunt; thresholds; error paths; tests |
| `decider-pattern-conformance-reviewer` | file names, imports and API names versus the upstream quickstart; System One shape; `QUESTIONS` and `YES`; the `InterventionHandler` contract |
| `kiro-setup-reviewer` | `.kiro/` steering, spec and hooks against the confirmed Kiro conventions |
| `content-editor-reviewer` | article, README and SUBMISSION prose: style rules, front matter limits, first person, claims traceable to `FACTS.md` and `docs/results/` |
| `repo-aesthetics-reviewer` | README hero, badges, media, section order, tables, dark/light images, links, naming |
| `notebook-reviewer` | notebooks run offline top to bottom, outputs saved, narrative, no secrets, API fidelity |

## Running a review round

1. Make sure the venv is current (`make venv` if needed) and no real services are required:
   every reviewer works against the repo and the fake stack.
2. From Claude Code in the repo root, invoke each reviewer by name, in parallel when possible,
   with the round number and the files changed since the last round. Example prompt:
   `Use the hackathon-code-reviewer subagent on round 3; changed files: patterns/strands/tool_call_intervention.py, tests/unit/test_patterns.py.`
3. Collect the seven reports into `hackathon/REVIEW-LOG.md` under a heading
   `## Round N (YYYY-MM-DD)`, one subsection per reviewer, keeping each findings table and
   score block verbatim. Add a `### Decisions` subsection where the lead marks each finding
   `fix`, `defer` or `reject` with one line of reason.
4. Fix in priority order: FAIL rows first (qualification), then HIGH rows on the 30 percent
   criteria, then the rest. Re-run the two hooks' commands by hand after fixes:
   `.venv/bin/python hackathon/scan_submission.py --repo . --article docs/article/article.md`
   and `.venv/bin/python -m pytest tests/unit/test_patterns.py -q`.
5. Repeat until the criteria reviewer reports zero FAIL and no HIGH finding is left open;
   the final round's log is part of the submission evidence.

Reviewers quote the official rule text they apply (the brief, `hackathon/RUBRIC.md`, the Kiro
docs, `docs/dev/CONTRACTS.md`) and cite `file:line`, so a finding can be checked without
re-running the agent. The lead commits; reviewers never do.
