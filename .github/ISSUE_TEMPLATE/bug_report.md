---
name: Bug report
about: Something in the agent, the gate, the pattern library or the fakes misbehaves
title: ""
labels: bug
---

**What happened**

One or two sentences. If the car moved when it should not have, say so first.

**How to reproduce**

The exact command (`make ...` or `python ...`), the body (`sim` or `car`), and whether the
decider was the fake (`make fake-decider`) or the real one (`make decider`).

**What you expected**

**Evidence**

The relevant rows from `events.jsonl` or the gate log, and the verdict with its reason string.
Do not paste frames that show people.

**Never include**

Car passwords, the contents of `~/.config/deepracer/env`, hostnames, IP addresses or SSH keys.
For anything security-related, follow [SECURITY.md](../../SECURITY.md) instead of opening an issue.
