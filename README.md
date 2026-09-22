# Theseus Transmission Ecology Lab

This repository tests whether selected transmission-dynamics invariants survive
a substrate change from virus to meme to AI-agent systems.

It does **not** claim that biological, cultural, and agent systems are identical.

- `tools/dev/check` verifies repository mechanics.
- `tools/research/check` verifies the declared research contract once that
  endpoint is implemented.
- Neither endpoint has scientific acceptance authority.

The initial research line is tracked by
[`TeaShaman-cyber/theseus-research#72`](https://github.com/TeaShaman-cyber/theseus-research/issues/72).
## Deterministic v0 acceptance slice

The manual `deterministic-v0-replay` workflow is an acceptance-slice witness,
not a per-push correctness oracle. It checks two different propositions:

1. the exact execution commit bound by the reference receipts regenerates the
   same receipt bytes from a clean detached worktree;
2. the current repository head still satisfies the research contract through
   `tools/research/check`.

A green workflow is **not** scientific acceptance. It does not choose the v0
disposition and it grants no merge, release, or research-scope authority.
