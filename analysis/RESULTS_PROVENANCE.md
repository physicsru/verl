# Compositional generalization — results provenance & verification ledger

Written 2026-09-02; **audited the same evening** (issues #5-7 below: every
mean±sd was re-derived from the per-seed CI files by script, every job id
mapped to its log, the co-occurrence data sets measured directly). Purpose:
every claim below is traceable to a job log, data dir, checkpoint, and CI
report so it can be re-verified in a fresh session without trusting summaries.
**Read this before quoting any number.**

Repo root: `/work/go39/b20033/code/generalization/verl` (all paths relative).
Env: `source /work/go39/b20033/code/generalization_venv/bin/activate`.
Job logs land in repo root as `<jobname>.o<jobid>`.
CI numbers are held-out **greedy @3072**, extracted with
`compositionality_index.py --sweep <label>=<rollout_dir> --out <md>`.

## How to re-verify any cell
```
# CI report already on disk:
grep -E '^\| [0-9] \|' analysis/ci_ra_abl_<cell>_b3072.md      # heldout
grep -E '^\| [0-9] \|' analysis/ci_ra_abl_<cell>_b3072_trainops.md
# recompute from the rollout parquet (audit):
python examples/compositional_trainer/compositionality_index.py \
    --sweep <cell>=data/compositional/paper/ra_rft/ablation_sweep_<cell>_b3072 \
    --out /tmp/recheck.md
# mean ± sd over seeds = population sd (ddof=0) of the three CI values, the
# convention of analysis/ra_v2_campaign.md; parse the '| <depth> |' rows.
# measured properties of the co-occurrence data sets quoted in section (3):
python examples/compositional_trainer/audit_multi_atomic_data.py \
    data/compositional/paper/ra_rft/sft_bootstrap_{eco,eptr,epho,pfirst,plast}
```
Seed tags: base run = seed 1 (no tag); `_s7`,`_s123` for the others. Sweep
dirs `ablation_sweep_<cell>[_s<seed>]_b3072`, CI `ci_ra_abl_<cell>[_s<seed>]_b3072.md`.

---

## ⚠️ KNOWN ISSUES / DO-NOT-TRUST FLAGS (read first)

1. **CI-report filename collision (CORRECTED).** Both name-ablation RA jobs ran
   `ABL_VARIANTS=v1`, so both wrote `analysis/ci_ra_abl_v1_b3072.md` — the
   second overwrote the first. The **checkpoints and rollout dirs are distinct**
   (`ra_sft_bootstrap_paper_v1_qwen3_4b` in `paper/…` vs
   `ra_sft_bootstrap_paper_alt_v1_qwen3_4b` in `paper_alt/…`), so only the
   summary md collided. Correct numbers were regenerated into
   `analysis/ci_v1_numfb_b3072.md` and `ci_v1_altfb_b3072.md`. **The generic
   `analysis/ci_ra_abl_v1_b3072.md` is ambiguous — do not cite it for the name
   ablation.** FIX for future: give alt-line jobs a distinct ABL_VARIANTS tag.
2. **RL-E-co (rl-ecorl, job 3279399) COLLAPSED.** held-out rose to E-co level by
   step 20-40 (d4 0.96, d8 0.69) then crashed at step 40-60 (d4 0.14, rlops
   0.88→0.12) while reward saturated at 1.20 = reward-hacking/policy collapse.
   Only steps ≤40 are meaningful; the run's final ckpt is degenerate. Needs the
   step-40 ckpt re-eval + early-stop/stronger-KL rerun before any claim.
3. **Qwen3-8B line INCOMPLETE.** stage15b-8b trained 500 steps but the HF-export
   OOMs (memsw) at aggregation on both 4- and 8-node configs; no usable
   `global_step_500/huggingface/*.safetensors`. External-validity (§⑤) has NO
   result yet. Needs sharded save or offline conversion.
4. **Single-seed cells** are marked (n=1) below — treat as directional only; the
   3-seed replication of C1–C5 (2026-09-01) already flipped one earlier n=1
   claim ("volume hurts", C3>C4), so do not publish n=1 orderings.
5. **(AUDIT 2026-09-02) The first version of this ledger's MAIN-RESULT v1 row
   was itself a victim of issue #1.** Its numbers (0.91±0.03 / 0.52±0.14 /
   0.27±0.14 / 0.12±0.11) reproduce exactly from the overwritten
   `ci_ra_abl_v1_b3072.md` (= the numfb run, job 3279397: a v1 trained from the
   RE-TRAINED stage-1.5 `stage15b_num_frombase`) + s7 + s123 — not from the d14
   ckpt the row cited. Corrected below to d14@3072
   (`ci_trainops_sweep_ho_b3072.md`) + s7 + s123 = 0.92±0.05 / 0.53±0.15 /
   0.24±0.11 / 0.09±0.05, which is what HISTORY §11/§13/§15, `eco_result.md`
   and `ra_v2_campaign.md` already said. `doc/CLAUDE.md` had propagated the
   wrong 0.52±0.14 — fixed the same day. Headline direction unchanged.
6. **(AUDIT) ③ co-occurrence cells eptr / epho are CONFOUNDED and were
   mislabelled.** Measured from the parquets (`audit_multi_atomic_data.py`):
   eptr has held-out defs at the head of 100% of groups (not "mostly") AND only
   54% of held-out atomic defs under load — 2,193/4,753 fell back to
   single-task rows because the train-op partner pool ran out; epho has a
   train op at the head of EVERY group (partners are not "held-out only":
   4,494 train vs 5,488 held-out partner slots) and 100% of held-out defs
   under load. pfirst/plast "forced" position is 61% (a group with several
   held-out tasks cannot put all of them first). The reading "position, not
   partner identity" is RETRACTED — see §③.
7. **(AUDIT) ① name ablation is NOT an identical pipeline.** paper_alt
   stage15b train = 36,000 rows vs paper 32,000: train ops have 1,048–1,412
   depth-1 rows each vs a flat 800 (held-out 800 in both; comps 12,000 both);
   the alt stage-1.5 ran 562 steps vs 500. RA data matched (25,723 rows).
   Root cause (verified): `build_closedbook_codeexec.py` takes every depth
   present in `--comp_src` at `comp_per_depth`=4,000; the alt build's comp
   source contained depth-1 rows, so 4,000 single-op train-op rows were added
   as "comps" (extra_info depth=1, op=single func; the 4,000 extra = exactly
   one comp_per_depth). REBUILT 2026-09-02 (`build_pool_data.sh`, 32,000 rows,
   0 shallow rows); matched results in §①.
8. **(2026-09-03) Checkpoint-name collision → silent resume.** `ra-alt-v1-s1`
   (job 3282001) targeted `ra_sft_bootstrap_paper_alt_v1_qwen3_4b`, which the
   old unmatched job 3279398 had already written; verl `resume_mode=auto`
   loaded its global_step_400 and trained **0 steps** (log: "Found latest
   checkpoint … (step 400)", safetensors dated 09-02 05:05). Its sweep therefore
   reproduces the old 0.977/0.902 exactly and is NOT a matched replicate.
   Rerun as `ABL_TAG=m` (job 3284529). `run_ra_depth_ablation.sh` now aborts
   when SAVE_DIR already holds a checkpoint (ABL_FORCE=1 to override).
9. **(2026-09-03) Two different stage-1.5 inits are in play.** The original
   `stage15b_paper_closedbook_cx_qwen3_4b` (job 2465179, 2026-07-30) was
   initialised from `stage1_paper_rftcx_iter1/global_step_1984` (the RFT-cx
   stage-1 model), whereas every `*_frombase*` stage-1.5 (num 3278516, alt
   3282000, alt2 3282007, the old alt 3279056) starts from Qwen3-4B-Base. Same
   data, 4 nodes, seed 1 in both cases. On the from-base init E-co gives
   held-out d4 **0.77±0.07** (numfb) instead of 0.97±0.02, and v1 varies
   0.18–0.71 across RA seeds. Every 3-seed claim in this ledger shares ONE
   stage-1.5 init (the RFT-cx one for the paper pool); the RA-seed sd
   understates the pipeline's variance. The 27 H0/H1 cell jobs use the RFT-cx
   init (driver default), consistent with E-co / C1–C5.

---

## EXPERIMENT SETTINGS (glossary; every cell below differs from v1 / E-co in ONE thing)

Common to every RA cell unless stated: init = `stage15b_paper_closedbook_cx_qwen3_4b/global_step_500`
(stage-1.5: 20k closed-book depth-1 atomics over all 25 ops + 12k depth-2..4 train-op comps,
itself initialised from the RFT-cx stage-1 model — issue #9); one stitched RA SFT (2 epochs,
batch 128, LR 2e-5 constant, `trainer.seed` 1/7/123); eval = greedy @3072 on the held-out test
(12 held-out ops, depths 1-8, 256/depth) and the train-op test (13 train ops). "Comps" = train-op
compositions in RA format (one `Recall func_N:` episode per distinct op + `Assemble:` block);
"atomics" = depth-1 single-op tasks in the same format. Held-out ops never appear in any comp.

| cell | atomic side (10k tasks, all 25 ops) | composition side | the one variable | held-out d4 / d8 |
|---|---|---|---|---|
| baseline (stage15b) | — (no RA SFT; prose + one code block) | — | no RA format | 0.03 / 0.00 |
| d1 | single-task | none | RA format seen at k=1 only | 0.00 / 0.00 |
| d12 | single-task | 16k, depth 2 only | comp depth range | 0.73 / 0.12 |
| d13 / d13b | single-task | 16k, depth 2-3 (seed 42 / 123) | comp depth range | 0.46 / 0.04 ; 0.67 / 0.09 |
| **v1** (= d14) | single-task, 10,000 rows | 15,979 mixed-structure comps d2-4 | reference recipe | 0.53±0.15 / 0.09±0.05 |
| **E-co** | 1-4 independent tasks per answer (base + U{0..3} partners), all ops, ~3.7k rows; 90% of held-out defs under load | same 15,979 comps | atomic context shape | 0.97±0.02 / 0.73±0.15 |
| C1 | E-co grouping | none | comps removed | 0.66±0.14 / 0.08±0.04 |
| C2 | E-co grouping | 2,068 pure chains f(g(x)), depth 2 | structure: chains only | 0.60±0.04 / 0.08±0.01 |
| C3 | E-co grouping | 2,059 mixed-structure comps, depth 2 | structure: mixed (vs C2) | 0.77±0.11 / 0.17±0.05 |
| C4 | E-co grouping | 12,452 mixed comps, depth 2 | volume ×6 (vs C3) | 0.70±0.03 / 0.12±0.05 |
| C4b | E-co grouping | 12,436 mixed comps, depth 2-4 | depth range (vs C4, matched count) | 0.90±0.04 / 0.62±0.13 |
| C5 | single-task; held-out ops' atomic rows duplicated to ~3,760/op (v1: 397) | same 15,979 comps | frequency ×9.5, no co-occurrence | 0.63±0.12 / 0.14±0.11 |
| eptr | held-out tasks as group bases, partners = train ops only → measured: held-out always first, 54% under load | same comps | partner identity (confounded, §③) | 0.53±0.07 / 0.11±0.02 |
| epho | bases = train tasks, partners = held-out only → a train op heads every group, held-out never first, 100% under load | same comps | partner identity (confounded) | 0.83±0.03 / 0.46±0.17 |
| pfirst / plast | E-co groups reordered: held-out at head (61%) / tail (61%) | same comps | position, clean pair (n=2) | 0.88±0.11 / 0.59 ; 0.98±0.01 / 0.73 |
| sub0 / sub3 / sub6 / sub9 | E-co grouping for train ops + K held-out ops (nested: K=3 func_2/6/18; +func_7/8/21; +func_10/12/16); other held-out ops single-task | same comps | how many held-out ops get load practice | 0.50 / 0.51 / 0.75 / 0.82 (d4) |
| dose25 / 50 / 75 | E-co grouping for a random 25/50/75% of atomic tasks → 21/45/66% of held-out defs under load | same comps | fraction of practice under load | 0.75 / 0.83 / 0.91 (d4) |
| nops4 / nops8 | E-co grouping | 16k mixed d2-4 comps regenerated from only 4 / 8 train ops (nested: reverse_words, while_rotate, sort_chars, mirror_str; + recursive_interlace, fancy_brackets, insert_separator, add_prefix) | diversity of composed ops | 0.55±0.03 / 0.79±0.09 (d4) |
| num / alt / alt2 (§①) | v1 or E-co atomics | same comps | op-name scheme; stage-1.5 from base (not RFT-cx) | v1 0.52 / 0.46 / 0.37; eco 0.77 / 0.71 / 0.76 (d4) |
| P0b / P1b (§14 HISTORY) | width-2 pairs only / pairs + depth-2 chains | — | minimal primitives | see `structured_map_round*.md` |
| decomposed inference | v1 model; each helper recalled in its own forward pass, assembled mechanically | — | system-level isolation | 1.00 / 1.00 |
| RL (A) / (B) | GRPO from v1 on train-op comps d7-10 with 3 probe ops held out of RL / from d12 on d1-4 | — | RL on compositions | held-out flat→declines; rlops+probe rise |
| RL-E-co | GRPO from v1 on width-1..4 multi-task pool, all 25 ops | — | RL as the co-occurrence teacher | d4 0.96 at step 20-40, collapsed at 45 |

---

## MAIN RESULT — E-co vs v1 (the headline, 3 seeds each)

| cell | held-out d2 / d4 / d6 / d8 (mean±sd) | seeds | jobs | ckpts | CI reports |
|---|---|---|---|---|---|
| **v1** (single-task atomics + 16k mixed d2-4 comps) | 0.92±0.05 / 0.53±0.15 / 0.24±0.11 / 0.09±0.05 | 1,7,123 | seed1 = d14 bootstrap (job 2490799, swept @3072 in 2553298); s7 = 2847939; s123 = 2847940 | `ra_sft_bootstrap_paper_qwen3_4b/global_step_400` (seed1=d14); `…_v1_s{7,123}_qwen3_4b/global_step_400` | seed1: `ci_trainops_sweep_ho_b3072.md` (d14 section, sweep `trainops_sweep_d14_ho_b3072`); `ci_ra_abl_v1_s{7,123}_b3072.md`. **Not** `ci_ra_abl_v1_b3072.md` (issue #1/#5) |
| **E-co** (co-occurrence atomics + same 16k comps) | 1.00±0.00 / 0.97±0.02 / 0.89±0.09 / 0.73±0.15 | 1,7,123 | 3267112, 3267226, 3267227 | `ra_sft_bootstrap_paper_eco{,_s7,_s123}_qwen3_4b/global_step_308` | `ci_ra_abl_eco{,_s7,_s123}_b3072.md` |

Per-seed d2/d4/d6/d8 — v1: d14 0.984/0.746/0.395/0.160, s7 0.910/0.434/0.180/0.039,
s123 0.875/0.410/0.156/0.059; E-co: s1 1.000/0.980/0.934/0.832, s7
1.000/1.000/0.969/0.844, s123 1.000/0.945/0.762/0.520. Both cells share the init
`stage15b_paper_closedbook_cx_qwen3_4b/global_step_500`, 2 epochs, batch 128,
constant LR 2e-5 (v1 400 steps over 25,723 rows; E-co 308 over 19,719 — fewer
rows because 1–4 atomic tasks share one row). A 4th v1-recipe sample exists
(numfb, job 3279397, seed 1 from a RE-TRAINED stage-1.5): 0.953/0.711/0.473/0.277,
the best v1 d8 ever — excluded from the mean because its init differs; it shows
the stage-1.5 seed is a variance source of its own. **Init caveat (issue #9):**
both rows sit on the RFT-cx-initialised stage-1.5; on a from-base stage-1.5
(numfb line, §①) the same recipes give v1 0.52±0.24 / eco 0.77±0.07 at d4.

Data: E-co train parquet `data/compositional/paper/ra_rft/sft_bootstrap_eco/`,
built by `build_ra_sft_data.py --multi_atomic` (each atomic answer holds U{0..3}
extra independent atomic tasks; per-op def counts unchanged). Report:
`analysis/eco_result.md`.

**Decomposed-inference ceiling** (mechanism, job 3267111,
`rollout_decomposed.py`): held-out & train-op = **1.000 at every depth 1-8**
(9,113/9,113 held-out helper recalls unit-test-pass). Report
`analysis/ci_decomposed_v1.md`; sweep dirs
`data/compositional/paper/ra_rft/decomposed_v1_{heldout,trainops}`.

**Failure mechanism** (3-seed v1 sweeps): `analysis/heldout_failure_mechanism.md`
— name→def collapse onto composed train-op neighbours (1,102/1,175 chimera
bodies from train ops).

---

## C1–C5 CAUSAL TABLE (single-variable around E-co; 3 seeds each)

All share E-co's co-occurrence atomics; only the composition set varies.
Jobs: base seed = C2 3274459, C4 3274461, C1/C3/C5 3275134/3275135/3275136
(3274458/60/62 left no log — resubmitted); s7 = 3275724/26/28/30/32; s123 =
3275739-43. Training length (2 epochs, batch 128, constant LR): C1 58 steps,
C2/C3 90, C4/C4b 252, C5 1,034, E-co 308, v1 400.
Data dirs `data/compositional/paper/ra_rft/sft_bootstrap_c{1..5}/`. Report
`analysis/ablation_c1c5.md` (has the 3-seed section).

| cell | comps | d4 (mean±sd) | d8 | reading |
|---|---|---|---|---|
| C1 | none | 0.66±0.14 | 0.08±0.04 | composition demos NOT necessary for mid-depth |
| C2 | 2,068 pure chains d2 | 0.60±0.04 | 0.08±0.01 | pure chains ≤ no-comps |
| C3 | 2,059 mixed d2 | 0.77±0.11 | 0.17±0.05 | **structure diversity** (C3−C2 +ve all 3 seeds) |
| C4 | 12,452 mixed d2 | 0.70±0.03 | 0.12±0.05 | volume ≈ neutral (C3≈C4, "volume hurts" RETRACTED) |
| C4b | 12,436 mixed **d2-4** | 0.90±0.04 | 0.62±0.13 | **depth diversity** (C4b−C4 at matched count) |
| C5 | 16k mixed d2-4, held-out atomic freq ×10 (single-task) | 0.63±0.12 | 0.14±0.11 | **frequency is NOT the mechanism** (≈ v1) |
| E-co | 16k mixed d2-4 | 0.97±0.02 | 0.73±0.15 | best + lowest variance |

C4b jobs: base 3278552, s7 3279487, s123 3279488. C4 failure classification
`analysis/c4_failures.md`: at d8, 159/256 problems (62% of all, 70% of the 227
failures) have incomplete recall (episode omission), so d3-4 data mostly fixes
episode-count extrapolation — but C4's per-episode TypeError rate is still
13.8% at d8 (E-co 0.6%), i.e. the name→def collapse is only partly gone in C4.

**Established, publishable (3-seed):** (i) co-occurrence ≫ frequency (E-co vs
v1, C5 vs v1); (ii) composition without composition data is real (C1);
(iii) structure diversity matters (C3 vs C2, positive in all 3 seed pairs)
while volume at fixed diversity is ~neutral (C4 vs C3, 0.70±0.03 vs
0.77±0.11); (iv) depth diversity is the dominant comp-side factor (C4b vs C4,
non-overlapping bands; E-co vs C4).

---

## ③ CO-OCCURRENCE STRUCTURE: partner identity vs position — INCONCLUSIVE (audited)

`--partner_split` restricts held-out ops' partners; `--heldout_position` pins
held-out tasks to group head/tail (both in `build_ra_sft_data.py`). Comps fixed
at 16k d2-4. The table carries the **measured** properties of each data set
(`python examples/compositional_trainer/audit_multi_atomic_data.py …`), not
the intended ones — they differ (issue #6).

| cell | held-out defs under load | held-out at head / mid / tail | partner slots train : held-out | d4 / d8 | seeds | jobs |
|---|---|---|---|---|---|---|
| eptr | **54%** (2,193/4,753 single-task) | **100%** / 0 / 0 | 4,814 : 0 | 0.53±0.07 / 0.11±0.02 | 1,7,123 | 3278550,3279489,3279490 |
| epho | 100% | 0 / 47% / 53% | 4,494 : 5,488 (a train op heads every group) | 0.83±0.03 / 0.46±0.17 | 1,7,123 | 3278551,3279491,3279492 |
| pfirst | 90% | 61% / 30% / 9% | 4,668 : 3,968 | 0.88±0.11 (0.762, 0.992) / 0.59±0.20 | 1,7 | 3279504,3279505 |
| plast | 90% | 9% / 30% / 61% | same groups as pfirst, reordered | 0.98±0.01 (0.965, 0.988) / 0.73±0.08 | 1,7 | 3279506,3279507 |
| E-co | 90% | 36% / 31% / 33% | 4,668 : 3,968 | 0.97±0.02 / 0.73±0.15 | 1,7,123 | (above) |

Why the labels were wrong: with `--partner_split train` every held-out task is
a group *base* (always first) and draws U{0..3} train partners; the ~5k train
atomic tasks are exhausted before the ~4.8k held-out bases, so late bases get
k=0 → 46% of held-out practice is single-task (the v1 regime). With
`--partner_split test` the bases are train tasks, so a train op heads every
group and held-out tasks fill positions 1-3. `--heldout_position first|last`
only reorders within a group, so with several held-out tasks per group only
61% can be at the pinned end.

Reading (audit 2026-09-02): only pfirst/plast is a clean pair (identical
groups, reordered); it *suggests* late position helps (d4 0.98 vs 0.88, d8
0.73 vs 0.59) but one pfirst seed (0.992) equals plast, so n=2 does not
establish it. eptr changes three things at once (always-head, train-only
partners, half the under-load practice) — its 0.53 cannot be attributed to
position. epho (0% head) at 0.83 sits well below plast (9% head) at 0.98, so
partner composition and/or group structure matters too. The earlier reading
"position, not partner identity" is **retracted**. NEEDS: pfirst/plast seed
123; eptr rebuilt with a large enough train partner pool (≥90% under load,
matched to E-co); an epho variant without the train-op head (held-out-only
groups); ideally the 2×2 partner × position at matched load. Data dirs
`sft_bootstrap_{eptr,epho,pfirst,plast}`.

---

## ① NAME ABLATION — MATCHED REPLICATION (2026-09-03): letter names do NOT lift v1; H1-names branch refuted

Design: three op-name schemes (`COMPOSITIONAL_NAME_SCHEME` in `operators.py`:
num=`func_10`, alt=`func_qzk`, alt2=`func_ubiz`, tokenisation identical: 3–4
tokens per name in every scheme), each with its own pool regenerated row-for-row
from the paper recipe (`build_pool_data.sh`: stage15 20,000, stage15b 32,000 with
`--comp_min_depth 2`, tests 2,048, RA v1 25,723 / eco 19,719), stage-1.5 trained
**from Qwen3-4B-Base** (4 nodes, 2 epochs, 500 steps), then RA v1 and RA E-co ×
seeds 1/7/123, greedy @3072. The num side uses the same from-base recipe
(`stage15b_num_frombase`, job 3278516; RA runs tagged `numfb`), so the three
schemes share the init procedure (see issue #9 for why this differs from the
main table).

| scheme | stage-1.5 (from base) | RA v1 held-out d4 / d8, mean±sd (seeds 1/7/123) | RA E-co d4 / d8 | jobs |
|---|---|---|---|---|
| num | `stage15b_num_frombase_qwen3_4b` (3278516) | 0.52±0.24 (0.71/0.18/0.66) / 0.21±0.14 (0.28/0.01/0.33) | 0.77±0.07 (0.88/0.71/0.73) / 0.52±0.26 (0.87/0.46/0.25) | v1: 3279397, 3282014, 3282015; eco: 3282016-18 |
| alt | `stage15b_paper_alt_frombase_matched_qwen3_4b` (3282000) | 0.46±0.06 (0.54/0.43/0.40) / 0.11±0.04 (0.16/0.09/0.07) — seed 1 = rerun 3284529 (`ABL_TAG=m`, issue #8) | 0.71±0.07 (0.61/0.79/0.72) / 0.32±0.11 (0.18/0.45/0.35) | v1: 3284529, 3282002, 3282003; eco: 3282004-06 |
| alt2 | `stage15b_paper_alt2_frombase_matched_qwen3_4b` (3282007) | 0.37±0.11 (0.51/0.35/0.24) / 0.05±0.04 (0.11/0.03/0.01) | 0.76±0.17 (0.62/0.99/0.67) / 0.42±0.33 (0.16/0.88/0.23) | v1: 3282008-10; eco: 3282011-13 |

CI reports: `ci_ra_abl_paper_alt{,2}_{v1,eco}[_s{7,123}]_b3072.md` (alt v1 seed 1 =
`ci_ra_abl_paper_alt_v1_m_b3072.md`; the un-suffixed alt v1 file is the collided
job = old model),
`ci_ra_abl_{v1,eco}_numfb[_s{7,123}]_b3072.md` (+ `_trainops`); ckpts
`ra_sft_bootstrap_paper_alt{,2}_{v1,eco}[_s*]_qwen3_4b`,
`ra_sft_bootstrap_paper_{v1,eco}_numfb[_s*]_qwen3_4b`; sweeps under
`data/compositional/paper_alt{,2}/ra_rft/`. Train-op d8 is 0.70–0.99 in every
cell (models are fine on composed ops; the loss is held-out-specific as before).
Failure classification: `analysis/cls_name_ablation_{alt,alt2,num}.md`.

**Reading.** The 2026-09-02 n=1 claim ("letter names raise held-out d8 0.28 →
0.90") does not replicate: three matched alt seeds give d4 0.54/0.43/0.40 and
three alt2 seeds 0.51/0.35/0.24 — the v1 band. The one 0.98/0.90 model is the
old unmatched-stage-1.5 run (issue #7), re-measured identically by the
collided job (issue #8). Job 3284529 repeats it with the SAME RA seed (1) on the
matched stage-1.5 and gets 0.54/0.16, so the 0.98 came from that particular
stage-1.5 model — its extra 4k train-op rows / 62 steps or plain stage-1.5
run variance, not separable with one run; under issue #9 (per-op bistable
binding, init-dependent) run variance is the parsimonious reading. Meanwhile E-co lifts every scheme by a similar margin from
the same from-base init (num +0.25, alt +0.30, alt2 +0.39 at d4), so the
co-occurrence effect is name-agnostic and the digit-neighbour-confusion
mechanism is **not** the lever. New fact instead: the stage-1.5 init is a
first-order factor (issue #9) — E-co 0.97±0.02 on the RFT-cx-initialised
stage-1.5 vs 0.71–0.77 on from-base stage-1.5, with much larger seed variance
(eco alt2 seeds 0.62/0.99/0.67).

Old unmatched line, kept for the record: num 0.95/0.71/0.47/0.28 (3279397 =
numfb seed 1 above), alt 0.99/0.98/0.93/0.90 (3279398, stage-1.5 3279056 on
36k rows / 562 steps); reports `ci_v1_{numfb,altfb}_b3072.md`.

**Failure classification** (`cls_name_ablation_{alt,alt2,num}.md`, per-op episode
table, depth 2-8): in every weak from-base model the loss sits in ONE or TWO
held-out ops that are almost totally collapsed while the other 10-11 are ≥ 0.9
ok — func_24 backchain_palindrome `(s, depth)`: alt `func_umket` 0.08 ok / 0.92
TypeError (eco s1), 0.28 (eco s7), 0.08 (v1 s7); alt2 `func_uzuw` 0.12 (v1 s1),
0.31 (eco s1); num 0.13 (v1 s7), 0.66 (eco s123); func_8 rotate_str `(s, n)`:
num v1 s7 0.14, alt2 `func_eqah` 0.74; func_6 add_suffix `(s, suf)`: num v1 s7
0.53, eco s1 0.86; func_7 interlace_str: alt `func_kacy` 0.27 (wrong body);
func_10 alternate_case: alt2 `func_hevul` 0.31 (wrong body). The dominant verdict
is TypeError = the op written with one parameter — an arity prior, not a
digit-neighbour chimera — consistent with names not mattering. Per-op binding is
near-bistable (≈ 1.0 or ≈ 0.1) and which ops flip is seed-dependent, so a
model's held-out number is governed by 1-2 ops; that is the seed variance. The
0.99 alt2-eco seed simply has no flipped op. The subset-transfer readout (per-op
table) is therefore the right unit of analysis for the cells.

---

## ② RL-E-co — see KNOWN ISSUE #2 (collapsed; steps ≤40 only)

Job 3279399 `rl-ecorl.o3279399`. Pool
`data/compositional/paper/structured/pool_w14d/train.parquet` (parmt widths 1-4,
all 25 ops, split=train). Prefilter 3278553. Init = v1 d14 ckpt. Trajectory:
step0 d4 0.75 → step20 0.96 → step40 0.96 → **step60 0.14 (collapse)**.
Full val trajectory (greedy, from the log): held-out d4/d8 0.750/0.164 (step
0) → 0.965/0.691 (20) → 0.961/0.660 (40) → 0.145/0.062 (60, 80, 100); rlops
d8 0.883 → 0.867 → 0.859 → 0.117; probe d8 0.844 → 0.824 → 0.812 → 0.080.
Collapse onset: `response_length/mean` 490 tokens at step 43 → 603 (44) →
1,264 (45) → 2,523 (46) → 3,915 (47) → the 4,096 cap by step 58 (clip_ratio
1.0), while `critic/score/mean` rises 0.56 → 1.19 over steps 43-49. Ckpts
`rl_ra_grpo_w14_v1init_ecorl_qwen3_4b/global_step_{50,100}` are both
POST-collapse (step 50 already at reward 1.19 / length 4,083); a usable ckpt
must be ≤ step 43 — rerun with save_freq=10, an early stop on response length
or held-out val, and stronger KL.

---

## EARLIER SETTLED LINES (see COMPOSITIONAL_HISTORY.md for full detail)

| line | verdict | jobs | report |
|---|---|---|---|
| RA-v2 stitcher (arity cue etc.) | NEGATIVE (regression) | 2847832-34, 2847939-40 | `analysis/ra_v2_campaign.md` |
| RL on train-op comps (probe split) | held-out flat/declines | 3208916; 3242468+3255766 | `analysis/rl_ra_grpo_{d7to10,d1to4_d12init}.md` |
| Minimal primitives (SFT vs RL, structure map) | serial extrapolates via RL; width doesn't; skills interfere | exp1 3271797, exp2 3271798, exp3 3273779 | `analysis/structured_map_round{1,2,3}.md` |

Canonical logs: `examples/compositional_trainer/WALKTHROUGH.md` §1-21;
`doc/COMPOSITIONAL_HISTORY.md` §0-16.

---

## H0/H1 PLAN (pre-registered 2026-09-02; code committed, jobs NOT yet run)

The research question behind the project: can LIMITED composition data (few ops, depths 2-4)
yield composition over ARBITRARY atomic ops, or does every op need its own data? The
evidence so far says the composition *procedure* transfers (decomposed inference 1.000, k=2
demos extrapolate to k≈8, RL extends depth) and the bottleneck is load-robust name→def
binding, which E-co installs with per-op atomic data in multi-task form (O(#ops), not
O(#compositions)). Open: is that robustness a per-memory property or a transferable skill?

- **H0**: load-robust binding must be installed per op (untreated ops stay at v1 level).
- **H1**: it transfers across ops, or vanishes when names are non-confusable.

| experiment | cells (× seeds 1,7,123) | readout | H1 predicts | H0 predicts |
|---|---|---|---|---|
| subset transfer | sub0/3/6/9 (+eco = 12): K of 12 held-out ops get co-occurrence practice, nested prefixes of one seeded permutation (`--cooc_heldout_k`) | untreated ops' per-episode ok rate (`cls_*.md` per-op table) and untreated-only program accuracy (`ci_*_groups.md`) | untreated rises with K (≥ +0.15 episode-ok from sub0 to sub9, 3 seeds same sign) | untreated flat in the v1 band (episode ok ≈ 0.77–0.85) while treated → E-co level |
| names, matched | paper_alt + paper_alt2 pools rebuilt at 800/op (`build_pool_data.sh`), stage-1.5 from base, RA v1 and eco × 3; num side redone from `stage15b_num_frombase` (ABL_TAG=numfb) | held-out d4/d8 by scheme; eco−v1 gap under each scheme; chimera classification | letter names alone reach ≥ 0.8 at d8 for v1 (representation-level H1) | v1 stays ≤ 0.3 at d8 under every scheme; eco needed regardless |
| operator diversity | nops4 / nops8 (+eco = 13, c1 = 0): comps from only N train ops, 16k d2-4 fixed (`generate_data.py --ops`) | held-out d4/d8 vs N | monotone rise with N (procedure generality) | flat (binding-only story) |
| dose | dose25/50/75 (+v1 = 0, eco = 100): fraction of atomic tasks that enter grouping (`--multi_frac`) | held-out d4 vs measured under-load fraction (audit script) | — | gives the per-op practice needed; eptr's 54% → 0.53 should land on the curve |

Decision rule (fixed now): a claim goes in the paper only when the 3-seed bands do not
overlap in the predicted direction.

**Status 2026-09-03.** names: DONE — H1-names branch refuted (§①; one seed rerun
3284529 pending). cells: data built 2026-09-02 17:11 (`build_h01_cells.sh`), 27 jobs
submitted 2026-09-03 (seeds 1/7/123 in that order; all `-p 1023`): on go39 (moved
from gj26 while still queued, original ids 3284481-95 deleted) sub0 3284620-22,
sub3 3284623-25, sub6 3284626-28, sub9 3284629-31, dose25 3284632/3284634/3284635;
on gj26 dose50 3284496-98, dose75 3284499-501, nops4 3284502-04, nops8 3284505-07.
RA_INIT = the RFT-cx-initialised stage-1.5 (driver default). nops train-op subsets (seed 1,
nested): nops4 = reverse_words, while_rotate, sort_chars, mirror_str; nops8 = +
recursive_interlace, fancy_brackets, insert_separator, add_prefix.

**First cell in (2026-09-03 15:20) — sub0 = co-occurrence for train ops only, held-out
single-task (3 seeds, `ci_ra_abl_sub0{,_s7,_s123}_b3072.md`, `cls_ra_abl_sub0*.md`):**
held-out d4 0.50±0.06 (0.58/0.43/0.50), d8 0.12±0.04 (0.11/0.07/0.17) — the v1 band
(0.53±0.15 / 0.09±0.05), while train-op d8 stays 0.86–0.93. Per-op episode ok (depth 2-8)
is a graded spread, not a bistable flip: e.g. seed 1 func_0 0.44, func_21 0.68, func_6 0.69,
func_10 0.71, func_14 0.75, func_12 0.77; the weak ops differ by seed. Reading: multi-def
answers on the train ops alone do NOT transfer to held-out ops — the E-co gain is the
held-out ops' own practice under load, not the answer format (the A0 control). This is
the K=0 point of the subset-transfer curve; H1 now needs the untreated ops in sub3/6/9 to
rise above this band. (Groups report missing for sub0-9 jobs submitted before the
`GROUPS`→`OPGROUPS` driver fix — regenerate on the login node from the sweep dirs with
`compositionality_index.py --sweep … --op-groups <data_dir>/treated_ops.json`.) Scripts: `build_h01_cells.sh` (CPU data),
`build_pool_data.sh <pool> <scheme>` (matched name pools), `submit_h01_campaign.sh`
(DRY_RUN=1 prints the 27 + 19 qsub lines); readouts are produced by
`run_ra_depth_ablation.sh` automatically for cells that carry `treated_ops.json`.

---

## H0/H1 RESULTS (2026-09-03, 3 seeds per cell; complete)

All cells: E-co recipe on the RFT-cx-initialised stage-1.5 (issue #9), greedy @3072,
held-out test set. Whole-model numbers from `ci_ra_abl_<cell>[_s*]_b3072.md`; per-op
episode-ok from `cls_ra_abl_<cell>*.md` (`summarize_subset_transfer.py` prints the table);
program-level treated/untreated accuracy in `ci_ra_abl_<cell>*_groups.md`.

**Subset transfer** (K of 12 held-out ops get co-occurrence practice; treated set nested:
K=3 func_2/6/18, K=6 + func_7/8/21, K=9 + func_10/12/16; untreated at K=9 = func_0/14/24):

| K | held-out d4 | d8 | treated ops episode-ok | untreated ops episode-ok | untreated − sub0 (paired by op, seeds 1/7/123) |
|---|---|---|---|---|---|
| 0 (sub0) | 0.50±0.06 | 0.12±0.04 | — | 0.80 | 0 |
| 3 (sub3) | 0.51±0.07 | 0.09±0.05 | 0.96 | 0.74 | **−0.07** (−0.12/−0.08/−0.01) |
| 6 (sub6) | 0.75±0.14 | 0.37±0.17 | 0.98 | 0.84 | +0.05 (0.00/+0.12/+0.03) |
| 9 (sub9) | 0.82±0.07 | 0.39±0.17 | 0.98 | 0.82 | **+0.10** (+0.17/+0.05/+0.09) |
| 12 (eco) | 0.97±0.02 | 0.73±0.15 | 0.99 | — | — |

Program-level (programs whose held-out ops are ALL untreated, pooled d2-8): sub3 0.63 /
0.71 / 0.84, sub6 0.90 / 0.95 / 0.93, sub9 1.00 / 0.94 / 0.96 (n shrinks with K).
Verdict vs the pre-registration: H1 asked for ≥ +0.15 on untreated ops from K=0 to K=9
with 3 seeds in the same sign; observed +0.10, same sign in all 3 seeds. K=3 is
negative in all 3 seeds. Reading: **transfer exists but is weak and late** — untreated ops
gain only once most other ops are treated, and a small treated set makes the rest worse
(strengthened bindings act as attractors, cf. mechanism doc). Practically H0: at K=9 the
untreated ops still sit at 0.82 vs 0.98 treated, i.e. per-op practice remains necessary.

**Names** — refuted (§①): v1 under num/alt/alt2 = 0.52 / 0.46 / 0.37 at d4; E-co lifts all
three alike.

**Operator diversity** (E-co atomics; comps from N train ops, 16k d2-4 fixed):

| N composed train ops | held-out d4 | d8 | jobs |
|---|---|---|---|
| 0 (C1, no comps) | 0.66±0.14 | 0.08±0.04 | (C1) |
| 4 (nops4) | 0.55±0.03 (0.59/0.52/0.53) | 0.14±0.02 | 3284502-04 |
| 8 (nops8) | 0.79±0.09 (0.91/0.71/0.75) | 0.40±0.18 | 3284505-07 |
| 13 (eco) | 0.97±0.02 | 0.73±0.15 | — |

Verdict: held-out rises monotonically with N from 4 to 13 with non-overlapping bands
(4 vs 8 vs 13) — the H1 prediction on this axis (composition data on MORE distinct ops
transfers better to unseen ops). N=4 sits below N=0 but the bands overlap (C1 seed 7 =
0.46), so "a few composed ops hurt" is suggestive only.

**Dose** (fraction of atomic tasks that enter grouping; measured under-load share of
held-out defs from `audit_multi_atomic_data.py`):

| nominal | held-out defs under load | held-out d4 | d8 | jobs |
|---|---|---|---|---|
| 0 (v1) | 0% | 0.53±0.15 | 0.09±0.05 | — |
| 25 (dose25) | 21% | 0.75±0.15 (0.56/0.75/0.93) | 0.46±0.20 (0.25/0.41/0.74) | 3284632/3284634/3284635 |
| 50 (dose50) | 45% | 0.83±0.13 (0.92/0.93/0.66) | 0.41±0.15 | 3284496-98 |
| 75 (dose75) | 66% | 0.91±0.10 (0.78/0.98/0.98) | 0.62±0.18 | 3284499-501 |
| 100 (eco) | 90% | 0.97±0.02 | 0.73±0.15 | — |

Verdict: concave — 21% of the practice already buys half of the E-co gain at d4 (0.53 →
0.75), 45% two thirds (0.83), then 0.91 / 0.97; seed sd shrinks with dose (0.15 → 0.02).
eptr (54% under load, held-out always at head, train-only partners) = 0.53 sits FAR below
this curve (dose25 at 21% is already 0.75), so eptr's deficit is NOT the load fraction:
position and/or partner composition does matter after all (§③ stays open, but its
confound list shrinks).

**Overall.** The composition procedure transfers; the per-op binding must still be
installed under load for (nearly) every op — a general "robust retrieval" skill emerges
only weakly and only after most ops have been practised. What does scale favourably is
the *diversity* of composed ops and the *fraction* of practice under load, not the
naming. Init caveat (#9) applies to every number above.

---

## C — DEPTH EXECUTION RELIABILITY (submitted 2026-09-04; running)

Component C of the conclusion: with E-co the held-out and train-op curves decay together
(d8 0.73 vs 0.86); failures at d8 are 3/4 mechanical (episode omission, paren copy) and
per-step reliability drops 0.995 → 0.977 from d4 to d8; decomposed inference is 1.000, so
the pieces are fine and serial execution is the limit. Two levers, both on the E-co init:

| cell | design | jobs | pre-registered reading |
|---|---|---|---|
| eco_d28 (SFT) | E-co atomics + 16k train-op comps spanning depth **2-8** (fresh generation, seed 20260904, `stage2_level2to8_trainops_src`; 19,728 rows, 4 deep comps failed the gate), SFT_MAX_LENGTH 4096, seeds 1/7/123 | 3291420 / 3291421 / 3291422 (go39) | if held-out d8 rises toward train-op d8 → depth reliability is demonstration-limited and op-agnostic (mechanical errors shrink); if only train-op rises → the deep demos teach the composed ops, not the procedure; if neither → serial-length limit |
| rl-eco-d7to10 (RL) | GRPO from `ra_sft_bootstrap_paper_eco_qwen3_4b/global_step_308` on train-op comps d7-10 (probe split as line A), KL 0.01, 100 steps, SAVE_FREQ 10, TEST_FREQ 10, EARLY_STOP_RESP_LEN 3500 | 3290812 (go39) | line A from v1 lifted rlops/probe and squeezed held-out; from the E-co init H-C predicts held-out d8 rises with rlops (mechanical errors are shared) — if held-out declines again, RL on compositions squeezes even robust bindings |

Fixed budget: no manual stopping; the length early-stop is the only automatic rule.

**Preliminary (2026-09-04 16:20, one seed each):**
- eco_d28, **3 seeds** (3291420-22): held-out d4 **0.63±0.05** (0.57/0.62/0.69), d8
  **0.33±0.02** (0.29/0.34/0.35) vs E-co 0.97±0.02 / 0.73±0.15 — non-overlapping, replicated
  drop; train-op accuracy 1.000/1.000/0.891 at d4 and 1.000/1.000/0.684 at d8 (seed 123
  weaker on train ops too). Deep train-op demonstrations perfect the composed ops and
  squeeze the held-out ones — the RFT / stage15b effect again, amplified (k≈8.6 train-op
  defs per answer). Reading: depth reliability is NOT demonstration-limited in an
  op-agnostic way; deeper demos teach the composed ops and cost the others. Established
  (3-seed): the SFT lever for C is closed.
- rl-eco-d7to10 (3290812, COMPLETE, 100 steps; greedy val every 10 steps; step 0 = E-co
  seed 1; `ci_rl_ra_grpo_d7to10_ecoinit_{heldout,rlops,probe}.md`):

  | step | 0 | 10 | 20 | 30 | 40 | 50 | 60 | 70 | 80 | 90 | 100 |
  |---|---|---|---|---|---|---|---|---|---|---|---|
  | held-out d4 | 0.98 | **0.99** | 0.94 | 0.89 | 0.86 | 0.79 | 0.78 | 0.77 | 0.77 | 0.77 | 0.77 |
  | held-out d8 | 0.84 | **0.94** | 0.79 | 0.60 | 0.54 | 0.45 | 0.43 | 0.42 | 0.43 | 0.43 | 0.43 |
  | rlops d8 / d12 | 0.91 / 0.62 | 1.00 / 0.91 | 1.00 / 0.94 | 1.00 / 0.95 | 0.99 / 0.96 | 1.00 / 0.96 | 1.00 / 0.96 | 1.00 / 0.96 | 1.00 / 0.96 | 1.00 / 0.96 | 1.00 / 0.96 |
  | probe d8 | 0.87 | 0.99 | 0.99 | 0.99 | 0.99 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
  | train reward | — | 1.16 | 1.16 | 1.20 | 1.20 | 1.20 | 1.20 | 1.20 | 1.19 | 1.15 | 1.18 |

  Response length flat 1,220-1,370 (no blow-up; early stop never fired). The 100-step
  budget was honoured, no manual stop.

  **Diagnosis from the in-run val metrics (no reward hacking; over-optimisation that
  rewrites neighbouring held-out signatures):**
  - Failure form: at every step `exec_ok == score` and `ra_recall_complete` = 1.00 with
    `ra_n_episodes` constant — no omission, no wrong answers, no format drift. The whole
    loss is `ra_episode_typeerror_frac` (wrong arity) rising monotonically: d8 0.007 (0) →
    0.006 (10) → 0.027 (20) → 0.051 (30) → 0.073 (50) → 0.075 (100); d4 0.006 → 0.059.
  - It reaches **depth 1**: held-out d1 1.00 → 0.94 from step 50 with episode-TypeError
    0.055 ≈ one of the 12 held-out ops now written with the wrong arity even alone (no
    load). The binding was overwritten in the weights, not merely out-competed in context.
  - Train side: rlops episode-TypeError stays 0.000; reward is genuine (exec-verified,
    1.2 = max), length flat — nothing is being exploited. Policy entropy collapses 0.0022
    (step 10) → 0.0003 (20) → 0.0000 (80); from step 30 most batches have advantages
    max = min = 0 (fully saturated, pg_loss 0, grad_norm ≈ 0), and the remaining updates
    come from rare 7-vs-1 groups whose std-normalised advantages are −2.47 / +0.35 — a
    few deviant samples on the hardest train-op prompts drive large, one-sided updates.
    KL term ≈ 0.001 (coef 0.01): no restoring force.
  - Reading: the decline is NOT reward hacking; it is continued sharpening on train-op
    programs after the task is solved (entropy → 0), whose collateral is the arity of
    signature-neighbour held-out ops (the same attractor mechanism as eco_d28 / RFT /
    stage15b, now via RL). The step-10 lift is the shared-mechanics gain that arrives
    before the sharpening dominates. Onset (step 10→20) precedes reward saturation (step
    30), so "stop at saturation" would already be late; the entropy collapse (10× drop
    by step 20) coincides with the onset — a label-free candidate signal.
  - What this implies for "when to stop" in general: nothing in the training signal
    marks the peak except entropy collapse; the robust answer is to remove the cause —
    keep every skill in the objective (mix multi-task atomic prompts over ALL ops into
    the RL pool, so sharpening train-op comps at the expense of other ops is itself
    penalised by the same reward), and/or a KL strong enough to bind.

  **Per-op diagnosis (2026-09-04 23:30; full greedy held-out sweeps + classifier of the
  E-co init, RL step 20 and RL step 100 — `ci_ckpt_{eco_init,rl_eco_step20,rl_eco_step100}_heldout.md`,
  `cls_ckpt_*_heldout.md`, jobs 3294043-45):** raw held-out acc d1/d4/d8 = 0.996/0.984/0.836
  (init) → 0.996/0.945/0.789 (step 20) → 0.941/0.766/0.422 (step 100). **Exactly one held-out
  op fails**: func_0 (`deterministic_shuffle(s)`) episode-ok 0.998 → 0.774 → 0.029 with
  TypeError 0.002 → 0.221 → 0.964, and its depth-1 recall x_i 1.00 → 1.00 → **0.00**; the
  other 11 held-out ops stay ≥ 0.99 at every checkpoint. Signature written for func_0:
  ```
eco_init         func_0 signature: {'s': 1250, 's, n': 2} | body: {'gcd/multiplier': 1252}
rl_eco_step20    func_0 signature: {'s': 1082, 's, n': 174} | body: {'gcd/multiplier': 1256}
rl_eco_step100   func_0 signature: {'s': 704, 's, n': 548, 's, base': 4} | body: {'gcd/multiplier': 1256}
  ```
  i.e. RL on train-op comps sharpened func_5 `add_prefix(s, pre)` (a train op in the RL
  pool) and func_0 — its name-neighbour attractor already identified in
  `heldout_failure_mechanism.md` (func_0 → (s, pre) ×148, body from add_prefix) — was pulled
  into add_prefix's signature and then body, in the weights, until it no longer exists
  even alone. One op at 0.03 costs d8 0.84 → 0.42 because it appears in ~half of the
  depth-8 programs. So the "decline" is a single discrete binding overwrite, not diffuse
  forgetting; the damage was already 22% at step 20, when the depth-1 canary still read
  1.00 — a depth-1 monitor lags, a 2-3-def canary of each atomically-known skill would
  have caught it at step 20. Fix arms in OUTSTANDING.

  **Keep-all rerun (3292270, `rl_ra_grpo_d7to10_ecoinit_k_qwen3_4b`, 30 steps, SAVE=TEST=5,
  identical config, different rollout rng; `ci_rl_ra_grpo_d7to10_ecoinit_k_*.md`):**

  | step | 0 | 5 | 10 | 15 | 20 | 25 | 30 |
  |---|---|---|---|---|---|---|---|
  | held-out d4 / d8 | 0.98 / 0.84 | 0.97 / **0.93** | 0.98 / 0.89 | 0.96 / 0.73 | 0.93 / 0.55 | 0.91 / 0.39 | 0.87 / 0.32 |
  | held-out d8 episode-TypeError | 0.007 | 0.005 | 0.012 | 0.034 | 0.061 | 0.092 | 0.109 |
  | rlops d12 | 0.62 | 0.82 | 0.89 | 0.92 | 0.94 | 0.95 | 0.95 |
  | reward | — | 1.11 | 1.15 | 1.17 | 1.15 | 1.18 | 1.20 |
  | actor entropy | — | 0.0006 | 0.0019 | 0.0010 | 0.0006 | 0.0006 | 0.0007 |

  Same shape, peak earlier (step 5) and decline steeper (step 20 d8 0.55 vs 0.79 in the
  first run) — the onset is rng-dependent. **Entropy is NOT a usable stop signal**: it is
  ≈0.001 from step 1 and does not move with the onset (the "10× collapse" in the first run
  was one run's fluctuation; retracted). Nothing in the training-side metrics (reward,
  KL, length, entropy) marks the peak; only the held-out canary does. Peak checkpoints
  were LOST AGAIN: `CKPT_KEEP=` (empty) is not keep-all (`${VAR:-3}` treats empty as
  unset) — steps 5/10/15 pruned, 20/25/30 kept. Driver now maps CKPT_KEEP=all; third run
  `rl-eco-d7to10-k2` (job 3295454: 15 steps, save/val every 5, keep-all) to capture the
  peak for the per-op sweep.
- Issue #10: `run_rl_ra.sh` keeps only the last 3 checkpoints (CKPT_KEEP=3), so the
  step-10 checkpoint was deleted when step 40 saved; step 20 was copied to
  `rl_ra_grpo_d7to10_ecoinit_qwen3_4b/keep_global_step_20/huggingface`. Rerun
  `rl-eco-d7to10-k` (job 3292270: same init/data, 30 steps, SAVE_FREQ=TEST_FREQ=5,
  CKPT_KEEP empty = keep all) to recover the peak; `RL_TRAIN_FILE` added to the driver.

---

## N-SCALING (paper50; pre-registered 2026-09-04; COMPLETE 2026-09-05, 3 seeds per cell)

The 2^n question: does the per-op cost of load-robust binding, and the composition-demo
requirement, stay O(n) as the number of primitives grows? Pool `paper50` = the 25 paper ops
+ 25 extension ops (`operators.py`, func_25..func_49; 13 → train, 12 → eval), so train = 26
ops, held-out = 24 (the original 12 + 12 new). The paper pool's generation stream is
byte-identical (regression-checked against HEAD). Data recipe per op unchanged
(`build_pool_data.sh paper50 num paper50`: 800 stage-1.5 rows/op → 40k + 12k comps,
400 RA atomic tasks/op → 20k, 16k mixed d2-4 comps over the 26 train ops). Stage-1.5 is
trained **from base** (no RFT-cx stage-1 exists for 50 ops), so the comparison line is the
n=25 from-base pair of §① (numfb: v1 0.52±0.24, E-co 0.77±0.07 on the same orig12 file).

| cell (× seeds 1/7/123) | atomic side (50 ops) | comps | tests |
|---|---|---|---|
| v1-50 | single-task | 16k d2-4 over 26 train ops | orig12 (= the paper pool's own held-out file, directly comparable), new12, heldout24, trainops26 |
| eco-50 | E-co grouping | same | same |
| eco-50-n13 | E-co grouping | the paper pool's 16k comps over its 13 train ops | same |

Build (`build_pool_data.sh paper50 num paper50`, sources 60k rows each): stage15 40,000,
stage15b 52,000 (comp source d2 19,925 / d3 19,999 / d4 20,000), stage2_level1to4 50,000,
tests 2,048 × {heldout24, trainops26, new12}, RA v1 35,734 / eco 23,805 / eco_n13 23,794 rows
(gate 100% ok). Jobs: stage-1.5 `stage15b_paper50_frombase_qwen3_4b` 3291573 (4 nodes,
from base, 52k rows → ~810 steps); RA (depend=afterok, seeds 1/7/123): v1-50 3291574-76,
eco-50 3291577-79, eco-50-n13 3291580-82; CI files `ci_ra_abl_paper50_<var>[_s*]_b3072{,_orig12,_new12,_trainops}.md`.

Predictions. O(n) holds if eco-50 on orig12 ≈ 0.77 (n=25 from base) at the same 400
rows/op; a clear drop means more competitors need more practice per op (cost grows with n).
eco-50 vs eco-50-n13 extends the diversity curve (26 vs 13 composed ops at 16k). new12 ≈
orig12 means the recipe is op-agnostic. v1-50 vs v1 numfb measures interference growth
without load practice. Decision rule as before (3-seed bands).

**RESULTS** (held-out CI d4 / d8, mean±sd over seeds 1/7/123; `ci_ra_abl_paper50_<var>[_s*]_b3072[_orig12|_new12|_trainops].md`):

| cell | orig12 (same file as every paper-pool number) | new12 | heldout24 | trainops26 |
|---|---|---|---|---|
| n=25 v1 (numfb, from base) | 0.52±0.24 / 0.21±0.14 | — | — | trainops13 ≈1.00 / 0.89 |
| n=25 E-co (numfb, from base) | 0.77±0.07 / 0.52±0.26 | — | — | 1.00 / 0.87 |
| **v1-50** | 0.64±0.11 / 0.21±0.14 | 0.72±0.13 / 0.32±0.11 | 0.64±0.11 / 0.24±0.10 | 1.00 / 0.73±0.02 |
| **eco-50** | **0.79±0.11** / 0.32±0.15 | 0.97±0.03 / 0.67±0.17 | 0.85±0.08 / 0.41±0.12 | 1.00 / 0.74±0.01 |
| eco-50-n13 (comps over the paper's 13 train ops only) | 0.67±0.19 / 0.24±0.21 | 0.94±0.06 / 0.75±0.01 | 0.78±0.14 / 0.36±0.17 | 1.00 / 0.77±0.02 |

Test-set geometry (distinct ops per program, k): orig12 identical to the paper pool (3.95 /
6.08 / 7.79 at d4/6/8); new12 is EASIER (k 3.49 / 4.98 / 6.71 — the extension ops include
no two-string op, so binary branches fall to `+`), so new12 vs orig12 is not an op-agnosticity
test; heldout24 and trainops26 are HARDER at depth (k 9.90 / 10.04 at d8 vs 7.79 / 8.64).
eco-50 data: 89% of held-out defs under load (audit), same as E-co.

Readings:
1. **Per-op binding cost is O(n) at mid depth: confirmed.** eco-50 on the paper's own 12
   held-out ops at the paper's own 400 atomic tasks/op = 0.79±0.11 vs 0.77±0.07 at n=25 —
   identical, with 25 more competitors in every multi-def context and in the weights. v1-50
   (0.64±0.11) is not worse than v1-25 (0.52±0.24) either: interference without load
   practice does not grow with n.
2. **Deep-depth reliability got worse for everyone at n=50, on identical programs:** eco-50
   orig12 d8 0.32 vs 0.52 (n=25; seeds 0.49/0.13/0.34 vs 0.87/0.46/0.25, overlapping bands),
   and train-op d8 0.74 vs 0.87 (there the test is also harder, k 10.0 vs 8.6). Since
   orig12 is the same file, the drop is a model property. The comp budget was held at 16k
   while the composed ops doubled 13 → 26, so per-op composition exposure halved; the
   component that decays with depth (C) tracks the per-op composition exposure of the
   composed ops, i.e. the composition side also wants O(n) rows (per-op coverage), not O(1).
   Refines the earlier "composition side is O(1)" claim to: O(1) in *kinds* of demonstration
   (one depth suffices), O(n) in *rows* to keep per-op coverage.
3. **Diversity of composed ops at fixed budget: 26 vs 13** — eco-50 ≥ eco-50-n13 on every
   held-out set (0.79 vs 0.67 orig12, 0.85 vs 0.78 heldout24, 0.97 vs 0.94 new12) but the
   bands overlap (sd 0.11-0.19); direction matches the nops4/8/13 curve, not decisive at n=3.
4. **The new 12 held-out ops compose at 0.97±0.03 (d4) with zero composition data** — the
   recipe transfers to a fresh op set built after the method was fixed (no tuning on them).
5. Init caveat (#9) applies: all from-base. The paper-pool headline (0.97 on the RFT-cx
   init) has no n=50 counterpart yet.

Verdict on the 2^n question: the per-skill cost of load-robust binding does not grow
with the number of skills (item 1), composition demos need per-op coverage (O(n)) but not
combinatorial coverage (item 2, and the paper-pool d12/C3/C4b results), and unseen skills
compose at the rate their binding allows (item 4). Nothing measured scales with the
number of compositions.

---

## OUTSTANDING (for the next session)

- [ ] ③ co-occurrence: pfirst/plast seed 123; eptr rebuilt with ≥90% of held-out
      defs under load (larger train partner pool); epho variant without the
      train-op head; 2×2 partner × position at matched load.
- [x] ① name ablation, matched: done 2026-09-03 (refuted, all 3 seeds × 3 schemes
      × {v1, eco}); classification in `cls_name_ablation_*.md`.
- [x] H0/H1 cells: all 27 done and written up ("H0/H1 RESULTS", 2026-09-03 20:22).
- [ ] C: read eco_d28 ×3 and rl-eco-d7to10 (3290812) when done; fill the C table.
- [x] N-scaling: done 2026-09-05 (table above). Per-op classification of eco-50 on orig12
      (`cls_paper50_eco_orig12.md`): seeds 1 and 123 have all 12 held-out ops ≥ 0.9
      episode-ok; seed 7 has exactly one collapsed op, func_24 backchain_palindrome
      (0.28 ok / 0.72 TypeError) — the same bistable single-op flip and the same op as at
      n=25 from base (§①). Binding structure unchanged at n=50.
- [ ] N-scaling follow-up: eco-50 with comps scaled to 32k (per-op coverage matched to the
      paper pool) — tests reading 2 directly.
- [ ] Init variance (issue #9): E-co / v1 on a second RFT-cx-initialised stage-1.5
      seed, or stage-1.5 from base with 3 seeds — the headline's sd is understated.
- [ ] RL-E-co: rerun with save_freq=10 + early stop on response length /
      held-out val + stronger KL; re-eval the last pre-collapse ckpt.
- [ ] 8B line: fix HF export (sharded save or offline convert), then v1-8b / eco-8b.
- [ ] give alt-line jobs a distinct ABL tag so CI md never collides again.
