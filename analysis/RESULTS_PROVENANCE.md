# Compositional generalization — results provenance & verification ledger

Written 2026-09-02. Purpose: every claim below is traceable to a job log, data
dir, checkpoint, and CI report so it can be re-verified in a fresh session
without trusting summaries. **Read this before quoting any number.**

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

---

## MAIN RESULT — E-co vs v1 (the headline, 3 seeds each)

| cell | held-out d2 / d4 / d6 / d8 (mean±sd) | seeds | jobs | ckpts | CI reports |
|---|---|---|---|---|---|
| **v1** (single-task atomics + 16k mixed d2-4 comps) | 0.91±0.03 / 0.52±0.14 / 0.27±0.14 / 0.12±0.11 | 1,7,123 | seed1 = d14 bootstrap (job 2490799, swept @3072 in 2553298); s7 = 2847939; s123 = 2847940 | `ra_sft_bootstrap_paper_qwen3_4b/global_step_400` (seed1=d14); `…_v1_s{7,123}` | `ci_ra_abl_v1_b3072.md`(=d14 sweep `trainops_sweep_d14_ho_b3072`), `ci_ra_abl_v1_s{7,123}_b3072.md` |
| **E-co** (co-occurrence atomics + same 16k comps) | 1.00±0.00 / 0.97±0.02 / 0.89±0.09 / 0.73±0.15 | 1,7,123 | 3267112, 3267226, 3267227 | `ra_sft_bootstrap_paper_eco{,_s7,_s123}_qwen3_4b` | `ci_ra_abl_eco{,_s7,_s123}_b3072.md` |

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
Jobs: base seed = 3274458-62; s7 = 3275724/26/28/30/32; s123 = 3275739-43.
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
`analysis/c4_failures.md` (d8 failures = 62% episode-omission → d3-4 data fixes
episode-count extrapolation, a mechanical/length effect).

**Established, publishable (3-seed):** (i) co-occurrence ≫ frequency (E-co vs
v1, C5 vs v1); (ii) composition without composition data is real (C1);
(iii) structure diversity > volume (C3 vs C2/C4); (iv) depth diversity is the
dominant comp-side factor (C4b, E-co vs C4).

---

## ③ CO-OCCURRENCE STRUCTURE: partner identity vs position

`--partner_split` restricts held-out ops' partners; `--heldout_position` pins
held-out tasks to group head/tail (both in `build_ra_sft_data.py`; smokes 0
violations). Comps fixed at 16k d2-4.

| cell | held-out partners | held-out position | d4 / d8 | seeds | jobs |
|---|---|---|---|---|---|
| eptr | train ops only | (mostly head) | 0.53±0.07 / 0.11±0.02 | 1,7,123 | 3278550,3279489,3279490 |
| epho | held-out only | (mostly tail) | 0.83±0.03 / 0.46±0.17 | 1,7,123 | 3278551,3279491,3279492 |
| pfirst | random | HEAD (forced) | 0.88±0.11 / 0.59±0.20 | 1,7 | 3279504,3279505 |
| plast | random | TAIL (forced) | 0.98±0.01 / 0.73±0.08 | 1,7 | 3279506,3279507 |
| E-co | random | random | 0.97±0.02 / 0.73±0.15 | 1,7,123 | (above) |

Reading (PRELIMINARY, pfirst/plast n=2): the driver is **position, not partner
identity** — plast ≈ E-co ≫ pfirst; practising the held-out def in the hard
(late) position is what matters. NEEDS: pfirst/plast seed 123 (pfirst sd is
±0.20). Data dirs `sft_bootstrap_{eptr,epho,pfirst,plast}`.

---

## ① NAME ABLATION (digit-token neighbour confusion)

Controlled pair, both from Qwen3-4B-Base, identical pipeline, only the opaque
op-name scheme differs (`COMPOSITIONAL_NAME_SCHEME` in `operators.py`:
num=`func_10`, alt=`func_qzk`). PRELIMINARY (n=1 each).

| naming | held-out d2 / d4 / d6 / d8 | stage15b job | RA-v1 job | ckpt | CI report |
|---|---|---|---|---|---|
| num (`func_10`) | 0.95 / 0.71 / 0.47 / 0.28 | 3278516 (memsw at teardown; ckpt OK step 500) | 3279397 | `ra_sft_bootstrap_paper_v1_qwen3_4b` | `analysis/ci_v1_numfb_b3072.md` |
| **alt (`func_qzk`)** | 0.99 / **0.98** / 0.93 / **0.90** | 3279056 | 3279398 | `ra_sft_bootstrap_paper_alt_v1_qwen3_4b` (in `paper_alt/`) | `analysis/ci_v1_altfb_b3072.md` |

Data lines: num = `data/compositional/paper/…` (existing); alt =
`data/compositional/paper_alt/…` (regenerated with alt names). To evaluate/
regenerate the alt CI you MUST set `COMPOSITIONAL_NAME_SCHEME=alt` in the env.

**Finding (needs replication + chimera classification):** non-numeric names
raise held-out d8 from 0.28 → 0.90 — supports "collapse is largely digit-token
neighbour confusion (func_10↔func_11)". TODO before publishing: 2 more seeds
each; run `classify_ra_failures.py` on the alt sweep to confirm chimera
collapse actually disappears (not just accuracy up).

---

## ② RL-E-co — see KNOWN ISSUE #2 (collapsed; steps ≤40 only)

Job 3279399 `rl-ecorl.o3279399`. Pool
`data/compositional/paper/structured/pool_w14d/train.parquet` (parmt widths 1-4,
all 25 ops, split=train). Prefilter 3278553. Init = v1 d14 ckpt. Trajectory:
step0 d4 0.75 → step20 0.96 → step40 0.96 → **step60 0.14 (collapse)**.
Ckpts `rl_ra_grpo_w14_v1init_ecorl_qwen3_4b/global_step_{50,…}` (step-50 is
POST-collapse; the good ckpt would be ~step-40, not saved at that freq —
rerun with save_freq=20 + early stop).

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

## OUTSTANDING (for the next session)

- [ ] name ablation: +2 seeds each (num/alt); chimera classification on alt sweep.
- [ ] RL-E-co: re-eval step-40 ckpt; rerun with save_freq=20 + early stop / higher KL.
- [ ] 8B line: fix HF export (sharded save or offline convert), then v1-8b / eco-8b.
- [ ] ③ position: pfirst/plast seed 123.
- [ ] give alt-line jobs a distinct ABL tag so CI md never collides again.
