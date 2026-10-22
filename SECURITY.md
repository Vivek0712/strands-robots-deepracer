# Security

Report a vulnerability privately to the author, not in a public issue: use GitHub's private
vulnerability reporting on this repository (Security tab, "Report a vulnerability") or message
the author through github.com/Vivek0712. Expect an acknowledgement within a few days.

Never put car passwords, the contents of `~/.config/deepracer/env`, `~/strands-deepracer/poc`
or `edge/.env`, hostnames, IP addresses, SSH keys or host keys in an issue, a pull request or a
commit. The repository ships with no credentials; `car/connect/env.example` holds empty keys and
the AWS-documented image default only.

Scope: the laptop-side agent (`src/`, `patterns/`, `portal/`, `harness/`, `ops/`) and the on-car
units under `car/`. The decider is the explanation layer; a report that the gate can be made to
fail open (a Proceed with no decider, no frame, or a malformed answer) is the highest priority.
