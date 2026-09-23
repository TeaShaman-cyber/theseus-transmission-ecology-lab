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

### Matrix domains

The stage meanings are part of the contract, not inferred from any factorization that happens to reproduce the same composed operator.

- `V` is the same transition family as deterministic v0: a non-empty square, finite, nonnegative **column-stochastic** matrix. With `n` variants, `V.shape == (n, n)`, and every column must sum to one under the v0 canonical tolerance (`rtol = 0`, `atol = 1e-12`). A sub-stochastic or otherwise mass-removing `V` is invalid rather than being reinterpreted as selection.
- `W_source` and `W_target` are **diagonal weighting operators**, not arbitrary dense transforms. Each is `diag(w)` for a length-`n` vector of finite nonnegative weights. Off-diagonal mass is invalid because variant conversion belongs to `V`, not to a selection gate.
- `V`, `W_source`, and `W_target` must share the same variant dimension and ordering. Identity controls use the exact `n x n` identity for the corresponding gate.
- Global receipts must validate these local domains before constructing the Kronecker lift. A receipt with an invalid transition/gate domain is `FAIL`, not a different stage interpretation and not `UNKNOWN`.

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
- `total_mass_by_step`: keep as an end-of-complete-step outcome trajectory; **not** a stage locator. Stage timing is established only from the stage-local `source_ready`, `adapted`, and `persistent` witnesses (and totals derived from those witnesses when useful).
- `variant_shannon_entropy`, `surviving_variant_count`, `dominant_variant_share`, `time_to_extinction_or_horizon`: keep as outcome/composition metrics.
- `perturbation_recovery_ratio`: keep only when the perturbation stage is explicit.

## Minimal receipt contract

A step receipt includes the relevant state plus `source_ready`, `adapted`, `persistent`, `next_state`, exact bindings for `V`, `W_source`, `W_target`, fixture and source revision, plus `stage_attribution`. The stage-local total masses are deterministic derivations of those three intermediate states and may be recorded for convenience, but only the bound intermediate witnesses carry attribution authority. Global receipts additionally bind `A`, `transmission_scale`, graph fixture, and node/variant dimensions.

For **stage-attribution verdicts**:

A matched identity control is a paired intervention, not merely another receipt. **Each claimed stage has its own control reference.** For source-stage attribution, replace only `W_source` with identity and compare `source_ready`; for target-stage attribution, replace only `W_target` with identity and compare `persistent`. Every nonintervened field must match the tested case exactly: input state, `V`, graph fixture/`A`, `transmission_scale`, the opposite gate, node/variant dimensions, horizon/step, and numeric policy.

- `PASS`: all required witnesses are present, bound and internally consistent; every claimed stage has its own valid matched identity control; and the witness immediately after that stage differs from its control counterpart at canonical precision.
- `UNKNOWN`: stage attribution cannot be established, including final-state-only evidence, a stage whose **input is already zero** before the claimed gate, an exercised state on which the claimed gate is observationally identical to its valid control, **or an absent/unavailable identity-control receipt**. A nonzero stage input that is annihilated by a valid nonidentity gate may still support `PASS` when its immediate matched identity-control witness remains nonzero and all bindings match.
- `FAIL`: contradictory state, shape mismatch, non-finite/negative values, binding mismatch, or a supplied control whose reference, shape, nonintervened fields, or declared intervention are invalid/mismatched.

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
