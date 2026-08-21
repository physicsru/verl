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
