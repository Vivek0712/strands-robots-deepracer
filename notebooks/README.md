# Notebooks

`decider_gate_walkthrough.ipynb` teaches how a Strands Decider 2B decision guards a robot's motor
commands: the System One API in one request, the typed question set, grounded versus invented
arguments, the camera-frame questions on the drawn harness frames, the fail-closed rows (a failed,
slow or missing decider is a Deny), measured and recorded latency with the local 2B next to Amazon
Nova Pro on Bedrock, and the wiring into a Strands `Agent` on Amazon Bedrock with a run recorded
against the real model. No car, no GPU. The executed copy is committed with its outputs;
`decider_gate_walkthrough.html` is the same notebook for reading without Jupyter.

## Run it

```bash
uv pip install --python .venv/bin/python -e ".[notebook]"
.venv/bin/jupyter lab notebooks/decider_gate_walkthrough.ipynb
```

Headless, from `notebooks/`, writing the outputs into the file:

```bash
cd notebooks
../.venv/bin/jupyter nbconvert --to notebook --execute --inplace decider_gate_walkthrough.ipynb \
    --ExecutePreprocessor.timeout=600
../.venv/bin/jupyter nbconvert --to html decider_gate_walkthrough.ipynb
```

The first cell honours `DECIDER_URL`. When it is not set, the notebook uses a port of its own,
`http://127.0.0.1:8113`, and starts the fake decider there (`python -m harness.fake_decider
--port 8113`) when nothing answers; the last cell stops it. It does not use the sim stack's fake
on 8111 by default because section 4 flips the fake's shared camera label, which a sim run on the
same machine would see.

For the real model, serve it on a port of its own and point the notebook at it; the model on
Metal takes one request at a time, so do not run anything else against that port:

```bash
strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --vision --port 8112 --device mps
curl -s http://127.0.0.1:8112/health
DECIDER_URL=http://127.0.0.1:8112 .venv/bin/jupyter lab notebooks/decider_gate_walkthrough.ipynb
```

Against a real server the injected-failure knobs in section 4 are skipped (a real server has no
`/control`); the no-frame and dead-port rows still run.

Section 6 calls Amazon Bedrock only when `RUN_BEDROCK=1` is set and an AWS profile with Bedrock
access is in the environment (`us.amazon.nova-pro-v1:0` in us-east-1; `BEDROCK_MODEL_ID`
overrides). The recorded run in the markdown cell below it was made against the real decider on
2026-10-22.

Physics stops the car; the decider explains.
