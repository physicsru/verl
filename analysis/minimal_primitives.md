# Minimal primitives: SFT vs RL on width-2/depth-2, and the extrapolation map (2026-08-31)

Question (user): are width-2 parallel (two independent atomic tasks, multi-task
format, all 25 ops) and depth-2 serial (pure chains, train ops only) sufficient
building blocks — and is SFT needed to install them, or does RL from an
atomic-only model suffice? Training NEVER contains test structures; evaluation
is the structured map (`generate_structured.py`: serial d1-8 / parexpr w1-8 /
parmt w1-8 / grids, × held-out & train-op families). Full tables:
`analysis/structured_map_round{1,2,3}.md`. One seed per variant.

## Variants
| name | recipe |
|---|---|
| p0b | SFT width {1,2} pairs only (no serial) |
| p1b | SFT width {1,2} + 2,068 pure d2 chains |
| rl_exp1 | GRPO from d1 (atomic-only) on serial-d2 + parmt-w2 (step-50 ckpt) |
| rl_exp2 | GRPO from p1b on serial-d3 + parmt-w3 (step-100) |
| rl_exp3 | GRPO from d1 on d2+w2+d3+w3 mixed (step-150) |
| eco | SFT: width 1-4 multi-atomic + 16k mixed d2-4 train-op comps (reference) |

## Key cells (held-out / train-op)

| cell | p0b | p1b | rl_exp1 | rl_exp2 | rl_exp3 | eco |
|---|---|---|---|---|---|---|
| serial d4 | 0.54/0.59 | 0.52/0.87 | 0.61/1.00 | 0.63/1.00 | 0.63/0.96 | 0.99/1.00 |
| serial d8 | 0.00/0.03 | 0.01/0.19 | **0.03/0.90** | **0.13/0.88** | 0.02/0.85 | **0.95/0.98** |
| parexpr w8 | 0.07/0.14 | 0.02/0.36 | 0.24/**0.98** | 0.27/0.82 | 0.39/0.88 | 1.00/1.00 |
| parmt w4 | 0.90/0.98 | 0.68/0.80 | 0.00/0.00 | **1.00/1.00** | 0.00/0.00 | 1.00/1.00 |
| parmt w8 | **0.48/0.72** | 0.00/0.02 | 0.00/0.00 | **0.76/0.95** | 0.00/0.00 | 1.00/1.00 |
| gridexpr w4d4 | 0.00/0.00 | 0.00/0.01 | 0.03/**0.91** | 0.00/0.13 | 0.08/0.90 | 0.87/0.91 |
| gridmt w2d2 | 0.20/0.29 | 0.37/0.54 | **0.71/0.95** | 0.28/0.37 | 0.00/0.00 | 0.65/0.77 |

## Findings

1. **RL can install the primitives from an atomic-only init — no SFT
   demonstration needed** (exp1: serial from all-zero to trained-level in 20
   steps; width w2 discovered by exploration between steps 20-40). The user's
   "是不是需要SFT" — for INSTALLATION, no.
2. **Depth extrapolates only when serial was installed by RL.** Train-op serial
   d2→d8: RL variants 0.85-0.90 vs SFT-on-chains p1b 0.19, p0b 0.03. The RL
   models even compose `+`-expressions (never seen in any form) at w8 = 0.88-0.98
   on train ops, and grids gridexpr w4d4 ≈ 0.90 (exp1/exp3) where every SFT
   primitive variant is at 0. RL-installed skills compose with each other;
   SFT-installed d2 chains stay at d2-4.
3. **Width extrapolates only when installed by SFT on pairs alone, or extended
   by RL from an SFT base.** p0b (pairs only): parmt w8 0.72 (TR). Adding serial
   chains to the SFT (p1b) KILLS width extrapolation (w8 0.02); RL-discovered
   width (exp1) does not extrapolate at all (w3+ = 0); RL on w3 from the SFT
   base (exp2) restores it (w8 0.95). A clean chiasm: depth needs RL, width
   needs the right SFT distribution — and the two interfere when mixed.
4. **Mixing sizes from scratch is the worst curriculum** (exp3): serial snapped
   in 3× slower (steps 60-80, phase-transition-like), width was NEVER
   discovered in 180 steps (the hardened serial format choked multi-block
   exploration; parmt w2 = 0 despite w2 being in the training data), and its
   size-1 behaviour degraded (HO serial-1 0.52). Order matters when
   bootstrapping by reward.
5. **E-co still dominates the map** (only open cell: gridmt ≥ w4, 0.24-0.65) —
   but it uses 16k mixed-structure composition rows; the primitives variants
   use at most 2k chains and no mixed structures. The gap to close with a
   curriculum (install primitives → RL outward) is now measurable per cell.
6. Held-out vs train-op: every variant keeps a familiarity gap at depth
   (exp1 serial d8 0.03 HO vs 0.90 TR) — consistent with the binding story
   (`analysis/heldout_failure_mechanism.md`); E-co closes it (0.95 vs 0.98).

Caveats: one seed per variant (SFT seed variance was ±0.15 before E-co);
RL ckpt choice = best serial point; exp budgets differ (see memory).
