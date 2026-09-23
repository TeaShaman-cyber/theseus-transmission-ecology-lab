# v1 two-stage agent selection — design specification

Status: **DESIGN ONLY**. No implementation or scientific promotion is authorized by this document.

## Motivation

Deterministic v0 implements evaluator pressure as post-adaptation target weighting. Issue #39 established that the historical research framing did not uniquely justify target-only placement, while an observed engineering lineage exposed meaningful selection surfaces both before transfer and after local adaptation. Issue #40 therefore promotes a separate v1 design line rather than rewriting v0 in place.

## Minimal model

For column-vector state `x_t`:

```text
x_source_ready = W_source @ x_t
x_adapted      = V @ x_source_ready
x_persistent   = W_target @ x_adapted
x_{t+1}        = x_persistent
```

Equivalently:

```text
x_{t+1} = W_target @ V @ W_source @ x_t
```

- `W_source`: pre-transfer success or exposure gate: ranking, visibility, permission to propagate, source reputation, pre-transfer review.
- `V`: local adaptation / transformation. Columns are source variants; rows are destination variants.
- `W_target`: post-adaptation viability: verification, acceptance, retention, persistence, rejection.

Identity limits are explicit controls:

```text
W_source = I  -> target-only  W_target @ V
W_target = I  -> source-only  V @ W_source
both = I      -> V
```

## Identifiability boundary

Observing only `K = W_target @ V @ W_source` does not uniquely identify the factorization. A final trajectory may establish composed dynamics but not where selection acted.

A stage claim therefore requires stage-local witnesses. Missing stage witnesses force `stage_attribution = UNKNOWN`; matching only the final state cannot upgrade that result.

## First deterministic fixture

```text
x0 = [0, 1]
V  = [[0.95, 0.08],
      [0.05, 0.92]]
W  = diag(1.0, 0.95)
```

| case | `W_source` | `W_target` | `source_ready` | `adapted` | `persistent = next_state` | total |
|---|---|---|---|---|---|---:|
| target-only | `I` | `W` | `[0, 1]` | `[0.08, 0.92]` | `[0.08, 0.874]` | 0.954 |
| source-only | `W` | `I` | `[0, 0.95]` | `[0.076, 0.874]` | `[0.076, 0.874]` | 0.950 |
| two-stage | `W` | `W` | `[0, 0.95]` | `[0.076, 0.874]` | `[0.076, 0.8303]` | 0.9063 |

Acceptance is not merely that totals differ. The intermediate witnesses must identify **where** each difference was introduced.

## Metric carry-forward

- `spectral_radius`: keep as a regime summary for the composed operator; not a stage locator.
- `cycle_rank_beta1`: keep as a topology control.
- `total_mass_by_step`: keep; primary transient witness for stage timing.
- `variant_shannon_entropy`, `surviving_variant_count`, `dominant_variant_share`, `time_to_extinction_or_horizon`: keep as outcome/composition metrics.
- `perturbation_recovery_ratio`: keep only when the perturbation stage is explicit.

## Minimal receipt contract

A step receipt includes `x`, `source_ready`, `adapted`, `persistent`, `next_state`, exact bindings for `V`, `W_source`, `W_target`, fixture and source revision, plus `stage_attribution`.

- `PASS`: all required stage witnesses are present, bound and internally consistent.
- `UNKNOWN`: stage attribution cannot be established, including final-state-only evidence.
- `FAIL`: contradictory state, shape mismatch, non-finite/negative values, binding mismatch, or omitted identity control.

`UNKNOWN` must never become `PASS` only because the final state matches.

## Real-lineage discriminator

The sealed-ack lineage recorded in issue #39 provides one concrete specimen:

```text
source field scar
  -> shared exposure
  -> local adaptation to a different client mechanism
  -> target-side regression/fix
  -> release + later live repaired-path observation
```

It supports the existence of separately observable pre-transfer and post-adaptation selection surfaces. It does not identify numeric weights and is not parameter-fitting evidence.

## Falsifiers and stopping rules

The two-stage refinement is unsupported if no observed lineage can independently identify a source-side gate and a target-side persistence gate. A fixture also fails to identify stages if distinct parameterizations reproduce the same declared intermediate observations and final trajectory.

Do not add stochasticity, nonlinear gates, or multi-artifact composition until this deterministic stage-identification contract earns them through a concrete unresolved mechanism.

## Authority boundary

This spec defines a falsifiable candidate model. Scientific disposition remains human-reviewed; automated QA has no scientific authority. Deterministic-v0 disposition remains tracked separately in issue #10. Implementation promotion from this design requires a separate reviewed change.
