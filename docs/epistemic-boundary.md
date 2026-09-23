# Epistemic boundary

`tools/dev/check` and `tools/research/check` answer different questions.

- Repository QA asks whether the repository state is mechanically consistent.
- Research QA asks whether an experiment satisfies its declared provenance,
  preregistration, controls, reproducibility, witness, and claim-boundary contract.

A research-QA `PASS` is not a truth verdict. Automated QA always reports
`authority = NONE`; scientific disposition remains an explicit reviewed judgment.

The deterministic v0 comparison does not claim that viral, cultural, and AI-agent
systems share microscopic mechanisms. It tests only whether selected mathematical
measurements remain useful under a deliberately narrow common representation.


## Deterministic-v0 agent evaluator semantics

The current agent adapter has a precise **implemented** semantics that must not be
confused with a recovered scientific law. State is a column vector,
`variant_transition` columns are source variants and sum to one, and deterministic
v0 constructs the variant operator as:

```text
W_target @ V
```

where `V` performs one-parent local adaptation and `W_target = diag(evaluator_weights)`
weights the resulting target variant. Operationally, evaluator pressure therefore
acts **after** local adaptation in the current implementation.

Issue #39 records that the historical research prose did not specify this operator
placement. A source-side interpretation (`V @ W_source`) and a two-stage refinement
(`W_target @ V @ W_source`) remain scientifically live alternatives. The existing
v0 receipts therefore establish reproducible behavior of the implemented target-side
model; they do not establish that target-side weighting is the uniquely correct model
of evaluator pressure in real agent ecosystems.

This clarification is post-hoc model documentation. It does not rewrite the
preregistered v0 question, alter existing numerical results, or grant scientific
promotion authority.
