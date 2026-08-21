# Code-Execution Ablation (`code_exec`)

A **brand-new, standalone pipeline** added alongside the existing `cot` / `code`
conditions. It does **not** modify any existing file (`generate_data.py`,
`reward_fn.py`, training scripts are all untouched).

## What it tests

The existing `code` condition asks the model to write a Python function and then
*mentally trace it* to a `\boxed{}` answer. On long (OOD) inputs the model cannot
mentally execute its own code, so it hallucinates or never reaches an answer.

`code_exec` keeps the **exact same prompt** (abstract → code → apply), but takes
the answer from **actually executing the model's function** on the real input,
instead of from `\boxed{}`. This isolates *"can the model write correct code"*
from *"can it mentally run it"*, and is length-invariant: a correct function
generalizes to any `n`.

Because the function appears early (Step 2), even responses that truncate during
the verbose Step-3 trace usually still yield a runnable function.

## New files (nothing else changed)

| File | Purpose |
|---|---|
| `build_codeexec_from_code.py` | **Canonical data step.** Derives `data/lengthgen/{task}_code_exec/*.parquet` from the existing `{task}_code/*.parquet` — prompts/ground-truth/instances are byte-identical to the `code` runs; only adds `extra_info["call_args"]` and sets `condition="code_exec"`. Validates every row by re-solving the parsed input. Use this so the ablation differs from `code` **only** in the reward. |
| `generate_data_codeexec.py` | Alternative: generates *fresh* `code_exec` data from scratch (same eval lengths/counts as `code`, different random instances). Use only if you don't need identical instances. |
| `reward_fn_codeexec.py` | Reward fn: extracts the model's function, executes it in an isolated, resource-limited subprocess, calls it on `call_args`, compares output to ground truth. |
| `train_{lis,knapsack_01,max_subarray}_code_exec.sh` | PBS launch scripts; identical settings to the `code` scripts but point at the `code_exec` data dir and set `REWARD_FN=reward_fn_codeexec.py`. |

## Quick start

```bash
# 1. Build code_exec data from the existing *_code data (identical instances).
#    (Requires data/lengthgen/{task}_code/ to already exist.)
for task in max_subarray lis knapsack_01; do
  python examples/lengthgen_trainer/build_codeexec_from_code.py \
    --task $task --out_dir data/lengthgen
done

# 2. Train (Miyabi, 8 nodes)
qsub examples/lengthgen_trainer/train_lis_code_exec.sh
qsub examples/lengthgen_trainer/train_knapsack_01_code_exec.sh
qsub examples/lengthgen_trainer/train_max_subarray_code_exec.sh

# 3. Sanity-check the reward fn locally
python examples/lengthgen_trainer/reward_fn_codeexec.py
```

## How the answer is produced

1. Extract the first fenced code block that defines a function.
2. Run `<preamble: set CPU/mem/core rlimits> + <model code> + <driver>` via
   `python -I -S -c ...` in a subprocess (`timeout` wall-clock kill).
3. The driver reads `call_args` (JSON) from stdin, calls the solver
   (`solve` if present, else the last top-level user-defined function), and
   prints `__LGEN_RESULT__ <int>`.
4. Score = 1.0 if that int equals the ground truth, else 0.0 (+0.1 method bonus
   when abstract→code→apply is followed, mirroring the `code` condition).

`call_args` per task: `max_subarray`/`lis` → `[arr]`; `knapsack_01` → `[items, W]`.

## Sandbox / safety

Model-generated code is executed. Mitigations: fresh isolated interpreter
(`-I -S`), wall-clock timeout (`LENGTHGEN_EXEC_TIMEOUT`, default 5s), CPU-time
and address-space rlimits set inside the child (`LENGTHGEN_EXEC_CPU`,
`LENGTHGEN_EXEC_MEM_MB`, default 2048 MB), core dumps disabled. There is **no
network/filesystem isolation** — this assumes a trusted research cluster running
your own model. Tune the limits via the env vars above.

## Tunables (env vars)

- `LENGTHGEN_EXEC_TIMEOUT` (s, default 5) — wall-clock kill per sample.
- `LENGTHGEN_EXEC_CPU` (s, default timeout+1) — CPU-time rlimit in the child.
- `LENGTHGEN_EXEC_MEM_MB` (MB, default 2048) — address-space rlimit in the child.
- `LENGTHGEN_NUM_EXAMINE` (default 3) — sample printouts per (task, condition).
