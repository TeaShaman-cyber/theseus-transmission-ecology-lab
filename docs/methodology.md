# Deterministic v0 methodology

## Independent mathematical witness

For the committed `shared-v0` graph and committed threshold-control contract,
the independent witness must reconstruct the mathematics rather than trust the
primary NumPy outputs.

Frozen witness question:

1. Compute `E - N + P` for the underlying graph.
2. Build the directed incidence matrix and confirm its rank/nullity.
3. Confirm `dim ker(B^T B) = beta_1` for the graph as a 1-dimensional complex.
4. Build the transmission adjacency with convention `A[target, source]`.
5. Form `K0 = KroneckerProduct[A, IdentityMatrix[2]]`.
6. Independently scale `K0` to target spectral radii `0.8` and `1.2` and verify
   the first is below one and the second above one.

The witness is not asked whether viral, cultural, and AI-agent systems are
isomorphic. It verifies only the stated graph/Hodge/spectral calculations.

Observed Wolfram result:

```text
VertexCount = 4
EdgeCount = 5
WeakComponentCount = 1
CycleRank = 2
IncidenceRank = 3
IncidenceNullity = 2
Hodge1Nullity = 2
BaseSpectralRadius ~= 1.22074408460575947536
SubcriticalSpectralRadius = 0.8
SupercriticalSpectralRadius = 1.2
SubcriticalBelowOne = True
SupercriticalAboveOne = True
```

Primary implementation receipt for the same controls reports radii
`0.800000000000001` and `1.1999999999999995`; the difference is ordinary
floating-point representation and does not change the threshold predicates.

## Receipt numeric canonicalization

Computations use ordinary full-precision floating point. Durable JSON receipts
canonicalize finite floating values to 12 significant decimal digits before
serialization. This is an evidence-representation policy, not a claim that
BLAS/LAPACK eigensolver intermediates are bit-identical across machines.

Exact-byte replay therefore means exact equality of the canonicalized receipt
bytes for the same committed experiment inputs and runtime dependency versions.
The policy is declared in experiments/v0/contract.json and bound into run and
control receipts. Nonfinite values fail closed instead of serializing as NaN or
Infinity.

Reverification note: after receipt schema v2 introduced cross-runtime numeric
canonicalization, the independent Wolfram calculation was rerun against the
unchanged graph and controls inputs and bound to execution commit
`2bfe18806ddb182d7869d11876d5cbaa57c20c16`. The mathematical results
remained unchanged.

Second reverification note: after Codex review tightened witness-content
validation, dirty-evidence provenance, and reference-write semantics, the
Wolfram calculation was rerun independently and bound to execution commit
`0e9929a365235b990aca93827034b68118d70ea7`. Graph and controls hashes
remain unchanged and all required mathematical checks reproduced.

Third reverification note: after exact-head review required explicit independent-backend identity,
duplicate scientific-authority validation, and source-bound run horizons, the witness contract
preregistered `WolframLanguageEvaluator`. The graph/Hodge/spectral calculation was rerun through
the MarcoPolo mcporter Wolfram route and bound to execution commit
`9aea5dfb5642cc2fcebac1f4eba6f6dd7d72b4ad`. The graph and controls hashes were unchanged and
the required mathematical checks reproduced.

Fourth reverification note: after the run initial mass became an explicit source-bound control
parameter and diversity metrics gained cross-metric consistency checks, the controls blob changed
without changing the graph or spectral targets. The Wolfram graph/Hodge/spectral calculation was
rerun through the MarcoPolo mcporter Wolfram route and bound to execution commit
`f86cf7745b66c43003df96cf5f2a6d3bbf0b66e2`. All required mathematical checks reproduced.

Fifth reverification note: after research QA adopted survivor-aware dominant-share bounds,
a shared survival/extinction tolerance, and joint Shannon entropy/share feasibility checks,
the execution source changed without changing the frozen graph or control targets. The Wolfram
graph/Hodge/spectral calculation was rerun through the MarcoPolo mcporter Wolfram route and
bound to execution commit `38511ae57542db0df48ace40f1eed5f47b87e61b`. All required mathematical checks reproduced.

Sixth reverification note: after evidence generation was made fail-closed on a dirty
execution surface and `survival_tolerance` was preregistered as explicit metric
semantics, the execution source changed while the frozen graph and control targets
remained unchanged. The Wolfram graph/Hodge/spectral calculation was rerun through
the MarcoPolo mcporter Wolfram route and bound to execution commit
`0096a9becb8561a58b6cb7811c1e648016ddc9ea`. All required mathematical checks reproduced.

Seventh reverification note: the independent Wolfram witness is now backed by a
versioned executable recipe at `experiments/v0/witness/wolfram-v0.wl`, and the
receipt binds the exact source recipe digest rather than only naming the backend.
That exact recipe was executed through the MarcoPolo mcporter Wolfram route and
bound to execution commit `a3db87d8aa5f2a4ecb91decfd1280990f97de9bc`.
All required graph/Hodge/spectral checks reproduced.

Eighth reverification note: after the execution-surface guard was extended to include
the package initializer, the exact versioned Wolfram witness recipe was rerun through
the MarcoPolo mcporter route and rebound to execution commit
`b4497ec5c6c67afbbab5b6e69564ee1678a0e4bf`. The graph, controls, recipe digest,
and all required mathematical results were unchanged.

Seventh reverification note: after strict JSON input parsing and generalized package-level
execution-surface provenance were added, the execution source changed while the frozen graph,
controls, and versioned Wolfram recipe remained unchanged. The exact committed recipe was rerun
through the MarcoPolo mcporter Wolfram route and bound to execution commit
`18fbc55f8c361e91aa8e895f86efe03e6be93c5d`. All required mathematical checks reproduced.

Eighth reverification note: metamorphic QA exposed representation-dependent initial seeding.
Deterministic v0 now preregisters the seed node and one named seed variant per substrate, and
run-receipt schema v3 records those semantic identities with the initial mass. After the controls
and contract were updated, the exact committed Wolfram graph/Hodge/spectral recipe was rerun
through MarcoPolo/mcporter and bound to execution commit
`c5e84131f257a166109ef75667c627c5e661287c`. The graph and spectral targets are unchanged;
all required mathematical checks reproduced.

Ninth reverification note: exact-head review showed that hashing a Wolfram recipe did not prove
which graph/control values the remote execution actually consumed. Deterministic v0 now uses a
versioned source-consuming adapter (`experiments/v0/witness/wolfram_v0_adapter.py`) that reads the
exact source-commit graph and controls, renders those values into the versioned Wolfram recipe,
and binds both adapter and recipe digests into witness schema v2. The adapter was executed from a
detached checkout of execution commit `f9db32e0c6e1d5ab83f627e5e946fc93d0b04938` through the
established MarcoPolo/mcporter `WolframLanguageEvaluator` route. The resulting witness was
`VERIFIED`; all required graph/Hodge/spectral checks reproduced with authority `NONE`.
