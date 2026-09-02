# Compositional-Generalization Trainer

Tests whether a model that learns **atomic string skills** can **compose** them,
and how far that composition **generalizes** — to deeper nesting and to
**held-out operators never trained on**. Built on verl, mirroring the
`lengthgen_trainer` / `reval_trainer` conventions (zero verl-core edits; custom
reward via `reward.custom_reward_function.path`).

This directory is the **baseline codebase** (static two-stage pipeline). The
self-play curriculum and learned questioner are layered on top later (roadmap
below).

## Concepts

- **Atomic skills** — ~25 string operators (`func_0…func_24`), copied verbatim
  from RL-Compositionality so the `paper` pool is a faithful baseline.
- **Stage 1** (bodies *shown*): the model learns what each `func_N` does.
- **Stage 2** (bodies *hidden*): the model must recall + compose them — the real
  compositional test. Trains on **train ops**, evaluated on **disjoint held-out
  ops**.
- **Forward task**: predict `main_solution(x)`'s output as `{"output": ...}`.
  Scored by pure-Python string match — no sandbox.

### Two operator pools (`operators.py`)

| pool | ops | use | depth reach |
|---|---|---|---|
| `paper` | all 25, paper train(13)/eval(12) split | **baseline** (faithful to RL-Compositionality) | shallow (growth ops blow up) |
| `lenpres` | 8 length-preserving, unary (subset of the 25) | **deep track** | depth 100+ (output stays = input length) |

`lenpres` inherits the paper's train/eval assignment, e.g. `while_rotate` (train)
≡ `rotate_str` (held-out) — a free "same-operation, new-name" transfer probe.
Empirically (`python executor.py`) length-preserving compositions stay at input
length and run in ~0.1 ms even at depth 100/500 — this is what makes deep eval
tractable.

## Files

| file | role |
|---|---|
| `operators.py` | operator library + pools/splits (plumbing) |
| `executor.py` | safe ground-truth execution (length cap, timeout, recursion guard) |
| `generate_data.py` | parquet generator (stage 1/2, any pool, any depth) |
| `reward_fn.py` | forward-task reward (JSON/`\boxed` extraction + match) |
| `selection.py` | pluggable top-K curriculum selection (random default; frontier stub) |
| `build_baseline_data.sh` | generate all baseline parquet for a pool |
| `train_pbs_header.sh` | shared Miyabi PBS env + `launch_training` |
| `train_per_node.sh` | per-node Ray bootstrap; `RL_METHOD={grpo,reval}` |
| `train_stage1.sh` / `train_stage2.sh` | RL job scripts (grpo/reval) |
| `_sft_launch.sh` / `_rollout_launch.sh` | per-node **SFT** (FSDP) / **RFT rollout** (vLLM) primitives; launched by `launch_mpi` |
| `build_sft_data.py` / `train_stage1_sft.sh` | **SFT** Stage-1 (8-node FSDP): synthetic-trace data → SFT |
| `rollout_stage1.py` / `build_rft_data.py` / `run_stage1_rft.sh` | **RFT** Stage-1 (8-node, paper's recipe): iterative data-parallel rollout → keep-correct → FSDP SFT |
| `build_ra_sft_data.py` / `build_ra_rft_data.py` / `build_ra_elicit_data.py` / `run_ra_depth_ablation.sh` / `run_ra_rft.sh` / `classify_ra_failures.py` | **recall-then-assemble (RA)**: stitched bootstrap-SFT targets (`--format v1\|v2`, `--self-check`), verification gate, elicitation prompts, variant/seed driver, sweep failure classifier (WALKTHROUGH §14-17, `doc/COMPOSITIONAL_HISTORY.md` §10-11) |
| `build_codeexec_data.py` / `reward_fn_codeexec.py` / `run_stage1_rft_codeexec.sh` / `train_stage2_codeexec.sh` | **one-shot code-exec condition**: plan → ONE program, executed once at reward time (see [`README_codeexec.md`](README_codeexec.md)) |

**Stage-1 method.** The paper acquires atomic skills via **iterative RFT**, not
RL — and that matters: our GRPO Stage-1 did not instil held-out *recall* (held-out
Level-1 ≈0.4 vs the paper's ≈0.9), which caps the paper-pool baseline. See
`WALKTHROUGH.md` §5–6. RL / RFT / SFT are kept as separate scripts; RFT composes
the SFT primitive (`_sft_launch.sh`).

```bash
# Faithful Stage-1 RFT (rollout -> keep-correct -> SFT, iterated), then Stage 2:
POOL=paper RFT_ITERS=3 qsub examples/compositional_trainer/run_stage1_rft.sh
MODEL_PATH=<final rft ckpt> POOL=paper qsub examples/compositional_trainer/train_stage2.sh
```

## Quick start

```bash
# One-shot: build data + chain Stage 1 -> Stage 2 (PBS afterok dependency).
POOL=paper bash examples/compositional_trainer/run_baseline.sh
DRY_RUN=1 POOL=lenpres RL_METHOD=reval bash examples/compositional_trainer/run_baseline.sh  # print, don't submit
```

Or step by step:

```bash
# 0. (smoke) tiny data to sanity-check end to end
SMOKE=1 bash examples/compositional_trainer/build_baseline_data.sh lenpres

# 1. Generate baseline data
bash examples/compositional_trainer/build_baseline_data.sh paper     # baseline
bash examples/compositional_trainer/build_baseline_data.sh lenpres   # deep track

# 2. Stage 1 (atomic skills, from base model)
POOL=paper qsub examples/compositional_trainer/train_stage1.sh

# 3. Stage 2 (compositions, from the Stage-1 checkpoint)
POOL=paper MODEL_PATH=checkpoints/compositional/stage1_paper_grpo_qwen3_4b/global_step_400/actor/huggingface \
  qsub examples/compositional_trainer/train_stage2.sh

# value-based off-policy instead of GRPO:
RL_METHOD=reval POOL=lenpres MODEL_PATH=<stage1_ckpt> \
  qsub examples/compositional_trainer/train_stage2.sh
```

### Recall-then-assemble (RA) bootstrap SFT

The best held-out result (WALKTHROUGH §14-15) is ONE SFT on *stitched* RA
targets from the stage-1.5 checkpoint — no RL, no RFT. `build_ra_sft_data.py`
stitches them; every row passes the RFT gate (`build_ra_rft_data.check_response`).

```bash
CT=examples/compositional_trainer
# v2 format (COMPOSITIONAL_HISTORY §10.3): enumerated plan line, per-episode
# arity cue from the call site, sequential Assemble (t1 = ...; return tN),
# funcless rows; --self-check adds `Check: func_N(probe) -> out` after each def.
python $CT/build_ra_sft_data.py \
    --comp_path   data/compositional/paper/stage2_level1to4_codeexec/train.parquet \
    --atomic_path data/compositional/paper/stage15_closedbook_codeexec/train.parquet \
    --out_dir     data/compositional/paper/ra_rft/sft_bootstrap_v2 \
    --format v2 [--self-check] --n_comp 16000 --n_atomic 10000 --n_funcless 1500
# --format v1 (--n_funcless 0 default) = the original §14 data.

# SFT from stage15b + greedy d1-8 sweep + CI, one job per (variant list, seed);
# data dir = ra_rft/sft_bootstrap_<variant>:
qsub -N ra-v2-s1 -v ABL_VARIANTS=v2+v2_sc,SFT_SEED=1,ABL_TEST_SETS=heldout+trainops \
    $CT/run_ra_depth_ablation.sh     # ROLLOUT_MAX_TOKENS default 3072
```

### RL method switch

- `RL_METHOD=grpo` → `verl.trainer.main_ppo`, `adv_estimator=grpo` (policy-gradient baseline).
- `RL_METHOD=reval` → `verl.trainer.main_reval`, `adv_estimator=reval` (value-based,
  off-policy; `V_θ = logsumexp(logits)`, no separate critic). This is the
  "mixed value/policy" method and its FIFO buffer is the basis for off-policy
  trajectory replay. See `../reval_trainer/README.md`.

### Replay (anti-forgetting)

`TRAIN_FILE` accepts a comma-separated list, so data-level replay is free:
```bash
TRAIN_FILE="data/.../stage2_level1to2/train.parquet,data/.../stage1_level1/train.parquet"
```
The faithful off-policy trajectory buffer (reval gap #2) is a Phase-3 upgrade.

## Evaluation

Stage-2 `VAL_FILES` are the held-out eval splits, so verl logs per-split accuracy
during training (**Mode 1**: predict the final output; `has_answer` separates
genuine reasoning failure from response truncation). For `lenpres`: `eval_iid`
(train ops, shallow), `eval_easy` (held-out, depth 2-3), `eval_medium` (depth 10),
`eval_hard` (depth 100). Headline metric = **effective compositional depth** D\*
(largest depth with acc ≥ 0.5).

Mode 2 (intermediate-checkpoint probe) and Mode 3 (chunked multi-turn) are
planned standalone eval scripts (roadmap).

## Roadmap

Self-play (Phases 2–3) is designed in **[`SELFPLAY.md`](SELFPLAY.md)** — outer
loop, saturation gate, `S`-replay, `selection.py` pruning, learned questioner.

- **Phase 1 (this dir):** static two-stage GRPO/reval baseline + Mode-1 eval. ✅
- **Phase 1.5:** standalone `eval/` (Modes 1–3, depth sweep, D\*).
- **Phase 2:** curriculum outer-loop — expand `C` from train ops, train to
  saturation (val acc ≥ 0.95 on held-out depth-d) with replay from `S`, prune via
  `selection.py`, advance depth. Orchestrates unmodified verl.
- **Phase 3:** learned questioner (frontier/learning-progress reward), faithful
  off-policy reval buffer, OPD Stage-1 with a 32B teacher.

## AI-assistance disclosure

Drafted with AI assistance. Per `CLAUDE.md` §1, a human submitter must review
every changed line and run the relevant tests before any upstream contribution.

## H0/H1 campaign (2026-09-02) — does load-robust binding transfer across ops?

Plan and pre-registered predictions: `analysis/RESULTS_PROVENANCE.md` "H0/H1 PLAN".

```bash
source /work/go39/b20033/code/generalization_venv/bin/activate
CT=examples/compositional_trainer
bash $CT/build_h01_cells.sh                      # CPU: sub0/3/6/9, dose25/50/75, nops4/8 data
bash $CT/build_pool_data.sh paper_alt  alt       # CPU: matched letter-name pools (32k stage15b)
bash $CT/build_pool_data.sh paper_alt2 alt2
DRY_RUN=1 bash $CT/submit_h01_campaign.sh        # prints every qsub line; DRY_RUN=0 submits
```

Knobs behind the cells (`build_ra_sft_data.py`): `--cooc_heldout_k K [--cooc_heldout_seed]`
(only K held-out ops get co-occurrence practice; writes `treated_ops.json`), `--multi_frac F`
(fraction of atomic tasks grouped), `--partner_reuse` (keeps `--partner_split` cells at full
load). Readouts: `compositionality_index.py --op-groups treated_ops.json` (accuracy on
programs whose ops all lie in one group) and `classify_ra_failures.py` (per-op episode
verdicts) — both run automatically at the end of `run_ra_depth_ablation.sh` when the data
dir has `treated_ops.json` (or `ABL_CLASSIFY=1`). `audit_multi_atomic_data.py <dir>` prints
the measured under-load / position / partner statistics of any multi-atomic data set.
Name schemes: `COMPOSITIONAL_NAME_SCHEME=num|alt|alt2` (`operators.py`); the drivers set it
from `POOL` (paper_alt → alt, paper_alt2 → alt2). `ABL_TAG=<tag>` keeps a re-run from
colliding with existing ckpt / sweep / CI names; `RA_INIT` may be an experiment dir.
