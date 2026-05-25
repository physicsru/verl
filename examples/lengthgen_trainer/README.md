# Length-Generalization GRPO Training

Tests whether **code-first reasoning** generalizes better to longer DP problems
than plain chain-of-thought (CoT).

## Method

- **Condition A (CoT baseline):** Model solves step-by-step, outputs `\boxed{answer}`
- **Condition B (Code reasoning):** Model writes Python code, mentally traces it, outputs `\boxed{answer}`

Single-turn GRPO from Qwen3-4B-Base (no SFT). Three tasks: MaxSubarray, LIS, 0/1 Knapsack.

## Quick start

```bash
# 1. Generate data (all tasks & conditions)
for task in max_subarray lis knapsack_01; do
  for cond in cot code; do
    python examples/lengthgen_trainer/generate_data.py \
      --task $task --condition $cond --output_dir data/lengthgen
  done
done

# 2. Train (single node)
TASK=max_subarray CONDITION=code \
  bash examples/lengthgen_trainer/run_lengthgen_fsdp.sh

# 3. Train (Miyabi multi-node)
TASK=max_subarray CONDITION=code \
  qsub examples/lengthgen_trainer/submit_miyabi.sh

# 4. Evaluate
python examples/lengthgen_trainer/eval/run_eval.py \
  --model_path <checkpoint> --task max_subarray --condition code

# 5. Plot
python examples/lengthgen_trainer/eval/plot_results.py \
  --results_dir results/lengthgen
```

## AI-assistance disclosure

This pipeline was drafted with AI assistance. Per `CLAUDE.md` §1, a human
submitter must review every changed line and run relevant tests before any
upstream contribution.
