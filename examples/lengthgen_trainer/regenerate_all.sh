#!/bin/bash
# Regenerate ALL length-gen datasets with the unified prompts.
#   per-task cot/code  ->  all_tasks cot/code (concat)  ->  code_exec (derive)
# Writes into data/lengthgen/. Back up any existing data first.
set -euo pipefail

cd "$(dirname "$0")/../.."          # repo root: .../verl
PY=/work/go39/b20033/code/generalization_venv/bin/python
GEN=examples/lengthgen_trainer/generate_data.py
ALL=examples/lengthgen_trainer/build_all_tasks.py
CEX=examples/lengthgen_trainer/build_codeexec_from_code.py
TASKS=(lis knapsack_01 max_subarray)

echo "############ 1/4  per-task cot + code ############"
for task in "${TASKS[@]}"; do
  for cond in cot code; do
    echo "=== generate_data: $task / $cond ==="
    "$PY" "$GEN" --task "$task" --condition "$cond" --n_eval_total 200
  done
done

echo "############ 2/4  all_tasks cot + code (concat) ############"
"$PY" "$ALL" --condition cot
"$PY" "$ALL" --condition code

echo "############ 3/4  per-task code_exec (derive from *_code) ############"
for task in "${TASKS[@]}"; do
  echo "=== build_codeexec: $task ==="
  "$PY" "$CEX" --task "$task"
done

echo "############ 4/4  all_tasks code_exec (derive from all_tasks_code) ############"
"$PY" "$CEX" --task all_tasks

echo "############ DONE ############"
