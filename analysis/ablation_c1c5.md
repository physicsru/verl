# C1-C5: what actually matters for held-out composition (2026-09-01)

Single-variable ablations around E-co (all 1 seed unless noted; v1 / E-co are
3-seed means; sd at d6-8 can reach ±0.15 — replicate before leaning on deep-
depth orderings). Atomic side "co-oc" = E-co's grouping (each atomic answer
holds 1-4 independent tasks; per-op def counts unchanged). Standard held-out
test set (mixed structures), greedy @3072. Jobs: c1-c5 = 3274458-62 /
3275134-6; data `sft_bootstrap_c{1..5}`; reports `ci_ra_abl_c{1..5}_b3072*.md`.

| cell | atomics | comps | d2 | d3 | d4 | d5 | d6 | d7 | d8 |
|---|---|---|---|---|---|---|---|---|---|
| d1-var | single | none | 0.203 | 0.035 | 0.000 | 0 | 0 | 0 | 0 |
| **C1** | co-oc | **none** | 1.000 | 0.977 | 0.742 | 0.531 | 0.355 | 0.211 | 0.109 |
| **C2** | co-oc | 2,068 pure chains d2 | 0.992 | 0.918 | 0.598 | 0.344 | 0.184 | 0.094 | 0.070 |
| **C3** | co-oc | 2,059 mixed d2 | 1.000 | 0.992 | **0.898** | 0.727 | 0.586 | 0.359 | 0.242 |
| **C4** | co-oc | 12,452 mixed d2 | 1.000 | 0.887 | 0.672 | 0.449 | 0.301 | 0.195 | 0.113 |
| E-co (3s) | co-oc | 15,979 mixed d2-4 | 1.000 | 0.997 | **0.975** | 0.944 | 0.888 | 0.787 | 0.732 |
| v1 (3s) | single | 15,979 mixed d2-4 | 0.923 | 0.749 | 0.530 | 0.380 | 0.244 | 0.135 | 0.086 |
| **C5** | single, held-out ×10 freq | 15,979 mixed d2-4 | 0.934 | 0.805 | 0.543 | 0.332 | 0.172 | 0.082 | 0.066 |

## Causal readings (each row = one controlled pair)

1. **Frequency is NOT the mechanism (C5 vs v1).** Boosting every held-out
   op's atomic answers 10× (to the train ops' ~4k) changes nothing
   (d4 0.543 vs 0.530). With the same comps, switching the SAME-frequency
   atomics to co-occurrence contexts gives d4 0.975 (E-co). The phase
   transition is *practice under competition*, not binding strength by
   repetition — exactly the claim needed for "in the wild, per-op frequency
   is uncontrollable; context shape is the available lever".
2. **Composition demonstrations are not necessary (C1 vs d1-variant).**
   Co-occurrence atomics ALONE — zero compositions — reach d4 0.742 (the
   single-context version collapses to 0). Multi-task answers teach both the
   load-robust binding and a multi-def answer shape that transfers to nested
   composition. (Corroborated independently by P0b: no serial data at all,
   held-out chains d4 0.539.)
3. **Structure diversity is the most valuable property of comp data (C3 vs
   C2).** At identical count and depth, mixed structures beat pure chains by
   +0.30 (d4) / +0.40 (d6). Pure-chain data even UNDERPERFORMS no comps at
   all (C2 < C1 at every depth ≥ 4).
4. **More same-kind comp data HURTS (C4 vs C3).** 6× more mixed-d2 comps:
   d4 0.898 → 0.672. Same force as §15's RFT harm: volume of same-depth
   train-op comps specializes the model onto train-op patterns and squeezes
   held-out. Inverted U over comp volume at fixed diversity.
5. **Depth diversity compensates volume (E-co vs C4).** Adding depths 3-4
   (+3.5k rows) recovers 0.672 → 0.975 despite MORE data. Diversity (of
   structure and depth) is what scales, not quantity.

Caveats: C1-C4/C5 are single-seed; the C3>C4 inversion and deep-depth
orderings should be replicated (2 more seeds each) before publication. C5's
boost uses duplicated verified rows (not fresh unique prompts) — matches how
frequency would arrive in practice, but a unique-prompt variant is a possible
robustness check.


---

# 3-SEED UPDATE (2026-09-01, jobs 3275724-43): final table and revised readings

Held-out d4 (mean ± sd over seeds 1/7/123): C1 0.66 ± 0.14 · C2 0.60 ± 0.04 ·
C3 0.77 ± 0.11 · C4 0.70 ± 0.03 · C5 0.63 ± 0.11 · v1 0.53 ± 0.15 ·
**E-co 0.97 ± 0.02**. (d8: C1 0.08 · C2 0.08 · C3 0.17 · C4 0.12 · C5 0.14 ·
v1 0.09 · E-co 0.73 ± 0.15.)

Revisions after replication:
1. **E-co's dominance is the robust headline** — the only cell near ceiling
   AND the only one with tight seed variance (±0.02 at d4 vs ±0.11-0.15
   elsewhere). Stability itself is part of the effect.
2. **Frequency (C5) softened**: 0.63 ± 0.11 vs v1 0.53 ± 0.15 — a small,
   noise-scale bump (one high seed), nowhere near co-occurrence. Claim
   becomes "frequency cannot substitute for competition-context practice",
   not "frequency does nothing".
3. **C1 (no comps) holds as a band**: 0.66 ± 0.14 ≫ 0 — composition without
   any composition data is real; magnitude seed-dependent.
4. **Structure diversity (C3 vs C2) holds**: +0.30/+0.15/+0.08, positive in
   every seed pair (mean +0.17 at d4).
5. **"Volume hurts" (C4 < C3) RETRACTED**: the inversion flipped at seed 123;
   at 3 seeds C3 0.77 ± 0.11 vs C4 0.70 ± 0.03 — volume at fixed diversity
   is roughly neutral. The robust comp-side factor is **depth diversity**
   (E-co 0.97 vs C4 0.70, non-overlapping bands).
