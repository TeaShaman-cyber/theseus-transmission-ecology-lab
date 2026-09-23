# Deterministic v1 run

Run the reviewed canonical A/B/C fixture from a clean checkout:

```sh
tools/run-v1 --output receipts/v1/canonical.json
```

The durable receipt binds the exact Git source revision and fixture hash, includes stage-local witnesses plus separate matched identity controls for every claimed nonidentity gate, and reports only machine stage-attribution status. `scientific_authority` remains `NONE`; the command does not assign a scientific disposition.
