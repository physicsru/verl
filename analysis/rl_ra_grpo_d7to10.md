# GRPO on RA-v1, train-op depth 7-10 — stopped at step 80 (2026-08-29, job 3208916)

Init RA-v1 (d14 ckpt). Train = 4,855 mixed-outcome prompts, compositions of
10 train ops at depth 7-10 (3 probe train ops excluded from RL comps; 12
held-out ops never in any training). GRPO 64×8, KL 0.01, RA reward
(correctness + 0.2 × episode-unit-test fraction), response budget 4096.
Val every 10 steps, greedy: heldout (12 ops, d1-12), rlops (10 RL ops,
d1-12), probe (train-op test rows containing ≥1 probe op, d1-8). Stopped by
the pre-agreed rule (two consecutive held-out declines); step-50 ckpt kept:
`checkpoints/compositional/rl_ra_grpo_d7to10_qwen3_4b/global_step_50/actor/huggingface`.
Per-family trajectories: `analysis/ci_rl_ra_grpo_d7to10_{heldout,rlops,probe}.md`.

| step | train reward | rlops d8 / d10 / d12 | probe d8 | heldout d4 / d6 / d8 / d12 |
|---|---|---|---|---|
| 0 | 0.80 | 0.883 / 0.711 / 0.555 | 0.844 | 0.750 / 0.395 / 0.164 / 0.051 |
| 10 | 1.17 | 0.984 / 0.957 / 0.844 | 0.984 | 0.758 / 0.414 / 0.172 / 0.047 |
| 20 | 1.19 | 0.992 / 0.969 / 0.898 | 0.992 | 0.758 / 0.418 / 0.168 / 0.039 |
| 30 | 1.19 | 0.992 / 0.980 / 0.930 | 0.996 | 0.750 / 0.398 / 0.176 / 0.039 |
| 50 | 1.20 | 1.000 / 0.984 / 0.922 | 0.992 | 0.758 / 0.398 / 0.176 / 0.035 |
| 60 | 1.20 | 1.000 / 0.984 / 0.930 | 0.992 | 0.762 / 0.402 / 0.164 / 0.031 |
| 70 | 1.20 | 0.996 / 0.988 / 0.930 | 0.992 | 0.695 / 0.332 / 0.121 / 0.020 |
| 80 | 1.20 | 0.996 / 0.992 / 0.930 | 0.996 | **0.660 / 0.297 / 0.109 / 0.016** |

Findings
1. RL works fast on what it trains on: rlops d8-12 0.88/0.71/0.55 → 0.98/0.96/0.84
   in 10 steps, ~ceiling by step 30 (d12 0.93 — depth 11-12 were never trained:
   depth extrapolation of the RL gain is real for familiar ops).
2. The gain transfers to the PROBE ops (SFT-composed, never in an RL
   composition): d8 0.84 → 0.98 at step 10, in lockstep with rlops. So the
   learned improvement is not tied to the 10 RL ops' identities.
3. It does NOT transfer to held-out ops: every held-out depth flat within
   ±0.02 for 60 steps, then declining (d4 −0.10, d8 −0.055 by step 80) while
   train reward is saturated at 1.20 — the same "continued training on
   train-op comps squeezes held-out" pattern as the RFT round (§15), delayed
   by the KL term, not prevented.
4. Reading: the transferable part of the RL gain is confined to ops that
   have been practiced INSIDE compositions at some point (RL ops + probe ops
   via SFT). Ops known only atomically gain nothing — the held-out failure
   (wrong signature / body under multi-def load, §16) is a per-op familiarity
   deficit that a better composition procedure does not touch. This is the
   pre-registered "RL adds nothing to held-out" outcome, now measured.
