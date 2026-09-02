# GRPO on RA-d12, train-op depth 1-4 — the user's easy-to-hard design (2026-08-30)

Init = RA **d12** bootstrap ckpt (SFT saw depth-1 atomics of all 25 ops + depth-2
compositions of the 13 train ops only; `ra_sft_bootstrap_paper_d12_qwen3_4b/
global_step_346`). RL prompts = compositions of the 10 RL train ops at depth
1-4 (3 probe train ops excluded), 2,170 prompts after dropping only the
ALL-CORRECT groups of the init's T=1 n=8 rollout (all-wrong groups KEPT, per
user). GRPO 64×8, KL 0.01, RA reward (correctness + 0.2 × episode-unit-test
fraction), 5 epochs = 165 steps. Two replicates: job 3242468 (gj26) and the
user's job 3255766 (go39, `*_go39` experiment). Greedy val every 10 steps on
heldout (12 ops, d1-12), rlops (10 RL ops, d1-12), probe (train-op test rows
with ≥1 probe op, d1-8). Trajectories: `analysis/ci_rl_ra_grpo_d1to4_d12init[_go39]_{heldout,rlops,probe}.md`.
Ckpts: `checkpoints/compositional/rl_ra_grpo_d1to4_d12init[_go39]_qwen3_4b/global_step_{50,100,150}`.

## Step 0 → step 160 (gj26 run; go39 replicate in parentheses)

| family | d2 | d4 | d6 | d8 | d10 | d12 |
|---|---|---|---|---|---|---|
| rlops step 0 | 0.996 | 0.887 | 0.543 | 0.367 | 0.164 | 0.082 |
| rlops step 160 | 1.000 | 1.000 | 0.992 (0.977) | **0.922** (0.887) | 0.727 (0.641) | 0.617 (0.535) |
| probe step 0 | 1.000 | 0.819 | 0.535 | 0.216 | – | – |
| probe step 160 | 1.000 | 0.994 | 0.965 (0.934) | **0.812** (0.744) | – | – |
| heldout step 0 | 0.965 | 0.727 | 0.367 | 0.121 | 0.066 | 0.027 |
| heldout step 160 | 0.930 (0.902) | **0.457** (0.457) | **0.207** (0.188) | 0.098 (0.094) | 0.031 (0.023) | 0.008 (0.012) |

Trajectory (gj26): heldout d4 0.73 → 0.66 (step 10) → 0.50 (50) → 0.46 (160);
d6 0.37 → 0.25 (10) → 0.21; rlops d8 0.37 → 0.69 (10) → 0.91 (50) → 0.92; probe
d8 0.22 → 0.49 (10) → 0.78 (50) → 0.81. Train reward 0.52 → 1.14.

## Findings

1. **RL installs deep composition from depth-1-4 practice — for practiced ops.**
   rlops d8 0.37 → 0.92, d12 0.08 → 0.62 with NO training beyond depth 4:
   genuine easy-to-hard depth extrapolation. It transfers to the probe ops
   (SFT-composed at depth 2, never RL-composed): d8 0.22 → 0.81. Both
   replicates agree.
2. **It damages the never-composed (held-out) ops from the first 10 steps**:
   d4 0.73 → 0.46 (−0.27), d6 0.37 → 0.21, d3 0.91 → 0.70. Monotone decline
   throughout, both replicates. Held-out is worse than at the start at every
   depth ≥ 2.
3. **RL vs SFT on the same depth of train-op compositions, same init family**:
   SFT d2-4 (d14, from stage15b) → held-out d4 0.75 (seed-lucky; 3-seed band
   0.53 ± 0.15); d12 → RL d1-4 → held-out d4 0.46. RL is at the bottom of the
   SFT band or below, while beating SFT on train-op depth (rlops d8 0.92 vs
   d14's train-op d8 0.85). RL specializes harder.
4. Consistent with the d7-10 line (`rl_ra_grpo_d7to10.md`): across three RL
   runs, the gain covers exactly the ops that have ever appeared inside a
   composition (RL ops directly, probe ops via SFT) and never the ops known
   only atomically. The "meta composition procedure" the user hypothesized is
   learned — but it only operates on op representations that composition
   practice has already shaped; it does not pull atomically-known ops into
   the composable set. The held-out gap (wrong signature/body under multi-def
   load, §16) is a per-op representation issue, and RL on train-op
   compositions makes it worse, not better.

## Ops-side gotcha
Both jobs sat idle 5 h after "trainer exited with 0": vLLM EngineCore /
Ray workers did not exit, so `mpirun` never returned and the driver's CI
step never ran (qdel'd, CI extracted by hand with `compositionality_index.py
--log --source`). Add a Ray/vLLM teardown or a post-train timeout to
`train_per_node.sh` before the next RL run.
