# One-Shot Code-Execution Condition (`code_exec`)

A new experimental condition alongside the CoT forward task. The model may use
Python, but its program is **executed exactly once — at reward time, after the
response is complete — and the model never sees the output**. Whatever
`main_solution(x)` returns in the model's program IS its submitted answer.

## What it tests

In the CoT condition, compositional generalization is confounded with *mental
execution capacity*: at depth 8 (or 100) the model may know every operator yet
fail to trace the composition. `code_exec` removes that confound with a strict
separation of **planning** (free text: recall what each hidden `func_N` does)
and **action** (one self-contained program that re-implements every helper and
composes them exactly as `main_solution` specifies).

Because there is only ONE execution and no visible output, REPL-style
guess-and-check is impossible — the model is forced to commit to an **explicit
compositional function**. Correctness then factors cleanly:

> P(correct) ≈ ∏ over distinct ops used P(recall op's implementation) × P(transcribe the composition)

Depth is nearly free (the composition line can be copied from the prompt; the
sandbox does the execution), so the **held-out-operator axis** becomes the pure
measure of compositional generalization. The RL question: *does Stage-2 RL on
train-op compositions improve held-out-op accuracy, given Stage-1 atomic-skill
training?*

## Pipeline

Same two-stage structure as the baseline (see `README.md`), same instances:

1. **Data** — `build_codeexec_data.py` derives `*_codeexec` parquets from the
   existing baseline parquets. Programs/inputs/ref-outputs are byte-identical
   to the CoT condition; only the prompt (and the reward) differ.
2. **Stage 1 RFT** (`run_stage1_rft_codeexec.sh`, bodies SHOWN) — rollout →
   keep trajectories whose program *executes* to the right output → FSDP SFT,
   iterated. Correct trajectories reproduce each `func_N` as working code, so
   RFT bakes the atomic implementations into the model **in code space**.
3. **Stage 2 RL** (`train_stage2_codeexec.sh`, bodies HIDDEN) — GRPO/ReVal on
   train-op compositions; val on the disjoint held-out-op splits.

```bash
# 0. derive the data (instances identical to the baseline runs)
python examples/compositional_trainer/build_codeexec_data.py --pool paper
python examples/compositional_trainer/build_codeexec_data.py --pool lenpres

# 1. Stage-1 iterative RFT (code-exec condition)
POOL=paper RFT_ITERS=3 qsub examples/compositional_trainer/run_stage1_rft_codeexec.sh

# 2. Stage-2 RL from the final Stage-1 checkpoint
MODEL_PATH=<final rft-cx ckpt> POOL=paper qsub examples/compositional_trainer/train_stage2_codeexec.sh
RL_METHOD=reval POOL=lenpres MODEL_PATH=<...> qsub examples/compositional_trainer/train_stage2_codeexec.sh

# sanity-check the reward locally (no GPU needed)
python examples/compositional_trainer/reward_fn_codeexec.py
```

## How the answer is produced (`reward_fn_codeexec.py`)

1. Take the **last** fenced code block that defines a function (earlier
   text/blocks = the plan). `n_code_blocks`/`one_block` are logged; set
   `COMPOSITIONAL_STRICT_ONE_BLOCK=1` to zero-score multi-block responses
   (default is soft: multi-block responses just lose the format bonus — only
   the last block is ever executed either way, so the one-exec budget holds
   by construction).
2. Run `<rlimit preamble> + <model code> + <driver>` once via
   `python -I -S -c` in a subprocess (wall-clock timeout).
3. The driver reads `x` (JSON on stdin), calls `main_solution(x)`
   (`ground_truth["funcname"]`), and prints the returned string as one
   JSON-encoded sentinel line. The **last** sentinel wins, so a model that
   `print()`s a fake sentinel merely reimplements "return a literal".
4. Score = exact string match vs `ref_output`. A train-split-only format
   bonus (`COMPOSITIONAL_FORMAT_BONUS`, default 0.05) shapes
   plan + exactly-one-block; **val scores stay pure accuracy**, directly
   comparable to the CoT runs (identical instances).

Notes:
- Returning a hardcoded literal is allowed — it is exactly the CoT condition's
  "predict the output" strategy, and strictly harder than composing code.
- The shown Stage-1 code is not self-contained (`deterministic_shuffle` uses
  `gcd` from `operators.py`'s module-level import); the prompt therefore
  demands a self-contained program *including imports* — a verbatim copy
  without `from math import gcd` fails, and the RFT filter keeps only
  trajectories that add it.

## Sandbox / safety

Model code is executed: fresh isolated interpreter (`-I -S`), wall-clock
timeout (`COMPOSITIONAL_EXEC_TIMEOUT`, default 5 s), CPU-time + address-space
rlimits inside the child (`COMPOSITIONAL_EXEC_CPU`, `COMPOSITIONAL_EXEC_MEM_MB`,
default 2048 MB), core dumps off, 20 M-char return cap. No network/filesystem
isolation — assumes a trusted research cluster running your own model (same
posture as `lengthgen_trainer`'s `code_exec`).

## Files

| file | role |
|---|---|
| `build_codeexec_data.py` | derive `*_codeexec` parquets from baseline parquets (prompt-only rewrite; validates stage-1 rows by real execution) |
| `reward_fn_codeexec.py` | one-shot exec reward (self-tests in `__main__`) |
| `run_stage1_rft_codeexec.sh` | Stage-1 iterative RFT driver (8 nodes) for this condition |
| `train_stage2_codeexec.sh` | Stage-2 GRPO/ReVal job for this condition |

Shared with the baseline: `_rollout_launch.sh`, `_sft_launch.sh`,
`build_rft_data.py` (via `--reward_module reward_fn_codeexec`),
`train_pbs_header.sh` (REWARD_FN is now overridable), `train_per_node.sh`.

## Metrics glossary (wandb)

- `correctness` — executed answer == ref_output (the headline number).
- `exec_ok` — program ran and returned a string (vs crash/timeout/no code).
- `has_code`, `n_code_blocks`, `one_block`, `has_plan`, `follows_format` —
  plan/action format discipline.
- `depth` — composition depth of the instance.

## AI-assistance disclosure

Drafted with AI assistance. Per `CLAUDE.md` §1, a human submitter must review
every changed line and run the relevant tests before any upstream contribution.
