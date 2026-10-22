PY ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
RUFF ?= .venv/bin/ruff

.PHONY: venv unit sim wheels-off pen find-car lint fmt fake-car fake-console fake-decider portal portal-build evidence decider beat krewhq-start krewhq-handoff scan

venv:            ## create .venv and install the project editable (see docs/dev/CONTRACTS.md §2)
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -e ".[dev]"

unit:            ## layer 0: unit tests, no services
	$(PYTEST) -q tests/unit

sim:             ## layer 1: fake car + fake console + fake decider + agent + portal, end to end
	$(PYTEST) -q -m sim tests/sim

CAR_ENV = set -a; . ~/.config/deepracer/env; set +a; . car/connect/resolve-host.sh   # DEEPRACER_HOST=auto -> find the car

wheels-off:      ## layer 2: real car on a stand (DEEPRACER_HOST from ~/.config/deepracer/env, auto-resolved)
	$(CAR_ENV); DEEPRACER_BODY=car $(PYTEST) -q -m wheels_off tests/car

pen:             ## layer 3: the seven beats on the floor, operator present
	$(CAR_ENV); DEEPRACER_BODY=car $(PYTEST) -q -m pen tests/pen

find-car:        ## print the car's IP on this network (mDNS, then its MAC in the ARP table, then a sweep)
	set -a; . ~/.config/deepracer/env; set +a; car/connect/find-car.sh

lint:
	$(RUFF) check src portal/backend harness beats tests
	$(RUFF) format --check src portal/backend harness beats tests

fmt:
	$(RUFF) format src portal/backend harness beats tests

fake-car:        ## rosbridge-protocol fake car on ws://127.0.0.1:9091 (+ control http://127.0.0.1:8092)
	$(PY) -m harness.fake_car

fake-console:    ## MJPEG + console API on http://127.0.0.1:8090
	$(PY) -m harness.fake_console

fake-decider:    ## /v1/systemone on http://127.0.0.1:8111 answering from the fake console's label
	$(PY) -m harness.fake_decider

portal:          ## Pit Wall backend on http://127.0.0.1:8765 serving portal/frontend/dist
	$(PY) -m portal.backend.app

portal-build:    ## rebuild the frontend (needs Node 22); the dist/ output is committed
	cd portal/frontend && npm ci && npm run build

evidence:        ## Pit Wall screenshots + webm into docs/results/portal/ (own fake stack on 9191/8190/8192/8211, portal on 8865)
	uv pip install --python $(PY) -e ".[evidence]" -q && $(PY) -m playwright install chromium
	$(PY) -m portal.evidence.capture

DECIDER_MODEL ?= StrandsAgents/strands-decider-2B-qwen3.5-v1-2610
decider:         ## booth decider (benchmark 2026-10-14: 490 ms per gate on M4 Pro, 5.4 GB) on :8111
	strands-decider serve $(DECIDER_MODEL) --vision --device mps --port 8111

beat:            ## run one beat: make beat NAME=marshal BODY=sim
	DEEPRACER_BODY=$(BODY) $(PY) -m beats $(NAME)

# Optional maintainer tooling; skip if you do not have KrewHQ (nothing else depends on it).
krewhq-start:    ## KrewHQ session start + recall for this project (fails open if the hub is unreachable)
	scripts/krewhq-session.sh start $(TEAM)

krewhq-handoff:  ## hand this team's context to the next: make krewhq-handoff TEAM=car TO=portal
	scripts/krewhq-session.sh handoff $(TEAM) $(TO)

SCAN_ROUND ?= $(shell date +%Y%m%d-%H%M)
scan:            ## hackathon self-review: scan the repo and article, write hackathon/reports/<round>.md and .json
	$(PY) hackathon/scan_submission.py --repo . --article docs/article/article.md --md hackathon/reports/$(SCAN_ROUND).md --json hackathon/reports/$(SCAN_ROUND).json

.PHONY: pattern-demo pattern-demo-frame
pattern-demo:    ## guardrails recipe offline: patterns/strands/tool_call_intervention.py against the fake decider (make fake-decider first)
	$(PY) patterns/strands/tool_call_intervention.py --offline

pattern-demo-frame: ## vision recipe offline: the drawn frames in harness/frames/ through patterns/strands/frame_intervention.py
	$(PY) patterns/strands/frame_intervention.py
