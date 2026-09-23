# Deterministic v1 external replication

This package is for an independent reproduction of the first reviewed v1 A/B/C experiment. It tests **computational reproducibility only**; it does not grant scientific authority or assign a scientific disposition.

## Exact execution source

Checkout exactly:

```text
0aff78fa79171176118a31cecef56313b571ce3f
```

That is the execution source bound inside the canonical durable receipt. The later storage commit only records that receipt.

## Environment

Declared project requirements:

- Python `>=3.11`
- NumPy `2.4.3`

Reference run environment:

- Python `3.11.16`
- NumPy `2.4.3`

No maintainer-only service, token, database, or network API is required by the experiment itself.

## Reproduce

From a clean clone/worktree at the exact execution source:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
tools/run-v1 --output /tmp/theseus-v1-canonical.json
sha256sum /tmp/theseus-v1-canonical.json
```

Expected SHA-256:

```text
2927618e43f5d2003f4e784649d76c22aa915b3d340affc13a4bdb8598718ce8
```

The receipt must also report:

```text
source_revision = 0aff78fa79171176118a31cecef56313b571ce3f
fixture_sha256 = 9af859df17f80e7ea31949bfc90c08020a1a3b86a762d0f632727ff936d69aac
source-only.stage_attribution = PASS
target-only.stage_attribution = PASS
two-stage.stage_attribution = PASS
scientific_authority = NONE
scientific_disposition = null
```

## Return only observable evidence

Please return:

- OS / architecture;
- Python version;
- NumPy version;
- checked-out Git SHA;
- produced receipt SHA-256;
- the produced receipt if it differs;
- any command failure or environment limitation.

Classify the external run as:

- `REPRODUCED`: exact receipt hash and declared bindings match;
- `DIVERGED`: the run completes but observable output differs;
- `UNAVAILABLE`: the required environment or execution path cannot be reproduced.

Do not repair a divergence before reporting the original evidence. A divergence is a useful specimen for the lab.
