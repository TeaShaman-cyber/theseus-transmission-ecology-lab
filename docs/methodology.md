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
