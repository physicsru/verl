# Stage-2 Code-Exec RL (comp-s2-cx) — Experiment Summary & Conclusions

**Job**: 2372789.opbs, 8×GB200 nodes, 500 GRPO steps, finished 2026-07-14.
**Full trajectories**: `analysis/s2cx_val_trajectories/depth{1..8}.md` (412 captured).

## Setup

- **Question**: does RL on *train-op* compositions improve *held-out-op*
  accuracy under the one-shot code-exec condition (operator bodies hidden,
  model re-implements every `func_N` from memory, program executed exactly
  once at reward time, output never shown)?
- **Init**: Stage-1 RFT-codeexec checkpoint
  `stage1_paper_rftcx_iter1_qwen3_4b/global_step_1984` (bodies-SHOWN atomic
  training over all 25 ops; per-sample accuracy 3.59/8 = 0.449, pass@8 = 0.991).
- **Train data**: `stage2_level1to2_codeexec` — 50k hidden-body problems,
  depths 1–2, over the **13 train ops only**.
- **Val**: `stage2_level1to8_codeexec` — 256 problems per depth 1–8 over the
  **12 held-out ops** (`func_0,2,6,7,8,10,12,14,16,18,21,24`), greedy mean@1,
  no format bonus.
- GRPO, n=8, 64 prompts/step, lr 1e-6, max response 4096 tok, KL coef 1e-3.

## Results

| val depth | step 0 | peak (step) | step 500 |
|---|---|---|---|
| 1 | 0.344 | **0.457** (170–340) | 0.359 |
| 2 | 0.098 | 0.137 (300) | 0.121 |
| 3 | 0.016 | 0.051 (250) | 0.027 |
| 4 | 0.004 | 0.008 | 0.008 |
| 5–8 | 0.000 | 0.000 | 0.000 |

Train-side reward: 0.11 → ~0.19. Entropy: 1.5 → 1.99 (step 60) → 0.59
(step 159) → continued collapsing. Response-length clip ratio at the 4096
cap: 87% early, still >80% at mid-training.

Scores factorize multiplicatively: P(depth d) ≈ p^(#distinct ops) with
p ≈ 0.34–0.46. Depth ≥ 4 is numerically doomed at this p.

## Why it fails — trajectory autopsy

Late-run failures are clean single-block programs that **run fine and return
the wrong string**: the model mis-remembers the hidden op's semantics.
Failure-mode mix shifted from format problems (early: 43% wrong return type,
29% truncated code, arity crashes) to pure semantic errors (late: 50–100%
"ran fine, wrong answer"). Named examples (ground truth from `operators.py`):

| held-out op | true semantics | model wrote |
|---|---|---|
| `func_6` add_suffix | `x + lit` | `lit + x` — i.e. add_prefix = `func_5`, a **train op** (5/13 correct) |
| `func_8` rotate_str(s,n) | rotate by n | `s * n` — i.e. repeat_str = `func_1`, a **train op**, same signature |
| `func_14` duplicate_every_char | `'ab'→'aabb'` | literally `return x` (no memory, guessed identity) |
| `func_2` remove_vowels | drop vowels | identity / reverse |
| `func_16` compress_repeats | collapse runs | returned an **int** (recalled as counting) |
| `func_24` backchain_palindrome | `s + s[::-1]` | `s * n` |

Reliably recalled: `func_12` vowel_to_number, `func_21` loop_filter_nonalpha,
`func_7` interlace_str. So ~0.4 depth-1 is a bimodal mix of known ops and
sibling-confused / forgotten ops, not uniform mediocrity.

A second failure mode exists at step 0 and disappears with RL: **placeholder
refusal** — "func_16 is not defined … we will assume it is a placeholder
function; `return 16`". The model didn't treat "you know all of them from
prior training" as actionable. Late failures are all confident-wrong-variant.

### Why depth-1 *decays* after step ~340

The sibling pairs above (suffix↔prefix, rotate↔repeat) have the train-op
member rewarded thousands of times while entropy collapses; `func_N` names
carry zero semantic signal, so held-out recall is pure paired-associate
memory and gets pulled toward the reinforced sibling. Classic interference.
Of the saved checkpoints, **step 200 is the best for held-out performance**
(depth-1 = 0.449); step 500 is the worst since step 20.

## Conclusions

1. **RL transfers *behaviors*, not *memories*.** Format discipline,
   self-containment, one-clean-block, no rambling, attempt-recall-instead-of-
   placeholder all transferred to held-out ops (+30% relative depth-1 at
   peak). Semantics of ops absent from training did not — and were eventually
   eroded by interference from trained siblings.
2. **The recall ceiling is the binding constraint.** With per-op recall
   p ≈ 0.45, composition depth d succeeds at ~p^d; no amount of composition
   training fixes depth ≥ 3 without raising p.
3. **Stage 1 (bodies shown) never forced memorization.** Reading code and
   applying it does not create reliable label→body memory; incidental recall
   ≈ 0.34 (with sibling confusion at ~chance).
4. Pipeline plumbing (prompting, extraction, sandbox exec, grading) is
   validated end-to-end — failures are model-knowledge failures.

## Addendum: why RL replay was rejected as the fix

Decomposing the late-run train score (steps 440–499 mean 0.399, minus the
0.05 format bonus, split 50/50 depth-1/depth-2 with s2 ≈ s1²) gives
**train-op depth-1 ≈ 0.47–0.48 after 500 steps of direct hidden-body RL on
those exact ops**. RL raised trained ops from ~0.15 to ~0.5 and saturated —
because GRPO advantage is group-relative: an op the model never recalls
correctly produces all-wrong groups → advantage 0 → zero gradient forever.
RL sharpens memories that sampling occasionally hits; it cannot install
absent ones. Adding eval-op replay data (option A) would repeat the same
~0.5 ceiling.

## Next step (stage 1.5, launched 2026-07-15): closed-book code-exec SFT

Design decision: **atomic skill is stage-1's job; stage-2 measures
compositional skill.** All 25 ops get supervised recall training; only
*compositions* of eval ops stay held out.

`build_closedbook_codeexec.py` synthesizes SFT data: prompt = exact stage-2
hidden-body code-exec prompt (depth-1, one op); target = short recall plan +
one ```python block with the verbatim reference body (renamed to func_N,
docstring kept) + unchanged `main_solution`. Targets never state the output
string (the grader executes), so they are correct by construction; all rows
exec-validated + spot-checked end-to-end through reward_fn_codeexec.
Data: `stage15_closedbook_codeexec` — 20,000 train + 400 val rows, exactly
800/16 per op (deliberately flat vs stage-1 RFT's 22× exposure spread and
func_20's zero traces), 11,280 unique programs, zero real-name leaks.

Job 2387365 (`train_stage15_closedbook_codeexec.sh`, comp-s15-cbcx): SFT
from the stage-1 RFT-codeexec ckpt (keeps one-shot codeexec behaviors),
2 epochs, lr 2e-5. Then: recall-probe the ckpt (per-op depth-1, expect
≥0.9/op before spending stage-2 GPU time) → relaunch stage-2 unchanged
(train-op compositions only). With atoms at p, held-out composition accuracy
vs p^d becomes the real compositional-generalization measurement
(p ≈ 0.9 → depth-4 ≈ 0.66 predicted, vs 0.008 in this run).

Left open (documented, not yet done): `build_rft_data.py` fence-truncation
fix for the Stage-1 ramble poisoning; recall-probe eval set (depth-1 per-op)
for cheap per-op recall tracking during RL.

## Results: stage 1.5 + stage-2 v2 (jobs 2387385, 2387747, 2387955)

**Probe** (25 ops × 64 unseen depth-1, greedy@1): stage-1.5 ckpt = **1.000 on
all 25 ops**; its stage-1 RFT init = 0.181 mean (11 ops at exactly 0.000,
incl. train ops). Table: `analysis/probe_recall_stage15.md`. One 14-minute
SFT installed what 500 RL steps could not.

**Stage-2 v2** (identical to v1 except init = stage-1.5 ckpt), val by step
[s0 / s200 / s500 | peak] vs v1 peak:

| depth | s0 | s200 | s500 | peak | v1 peak |
|---|---|---|---|---|---|
| 1 | 0.977 | 1.000 | **1.000** | 1.000 | 0.457 |
| 2 | 0.324 | 0.887 | 0.820 | 0.910@20 | 0.137 |
| 3 | 0.137 | 0.664 | 0.574 | 0.668@180 | 0.051 |
| 4 | 0.105 | 0.324 | 0.270 | 0.328 | 0.008 |
| 5 | 0.031 | 0.156 | 0.125 | 0.188 | 0.000 |
| 6 | 0.023 | 0.066 | 0.074 | 0.074 | 0.000 |

Findings: (1) held-out depth-1 stayed 1.0 for all 500 steps — SFT-installed
memories resist the RL interference that eroded v1; (2) most composition gain
lands by step 10–50 (format fix: the SFT model emitted ~34 blocks/response at
step 0; RL took one_block 0→1.0 over steps 20–50), then mild decay at d3+
after ~step 200; (3) with atoms at p=1.0, remaining failure is *composition
itself*: per-extra-op success ≈ 0.5–0.75, dominated at depth ≥ 4 by exec
crashes (step-500 exec_ok: d2 0.98, d3 0.79, d4 0.43, d5 0.24, d6 0.12).
Best saved checkpoint: **step 200**.

## v2 failure-mode autopsy (from 1,733 captured val trajectories)

Classified every printed val sample by header (score / exec_ok / exec_error),
attributed to its val step via log position. Late run = steps 210–500,
depths 3–8: **817 failures**:

| class | share | what it actually is |
|---|---|---|
| TypeError | 23.9% | helper defined with the WRONG SIGNATURE, called correctly by the given `main_solution` (e.g. `func_10` = alternate_case(s) defined as `func_10(s, sep)`) |
| NameError | 20.2% | a `func_N` used by `main_solution` never got defined — model loses track of the helper list |
| unbalanced parens (SyntaxError) | 18.0% | stereotyped one-liner corruption: `return ''.join(ch1 + ch2 for ch1, ch2 in zip(s1, s2)` (missing final paren; 209 late occurrences of this exact interlace line) + paren-drops copying the giant nested `main_solution` |
| AttributeError | 11.5% | hallucinated methods in helper bodies, e.g. `''.chase(s, ...)` for loop_filter_nonalpha |
| genexp SyntaxError | 10.4% | corrupted shuffle/interleave one-liners: `reversed(s[i] for i in range(...), ...)` — "Generator expression must be parenthesized" |
| no_code_block / no_entry | 9.2% | response truncated at the 4096 cap before the fence closed |
| ran fine, wrong output | 5.5% | chimera bodies ("remove vowels AND non-alphabetic" = func_2⊕func_21 merged; "count occurrences" = no such op) or cross-op body swaps (func_18 loop_concat written with recursive_reverse's body) |

**Root cause 1 — recall corrupts under multi-helper load.** Atoms probe
1.000 in isolation, but per-MENTION recall in composite programs is only
~85–90%: of late-run plan lines for `func_10`, 87% are correct, 11% recall it
as insert_separator(s, sep) — a *train op's* semantics AND signature; `func_8`
~80% correct (1-arg variants, even "reverse the order of words" = func_4).
"Depth" understates load: binary branching means a depth-4 program can need
8–10 distinct helper implementations, so P(all intact) ≈ 0.85–0.9^k.
TypeError+NameError+AttributeError+wrong-output ≈ **61%** of failures are
this one mechanism in four disguises.

**Root cause 2 — degenerate generative state (SFT-inherited, RL-unfixable
here).** actor/entropy was **0.013 at step 10** — the closedbook SFT init is
near-deterministic from the start (it never "collapsed during RL"). Every
late response fills the whole 4096 budget: after the (closed) code block the
model repeats one sentence — "I will re-implement `func_N` exactly as
recalled and keep `main_solution` unchanged." — hundreds of times. Train
response clip_ratio ≥ 0.97 for the entire run ⇒ EOS is essentially never
sampled ⇒ stopping can never be reinforced ⇒ the mantra is self-perpetuating.
It also degrades code: the paren-dropping/hallucinated-method token noise is
the same degeneracy landing inside helper bodies. pg_loss ≈ 5e-8 by step 10 —
with entropy 0.01, GRPO groups are near-identical and the gradient is ~0,
which is why nearly all learning happened in steps 10–50.

**Levers, reordered by the autopsy** (raise-the-cap demoted — truncation is
only 9%, and a correct response is ~700 tokens):
1. **Stage-1.5b multi-helper closedbook SFT**: synthesize depth-2–4
   *train-op-composition* targets with the same builder (eval-op compositions
   stay held out) and make targets terminate (EOS) right after the block.
   Attacks the 61% recall-corruption class, the mantra, and truncation in one
   supervised pass (~15 min).
2. **RL train data at depths 3–4** so multi-helper contexts are on-policy.
3. **Restore sampling signal**: higher rollout temperature or an entropy
   floor — otherwise GRPO has no gradient to work with.
