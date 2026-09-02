# RA-v2 stitcher campaign — results (2026-08-25)

Spec: `doc/COMPOSITIONAL_HISTORY.md` §10 (sibling `generalization/doc/`). Jobs
2847832/33/34 (`v2`+`v2_sc`, seeds 1/7/123) and 2847939/40 (`v1`, seeds
7/123); v1 seed 1 = the existing d14 checkpoint re-swept @3072
(`trainops_sweep_d14{_ho,}_b3072`). Same init (stage15b/500), same SFT recipe,
same def bodies — only the answer STRUCTURE differs (v1: textual-order
episodes + verbatim-copied Assemble; v2: enumerated+counted plan line,
per-episode arity cue from the call site, sequential `t1..tN` Assemble,
funcless rows; v2_sc: + `Check:` line after each def). Greedy, 3072 tokens,
both test sets. Failure classification: `classify_ra_failures.py` →
`analysis/ra_v2_failure_classification.md`.

## Verdict

**RA-v2 is a regression.** In-distribution depth (d2-4) is a wash within seed
noise; beyond the trained depth every v2 variant collapses far below v1, on
held-out AND on train ops. All three structural changes replaced a
depth-invariant mechanical step of v1 (textual scan, verbatim copy) by a
PARSING task whose error rate grows with nesting depth — and the model then
faithfully executes its own wrong parse. The §10.6 decision rule fires on the
negative branch: the arity cue does not reduce signature errors (it doubles
them), so interference happens before "reading the call site"; format work
stops here, the operator-diversity route is next.

## Headline numbers (3 seeds, mean ± sd; full tables below)

| held-out CI | d2 | d3 | d4 | d5 | d6 | d7 | d8 |
|---|---|---|---|---|---|---|---|
| v1 | 0.923 ± 0.045 | 0.749 ± 0.117 | 0.530 ± 0.153 | 0.380 ± 0.146 | 0.244 ± 0.107 | 0.135 ± 0.060 | 0.086 ± 0.053 |
| v2 | 0.846 ± 0.141 | 0.723 ± 0.183 | 0.489 ± 0.168 | 0.260 ± 0.090 | 0.087 ± 0.032 | 0.026 ± 0.007 | 0.004 ± 0.000 |
| v2_sc | 0.935 ± 0.049 | 0.780 ± 0.066 | 0.514 ± 0.078 | 0.292 ± 0.110 | 0.121 ± 0.051 | 0.025 ± 0.015 | 0.009 ± 0.002 |

| train-op CI | d4 | d5 | d6 | d7 | d8 |
|---|---|---|---|---|---|
| v1 | 0.999 | 0.979 | 0.975 | 0.936 | 0.875 ± 0.023 |
| v2 | 0.965 | 0.852 | 0.596 | 0.243 | 0.070 ± 0.038 |
| v2_sc | 0.961 | 0.811 | 0.496 | 0.194 | 0.060 ± 0.008 |

1. **The published d14 numbers were a lucky seed.** v1 seeds 7/123 land at
   d4 = 0.43/0.41 (d14: 0.75) and d8 = 0.04/0.06 (d14: 0.16). The honest v1
   claim is d2-4 = 0.92/0.75/0.53 ± 0.05-0.15; the "×22 at depth 4" of §14 is
   ×20 on the mean, but with a ±0.15 band. Train-op depth extrapolation
   (0.85-0.91 at d8) IS seed-robust.
2. **v2 breaks depth extrapolation even for familiar ops**: train-op d8
   0.02-0.11 vs v1 0.85-0.91; d6 0.43-0.70 vs 0.96-1.00. v1's format
   extrapolates because nothing in its unit depends on k (§14 pt. 5); v2's
   units do.

## Mechanism (failure classification, first matching bucket, depth ≥ 5)

Buckets: `plan_omission` = a needed func is missing from the enumerated plan
line AND unrecalled; `assembly_wrong` = the model's own `main_solution` gives
the wrong answer even with the REFERENCE defs substituted (isolates the
copy/linearization step from recall); `def_*` = program crashed / wrong with
a complete, correctly-assembled skeleton — i.e. recall content.

| held-out, n=256/depth | ok | truncated | plan_omission | episode_om. | syntax | assembly_wrong | def_NameErr | def_TypeErr | def_wrong |
|---|---|---|---|---|---|---|---|---|---|
| v1_s7 d5 | 70 | 0 | – | 1 | 7 | 0 | 2 | **135** | 41 |
| v1_s7 d8 | 10 | 1 | – | 7 | 32 | 1 | 2 | **163** | 39 |
| v2_s1 d5 | 70 | 3 | **49** | 2 | 24 | **87** | 6 | 5 | 10 |
| v2_s1 d8 | 1 | 22 | **187** | 0 | 3 | **43** | 0 | 0 | 0 |
| v2_sc_s1 d5 | 82 | 3 | **43** | 0 | 1 | **101** | 1 | 3 | 21 |
| v2_sc_s1 d8 | 2 | 9 | **193** | 0 | 0 | **52** | 0 | 0 | 0 |

| train-op, n=256/depth | ok | plan_omission | assembly_wrong | syntax | episode_om. |
|---|---|---|---|---|---|
| v1_s7 d8 | 222 | – | 0 | 22 | 9 |
| v2_s1 d6 / d8 | 110 / 5 | 134 / **220** | 12 / 23 | 0 / 1 | 0 / 0 |
| v2_sc_s1 d6 / d8 | 101 / 13 | 133 / **219** | 22 / 20 | 0 / 0 | 0 / 1 |

Three mechanisms, one per structural change:

- **① Enumerated plan line → omission moved upstream and got 30× worse.**
  Plan incompleteness (per-episode table below) is 0% at k ≤ 3 and then rises
  steeply: v2 held-out d4/d5/d6/d7/d8 = 5/19/47/70/82% (seed 1; seeds 7/123:
  50-54% at d8), train-op d8 = 89%; ~90% of the omitted funcs are also
  unrecalled — the model follows its own plan. v1 recall_incomplete at d8 is
  3%. Enumerating the DISTINCT funcs of a nested skeleton in data-flow order
  is a parse+dedup task trained only at k ≤ 5; v1 emitted episodes by
  scanning the text, which needs no parse. The count cue meant to stop tail
  omission created a front-loaded omission channel instead.
- **② Arity cue → the model mis-counts and then obeys itself.** Per-episode
  TypeError rate (every recalled def unit-tested; independent of omission),
  held-out d8: v1 0.071/0.164/0.223 (seeds 1/7/123) vs v2 0.324/0.238/0.326
  vs v2_sc 0.183/0.327/0.193; d4: v1 0.022/0.112/0.150 vs v2
  0.147/0.063/0.307. Of 1,404 wrong-arity defs in v2_s1 (d ≥ 5), **1,388 sit
  under a cue whose parameter count is itself wrong** (1,000 too many); the
  cue error rate grows d2→d8 = 3.8/9.7/14.5/16.4/20.6/26.0/31.2%, and 89% of
  wrong cues occur where the call's argument subtree contains commas
  (`func_2(func_8(x, 2))` → "2 parameters"). Counting top-level arguments
  of a nested call is the same parsing problem as ①. A1 is REFUTED: the cue
  does not remove the signature mode; it converts parse errors into
  signature errors. (The §16 "46% TypeError" is real for v1 — 65-75% of v1
  failures at d5-8 — but it is not fixed by restating the call site.)
- **③ Sequential Assemble → linearization errors replace paren-copy errors,
  and are more frequent.** `assembly_wrong` = 43-101 per 256 (held-out),
  12-27 (train-op) — of the responses that survive plan omission at held-out
  d8, 43/69 have a wrong `t1..tN` chain. v1's paren-copy syntax errors were
  7-32 per 256. Verbatim copy scales; re-writing an expression tree as SSA
  does not (max 62 temps at depth 8; trained on ≤ ~8).
- **④ Self-check** is the one non-negative change: v2_sc ≥ v2 at every depth
  on held-out (d2-4 +0.09/+0.06/+0.03; per-episode TypeError roughly halved
  at seeds 1/123, not at 7) — but it rides on the broken v2 base, so it is
  not separable here. Worth re-testing on the v1 base if format work resumes.
- Truncation is minor at 3072 (≤ 22/256), funcless rows are fine (d1 = 1.000
  for every v2 seed; v1 seeds 7/123 lose 2-3% at d1 = the funcless artifact
  of §16 — the one v2 change that worked).

## Decision (per §10.6)

- Arity cue did NOT reduce TypeError → "interference happens before reading
  the call site; strong evidence for the diversity route; stop format work."
  Adopted. RA-v1 (textual episodes + verbatim copy) stays the format.
- Anything that adds a k-dependent transformation to the answer (enumerate,
  count, linearize) must be assumed NOT to extrapolate past the trained k.
  Any future format change needs a train-op deep-depth check FIRST — it is
  the cheap detector of broken extrapolation (v2 fails it at d5 already).
- Report v1 with 3-seed bands from now on; the single-seed d14 numbers are
  the upper edge of the band, not the estimate.
- Next: operator diversity (25 → 50+ ops; more distinct ops per held-out
  episode context) on the v1 format, 3 seeds, both test sets @3072; optional
  cheap follow-ups on the v1 base: `--self-check` alone, funcless rows alone.

## Full CI tables (all seeds)

### HELD-OUT test set — CI (= accuracy; per-op x_i = 1.0), greedy @3072 tokens; exec_ok in parentheses

| variant | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 |
|---|---|---|---|---|---|---|---|---|
| v1_s1 | 1.000 (1.00) | 0.984 (1.00) | 0.910 (0.96) | 0.746 (0.91) | 0.586 (0.82) | 0.395 (0.68) | 0.219 (0.47) | 0.160 (0.37) |
| v1_s7 | 0.969 (0.97) | 0.910 (0.94) | 0.637 (0.73) | 0.434 (0.59) | 0.273 (0.43) | 0.180 (0.37) | 0.105 (0.23) | 0.039 (0.19) |
| v1_s123 | 0.977 (1.00) | 0.875 (0.90) | 0.699 (0.74) | 0.410 (0.50) | 0.281 (0.37) | 0.156 (0.26) | 0.082 (0.13) | 0.059 (0.11) |
| v2_s1 | 1.000 (1.00) | 0.930 (0.94) | 0.777 (0.87) | 0.496 (0.68) | 0.273 (0.51) | 0.090 (0.32) | 0.023 (0.15) | 0.004 (0.07) |
| v2_s7 | 1.000 (1.00) | 0.961 (0.96) | 0.914 (0.93) | 0.691 (0.75) | 0.363 (0.50) | 0.125 (0.28) | 0.035 (0.11) | 0.004 (0.06) |
| v2_s123 | 1.000 (1.00) | 0.648 (0.86) | 0.477 (0.77) | 0.281 (0.57) | 0.145 (0.38) | 0.047 (0.18) | 0.020 (0.09) | 0.004 (0.07) |
| v2_sc_s1 | 1.000 (1.00) | 0.980 (1.00) | 0.836 (0.98) | 0.547 (0.90) | 0.320 (0.67) | 0.121 (0.41) | 0.039 (0.23) | 0.008 (0.13) |
| v2_sc_s7 | 1.000 (1.00) | 0.957 (0.96) | 0.688 (0.81) | 0.406 (0.62) | 0.145 (0.29) | 0.059 (0.14) | 0.004 (0.04) | 0.008 (0.02) |
| v2_sc_s123 | 1.000 (1.00) | 0.867 (0.87) | 0.816 (0.84) | 0.590 (0.66) | 0.410 (0.51) | 0.184 (0.31) | 0.031 (0.14) | 0.012 (0.09) |

| variant (n=3 seeds) | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 |
|---|---|---|---|---|---|---|---|---|
| **v1** mean ± sd | 0.982 ± 0.013 | 0.923 ± 0.045 | 0.749 ± 0.117 | 0.530 ± 0.153 | 0.380 ± 0.146 | 0.244 ± 0.107 | 0.135 ± 0.060 | 0.086 ± 0.053 |
| **v2** mean ± sd | 1.000 ± 0.000 | 0.846 ± 0.141 | 0.723 ± 0.182 | 0.489 ± 0.167 | 0.260 ± 0.089 | 0.087 ± 0.032 | 0.026 ± 0.006 | 0.004 ± 0.000 |
| **v2_sc** mean ± sd | 1.000 ± 0.000 | 0.935 ± 0.049 | 0.780 ± 0.066 | 0.514 ± 0.079 | 0.292 ± 0.110 | 0.121 ± 0.051 | 0.025 ± 0.015 | 0.009 ± 0.002 |

### TRAIN-OP test set — CI (= accuracy; per-op x_i = 1.0), greedy @3072 tokens; exec_ok in parentheses

| variant | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 |
|---|---|---|---|---|---|---|---|---|
| v1_s1 | 1.000 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 0.996 (1.00) | 0.996 (1.00) | 0.930 (0.93) | 0.852 (0.85) |
| v1_s7 | 0.977 (0.98) | 0.996 (1.00) | 1.000 (1.00) | 0.996 (1.00) | 0.977 (0.98) | 0.973 (0.97) | 0.930 (0.93) | 0.867 (0.87) |
| v1_s123 | 0.977 (1.00) | 0.996 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 0.965 (0.96) | 0.957 (0.96) | 0.949 (0.95) | 0.906 (0.91) |
| v2_s1 | 1.000 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 0.914 (0.91) | 0.727 (0.73) | 0.430 (0.48) | 0.129 (0.23) | 0.020 (0.15) |
| v2_s7 | 1.000 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 0.980 (0.98) | 0.922 (0.96) | 0.660 (0.79) | 0.289 (0.47) | 0.078 (0.27) |
| v2_s123 | 1.000 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 0.906 (0.93) | 0.699 (0.76) | 0.312 (0.47) | 0.113 (0.28) |
| v2_sc_s1 | 1.000 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 0.934 (0.93) | 0.746 (0.78) | 0.395 (0.50) | 0.117 (0.24) | 0.051 (0.20) |
| v2_sc_s7 | 1.000 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 0.969 (0.97) | 0.762 (0.78) | 0.422 (0.48) | 0.156 (0.27) | 0.059 (0.15) |
| v2_sc_s123 | 1.000 (1.00) | 1.000 (1.00) | 1.000 (1.00) | 0.980 (0.98) | 0.926 (0.96) | 0.672 (0.85) | 0.309 (0.58) | 0.070 (0.33) |

| variant (n=3 seeds) | d1 | d2 | d3 | d4 | d5 | d6 | d7 | d8 |
|---|---|---|---|---|---|---|---|---|
| **v1** mean ± sd | 0.985 ± 0.011 | 0.997 ± 0.002 | 1.000 ± 0.000 | 0.999 ± 0.002 | 0.979 ± 0.013 | 0.975 ± 0.016 | 0.936 ± 0.009 | 0.875 ± 0.023 |
| **v2** mean ± sd | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.965 ± 0.037 | 0.852 ± 0.088 | 0.596 ± 0.119 | 0.243 ± 0.081 | 0.070 ± 0.038 |
| **v2_sc** mean ± sd | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.961 ± 0.020 | 0.811 ± 0.081 | 0.496 ± 0.125 | 0.194 ± 0.083 | 0.060 ± 0.008 |
