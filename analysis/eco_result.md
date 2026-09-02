# E-co: multi-atomic co-occurrence SFT closes the held-out composition gap (2026-08-30, seed 1)

Recipe = RA-v1 stitched SFT with ONE change: each atomic row is grouped with
U{0..3} extra INDEPENDENT atomic tasks (1-4 defs per answer, multi-task prompt,
one Assemble block per task; `build_ra_sft_data.py --multi_atomic`). Per-op
def counts unchanged (held-out ops still ~400 answers each), no held-out op
ever composed, same 16k train-op d2-4 comps, same init/hyper-params
(job 3267112, `ra_sft_bootstrap_paper_eco_qwen3_4b`, greedy @3072).

| held-out CI | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 |
|---|---|---|---|---|---|---|---|---|
| RA-v1, 3-seed mean | 0.982 | 0.923 | 0.749 | 0.530 | 0.380 | 0.244 | 0.135 | 0.086 |
| RA-v1 best seed (d14) | 1.000 | 0.984 | 0.910 | 0.746 | 0.586 | 0.395 | 0.219 | 0.160 |
| **E-co (seed 1)** | 0.992 | **1.000** | **0.996** | **0.980** | **0.953** | **0.934** | **0.887** | **0.832** |
| decomposed-inference ceiling | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| train-op, E-co | 0.984 | 1.000 | 1.000 | 1.000 | 0.992 | 0.980 | 0.941 | 0.875 |

- Held-out now tracks train-op within ~0.05 at every depth (d8 0.832 vs
  0.875): the op-familiarity gap of §16 is essentially gone.
- Per-episode held-out recall (unit tests): 0.994 ok at d8, TypeError 0.006
  (v1: 0.67-0.87 ok, TypeError 0.07-0.22). Chimera / signature collapse is gone.
- Remaining failures are MECHANICAL and identical in kind on both test sets:
  d8 held-out 43/256 = episode omission 14 + paren-copy syntax 18 + TypeError
  10; train-op 32/256 = omission 16 + syntax 16. exec_ok == acc.
- Replicates: seed 7 = 1.000/1.000/1.000/0.992/0.969/0.887/0.844; seed 123 = 1.000/0.996/0.945/0.887/0.762/0.586/0.520.
  3-seed mean d2-8 = 1.000/0.997/0.975/0.944/0.888/0.787/0.732 (sd ≤0.04 through d5, 0.09-0.15 at d6-8).

Reading: the "phase transition" from atomically-known to composable is
"having written the def while other defs are present". Composition data is
not required for it, nor per-op frequency — only the context shape of atomic
practice. This is the user's proposed intervention (random 0-3 extra
independent tasks) and it is op-agnostic.
