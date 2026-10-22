# KrewHQ: team context layer for this project

Four agent teams (report 13 §5) share one ledger in KrewHQ, project `deepracer`.

| Team | Scope | Owns (see docs/dev/CONTRACTS.md §1) |
|---|---|---|
| `car` | driver, deadman, car packages, runtime | `src/deepracer_agent/{driver,transport,calibration,tools,runtime,events}.py`, `car/` |
| `intelligence` | decider gate, voice, VLM, beats | `src/deepracer_agent/{gate,decider_client,look,voice}.py`, `beats/` |
| `portal` | Pit Wall | `portal/` |
| `qa` | harness, sim tests, pen runs | `harness/`, `tests/sim`, `tests/conftest.py` |

## Session protocol (every agent session)

1. `scripts/krewhq-session.sh start <team>`: runs `krewhq session-start --ticket deepracer-<team>`
   and `krewhq recall --ticket deepracer-<team> "<team> handoff contracts gotchas"`; prints the
   recalled context. If the hub is unreachable the CLI fails open (exit 0) and the session
   continues on `docs/dev/CONTRACTS.md` alone.
2. While working: `krewhq capture --ticket deepracer-<team> --type decision|gotcha|investigation|procedure --title "..." "<text>"`
   for anything another team must know. Captures queue locally in `~/.krewhq` when offline.
3. End: `scripts/krewhq-session.sh handoff <team> <next-team>` builds the packet from the
   pending queue (`krewhq handoff deepracer-<next-team> --from-pending all --ref Vivek0712/strands-robots-deepracer`).
   The next session runs `krewhq pickup deepracer-<team>`.

## Hub

Running now: a LOCAL pilot hub in Docker (`deploy/docker` image, container `krewhq-hub`, API on
`127.0.0.1:8443`, team map `~/.krewhq-org/projects/deepracer/team-map.yaml` mounted read-only with
teams deepracer, car, intelligence, portal, qa and actor `u:Vivek0712`; a copy is `.krewhq/team-map.yaml`). Start or restart it with:

```
cd <your KrewHQ checkout> && docker compose -f deploy/docker/docker-compose.yml \
  -f ~/strands-robots-deepracer/.krewhq/hub-override.yml up -d --wait hub   # ports + team-map volume
```

`scripts/krewhq-session.sh` exports `KREWHQ_HUB_URL`, `KREWHQ_TOKEN` (dev token, identity asserted
not verified) and `KREWHQ_REPO=strands-robots-deepracer` for it. The EC2 hub below is the shared one
once its firewall admits this machine; records can be exported from the local hub and restored there
(`krewhq export` / `krewhq restore`).

### EC2 pilot hub (shared, currently firewalled)

Pilot hub: the maintainer's EC2 instance at `http://<hub-host>:8443`, configured
in `~/.krewhq/config.toml`. Its security group (`<redacted>`) currently allows 8443 only
from an old IP. Until the owner adds this machine (`aws ec2 authorize-security-group-ingress
--profile heisenberg --region us-east-1 --group-id <redacted> --protocol tcp --port 8443
--cidr <my-ip>/32`), captures stay in the local outbox and `krewhq sync` flushes them later.

## Handoff template

```
ticket: deepracer-<to-team>
from: <team>
done: <what now exists, with paths>
contracts touched: <sections of docs/dev/CONTRACTS.md changed, or "none">
gotchas: <things that cost time>
next: <what the receiving team should do first>
```
