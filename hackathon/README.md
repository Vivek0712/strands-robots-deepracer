# hackathon/

The self-review kit for a Strands Decider 2B hackathon submission. It scores a repository the
way a first-pass judge would, so gaps get fixed before the deadline. Nothing here runs the agent.

Files:

- `RUBRIC.md`: eight qualification gates, the four scored buckets with anchored sub-criteria,
  shortlist thresholds and a blank self-score sheet.
- `scan_submission.py`: stdlib-only scanner. Each check prints PASS, WARN or FAIL with evidence,
  then a fix list ordered by weight and a heuristic rubric estimate. Exit code 1 on any FAIL.
- `SUBMISSION.md`: the package pasted into the form (title, pitch, tags, pattern, decision,
  links, checklist).
- `REVIEW-LOG.md`: one row per finding per round.
- `reports/`: saved scanner output per round.

Use it on any Decider submission:

```bash
python hackathon/scan_submission.py --repo . --article docs/article/article.md \
    --byline "Your Name, Your Title" --tags strands-decider-2b,<your-pattern> \
    --md hackathon/reports/round-N.md --json hackathon/reports/round-N.json
```

Then score Part B of the rubric by hand, log findings, fix, and rerun (`make scan` here).
