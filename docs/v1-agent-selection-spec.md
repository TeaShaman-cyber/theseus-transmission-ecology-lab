# v1 two-stage agent selection — design specification

Status: **DESIGN ONLY**. No implementation or scientific promotion is authorized by this document.

## Motivation

Deterministic v0 implements evaluator pressure as post-adaptation target weighting. Issue #39 established that the historical research framing did not uniquely justify target-only placement, while an observed engineering lineage exposed meaningful selection surfaces both before transfer and after local adaptation. Issue #40 therefore promotes a separate v1 design line rather than rewriting v0 in place.

## Minimal model

The three-stage product first defines the **variant-local** transformation for a column vector `u_t`:

```text
u_source_ready = W_source @ u_t
u_adapted      = V @ u_source_ready
u_persistent   = W_target @ u_adapted
u_{t+1}         = u_persistent
```

Equivalently, the local variant operator is:

```text
B_variant = W_target @ V @ W_source
```

The experiment itself still evolves the existing node-by-variant global state. For graph adjacency `A`, transmission scale `s`, `N` graph nodes, and identity `I_N`, the v1 lift is:

```text
z_source_ready = (I_N ⊗ W_source) @ z_t
z_adapted      = s * (A ⊗ V) @ z_source_ready
z_persistent   = (I_N ⊗ W_target) @ z_adapted
z_{t+1}        = z_persistent
```

so the complete global operator remains:

```text
K_global = s * (A ⊗ (W_target @ V @ W_source))
```

This preserves v0 graph propagation and `transmission_scale`; only the variant factor is refined. The two-variant fixture below is a local stage-placement oracle, not a replacement for the graph-level simulation.

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

A claim about **stage placement for an exercised lineage** requires stage-local witnesses. Missing stage witnesses force `stage_attribution = UNKNOWN`; matching only the final state cannot upgrade that result. The minimal one-hot fixture below is not a parameter-identification experiment and cannot identify unexercised columns of `V`, `W_source`, or `W_target`.

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

Acceptance is not merely that totals differ. For the exercised `a1` lineage, the intermediate witnesses must identify **where** each difference was introduced. This fixture makes no claim to recover arbitrary matrix parameters. Any later parameter-identification claim must add linearly independent initial states (at minimum both basis vectors for the two-variant fixture) and demonstrate identifiability separately.

## Metric carry-forward

- `spectral_radius`: keep as a regime summary for the composed operator; not a stage locator.
- `cycle_rank_beta1`: keep as a topology control.
- `total_mass_by_step`: keep; primary transient witness for stage timing.
- `variant_shannon_entropy`, `surviving_variant_count`, `dominant_variant_share`, `time_to_extinction_or_horizon`: keep as outcome/composition metrics.
- `perturbation_recovery_ratio`: keep only when the perturbation stage is explicit.

## Minimal receipt contract

A step receipt includes the relevant state plus `source_ready`, `adapted`, `persistent`, `next_state`, exact bindings for `V`, `W_source`, `W_target`, fixture and source revision, plus `stage_attribution`. Global receipts additionally bind `A`, `transmission_scale`, graph fixture, and node/variant dimensions.

For **stage-attribution verdicts**:

A matched identity control is a paired intervention, not merely another receipt. It must bind the exact control receipt/reference and keep every nonintervened field identical to the tested case: input state, `V`, graph fixture/`A`, `transmission_scale`, opposite gate, node/variant dimensions, horizon/step, and numeric policy. The only allowed difference is replacement of the attributed gate with identity.

- `PASS`: all required witnesses are present, bound and internally consistent; the matched identity control satisfies the equality contract above; and every claimed non-identity stage differs from that control witness at canonical precision.
- `UNKNOWN`: stage attribution cannot be established, including final-state-only evidence, an extinct/zero state, or an exercised state on which a claimed gate is observationally identical to its valid matched identity control.
- `FAIL`: contradictory state, shape mismatch, non-finite/negative values, binding mismatch, omitted identity control, missing control reference, or any nonintervened-field mismatch between tested and control receipts.

A structurally valid receipt may therefore still have `stage_attribution = UNKNOWN`. `UNKNOWN` must never become `PASS` only because the final state matches.

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

The two-stage refinement is unsupported if no observed lineage can independently identify a source-side gate and a target-side persistence gate. The first fixture tests **stage-placement observability for one exercised lineage**, not uniqueness of the full factorization. If a later experiment claims parameter identification, it fails that stronger claim whenever distinct parameterizations reproduce all declared intermediate observations across the required linearly independent inputs.

Do not add stochasticity, nonlinear gates, or multi-artifact composition until this deterministic stage-identification contract earns them through a concrete unresolved mechanism.

## Authority boundary

This spec defines a falsifiable candidate model. Scientific disposition remains human-reviewed; automated QA has no scientific authority. Deterministic-v0 disposition remains tracked separately in issue #10. Implementation promotion from this design requires a separate reviewed change.
