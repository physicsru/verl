"""Generate parquet datasets for length-generalization GRPO training.

Usage:
    python examples/lengthgen_trainer/generate_data.py \
        --task max_subarray --condition code --output_dir data/lengthgen

Produces:
    data/lengthgen/max_subarray_code/train.parquet
    data/lengthgen/max_subarray_code/test.parquet
"""

import argparse
import os
import random
import sys

import datasets

# Add the task package to path.
# verl repo:       /work/go39/b20033/code/generalization/verl
# task package:    /work/go39/b20033/code/generalization/length_generalization
# this file:       .../verl/examples/lengthgen_trainer/generate_data.py
TASK_PKG = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "length_generalization",
))
if not os.path.isfile(os.path.join(TASK_PKG, "tasks.py")):
    raise FileNotFoundError(
        f"Cannot find tasks.py at {TASK_PKG}. "
        "Set LENGTHGEN_TASK_PKG env var to override."
    )
sys.path.insert(0, os.environ.get("LENGTHGEN_TASK_PKG", TASK_PKG))

from tasks import TASKS, MaxSubarray, LIS, Knapsack01

# ============================================================================
# Problem renderers — override tasks.py to use \boxed{} instead of Answer:
# ============================================================================

CODE_INSTRUCTION = (
    "Let's think step by step. First, understand the problem and restate it in the "
    "abstract, as a general problem for an input of arbitrary length. Then write a "
    "Python function that solves the general case. Finally, apply your function to the "
    "given input and put the final answer in \\boxed{}."
)

COT_INSTRUCTION = (
    "Let's think step by step. Reason through the problem carefully, then put the "
    "final answer in \\boxed{}."
)


def render_problem_max_subarray(inst, condition="cot"):
    instruction = CODE_INSTRUCTION if condition == "code" else COT_INSTRUCTION
    return (
        f"Given the array {inst.arr}, find the maximum contiguous subarray sum "
        f"using dynamic programming.\n"
        f"{instruction}"
    )

def render_problem_lis(inst, condition="cot"):
    instruction = CODE_INSTRUCTION if condition == "code" else COT_INSTRUCTION
    return (
        f"Given the sequence {inst.arr}, find the length of the longest strictly "
        f"increasing subsequence using dynamic programming.\n"
        f"{instruction}"
    )

def render_problem_knapsack(inst, condition="cot"):
    items_str = ", ".join(f"({w},{v})" for (w, v) in inst.items)
    instruction = CODE_INSTRUCTION if condition == "code" else COT_INSTRUCTION
    return (
        f"0/1 Knapsack with capacity W = {inst.W}.\n"
        f"Items (weight, value): [{items_str}]\n"
        f"{instruction}"
    )

PROBLEM_RENDERERS = {
    "max_subarray": render_problem_max_subarray,
    "lis": render_problem_lis,
    "knapsack_01": render_problem_knapsack,
}


# ============================================================================
# Prompt renderers — \boxed{} format, two conditions
# ============================================================================

# ---- CoT solution renderers (Condition A) ----

def _render_cot_max_subarray(inst, dp_trace, answer):
    lines = []
    for i, dp_i in enumerate(dp_trace, start=1):
        if i == 1:
            lines.append(f"dp[1] = {dp_i}")
        else:
            arr_i = inst.arr[i - 1]
            prev = dp_trace[i - 2]
            lines.append(
                f"dp[{i}] = max(arr[{i}], dp[{i-1}] + arr[{i}]) "
                f"= max({arr_i}, {prev} + {arr_i}) = max({arr_i}, {prev + arr_i}) = {dp_i}"
            )
    lines.append(f"Maximum of dp = {answer}")
    lines.append(f"\\boxed{{{answer}}}")
    return "\n".join(lines)


def _render_cot_lis(inst, dp_trace, answer):
    lines = []
    for i, dp_i in enumerate(dp_trace, start=1):
        if i == 1:
            lines.append("dp[1] = 1")
        else:
            xs_i = inst.arr[i - 1]
            preds = [(j + 1, dp_trace[j]) for j in range(i - 1) if inst.arr[j] < xs_i]
            if not preds:
                lines.append(f"dp[{i}] = 1")
            else:
                pred_str = ", ".join(f"dp[{j}]={d}" for (j, d) in preds)
                best = max(d for (_, d) in preds)
                lines.append(f"dp[{i}] = 1 + max({{{pred_str}}}) = 1 + {best} = {dp_i}")
    lines.append(f"Maximum of dp = {answer}")
    lines.append(f"\\boxed{{{answer}}}")
    return "\n".join(lines)


def _render_cot_knapsack(inst, dp_trace, answer):
    lines = []
    for i, row in enumerate(dp_trace, start=1):
        w_i, v_i = inst.items[i - 1]
        lines.append(f"# After item {i} (w={w_i}, v={v_i})")
        lines.append(f"dp[{i}] = {row}")
    lines.append(f"dp[{inst.n}][{inst.W}] = {answer}")
    lines.append(f"\\boxed{{{answer}}}")
    return "\n".join(lines)


COT_RENDERERS = {
    "max_subarray": _render_cot_max_subarray,
    "lis": _render_cot_lis,
    "knapsack_01": _render_cot_knapsack,
}


# ---- Code solution renderers (Condition B: abstract → code → apply) ----

def _render_code_max_subarray(inst, dp_trace, answer):
    dp_str = str(dp_trace)
    return (
        f"Step 1 - Abstract: Given an array of integers, find the maximum sum of any "
        f"contiguous subarray. This is Kadane's algorithm using dp[i] = max(arr[i], dp[i-1] + arr[i]).\n\n"
        f"Step 2 - Code:\n"
        f"```python\n"
        f"def max_subarray_sum(arr):\n"
        f"    n = len(arr)\n"
        f"    dp = [0] * n\n"
        f"    dp[0] = arr[0]\n"
        f"    for i in range(1, n):\n"
        f"        dp[i] = max(arr[i], dp[i-1] + arr[i])\n"
        f"    return max(dp)\n"
        f"```\n\n"
        f"Step 3 - Apply to {inst.arr}:\n"
        f"dp = {dp_str}\n"
        f"max(dp) = {answer}\n"
        f"\\boxed{{{answer}}}"
    )


def _render_code_lis(inst, dp_trace, answer):
    dp_str = str(dp_trace)
    return (
        f"Step 1 - Abstract: Given a sequence of integers, find the length of the longest "
        f"strictly increasing subsequence. Use dp[i] = 1 + max(dp[j] for j < i if arr[j] < arr[i]).\n\n"
        f"Step 2 - Code:\n"
        f"```python\n"
        f"def lis_length(arr):\n"
        f"    n = len(arr)\n"
        f"    dp = [1] * n\n"
        f"    for i in range(1, n):\n"
        f"        for j in range(i):\n"
        f"            if arr[j] < arr[i]:\n"
        f"                dp[i] = max(dp[i], dp[j] + 1)\n"
        f"    return max(dp)\n"
        f"```\n\n"
        f"Step 3 - Apply to {inst.arr}:\n"
        f"dp = {dp_str}\n"
        f"max(dp) = {answer}\n"
        f"\\boxed{{{answer}}}"
    )


def _render_code_knapsack(inst, dp_trace, answer):
    items_str = str(inst.items)
    last_row = dp_trace[-1] if dp_trace else []
    return (
        f"Step 1 - Abstract: Given n items with (weight, value) and capacity W, find the "
        f"maximum total value without exceeding W. Each item used at most once. "
        f"Use dp[i][w] = max(dp[i-1][w], dp[i-1][w-w_i] + v_i).\n\n"
        f"Step 2 - Code:\n"
        f"```python\n"
        f"def knapsack_01(items, W):\n"
        f"    n = len(items)\n"
        f"    dp = [[0] * (W + 1) for _ in range(n + 1)]\n"
        f"    for i in range(1, n + 1):\n"
        f"        w_i, v_i = items[i - 1]\n"
        f"        for w in range(W + 1):\n"
        f"            dp[i][w] = dp[i-1][w]\n"
        f"            if w >= w_i:\n"
        f"                dp[i][w] = max(dp[i][w], dp[i-1][w - w_i] + v_i)\n"
        f"    return dp[n][W]\n"
        f"```\n\n"
        f"Step 3 - Apply to items={items_str}, W={inst.W}:\n"
        f"Final row dp[{inst.n}] = {last_row}\n"
        f"dp[{inst.n}][{inst.W}] = {answer}\n"
        f"\\boxed{{{answer}}}"
    )


CODE_RENDERERS = {
    "max_subarray": _render_code_max_subarray,
    "lis": _render_code_lis,
    "knapsack_01": _render_code_knapsack,
}


# ============================================================================
# Few-shot prefix construction
# ============================================================================

def _example_lengths(task_name):
    if task_name in ("max_subarray", "lis"):
        return [3, 4, 5]
    return [2, 3, 4]


def build_few_shot_prefix(task, condition, k=3, seed=0):
    rng = random.Random(seed)
    renderer = CODE_RENDERERS[task.name] if condition == "code" else COT_RENDERERS[task.name]
    lengths = _example_lengths(task.name)
    blocks = []
    for i in range(k):
        n = lengths[i % len(lengths)]
        inst = task.generate(n, rng)
        answer, dp_trace = task.solve(inst)
        problem = PROBLEM_RENDERERS[task.name](inst, condition=condition)
        solution = renderer(inst, dp_trace, answer)
        blocks.append(f"Problem:\n{problem}\n\nSolution:\n{solution}")
    return "\n\n---\n\n".join(blocks)


def build_prompt(task, instance, condition, k=3, seed=0):
    prefix = build_few_shot_prefix(task, condition, k=k, seed=seed)
    return (
        f"{prefix}\n\n---\n\n"
        f"Problem:\n{PROBLEM_RENDERERS[task.name](instance, condition=condition)}\n\n"
        f"Solution:\n"
    )


# ============================================================================
# Length ranges
# ============================================================================

TRAIN_LENGTHS = {
    "max_subarray": list(range(5, 21)),
    "lis": list(range(5, 21)),
    "knapsack_01": list(range(4, 13)),
}

WARMUP_LENGTHS = {
    "max_subarray": [3, 4, 5],
    "lis": [3, 4, 5],
    "knapsack_01": [2, 3, 4],
}

# IID eval: same range as training
EVAL_IID_LENGTHS = {
    "max_subarray": [5, 10, 15, 20],
    "lis": [5, 10, 15, 20],
    "knapsack_01": [4, 6, 8, 10, 12],
}

# Easy-to-hard OOD: train on small n, eval on larger n (length generalization)
EVAL_EASY_TO_HARD_LENGTHS = {
    "max_subarray": [30, 50, 100, 200],
    "lis": [30, 50, 80, 100],
    "knapsack_01": [16, 20, 25, 30],
}

# Hard-to-easy OOD: eval on shorter than training range
EVAL_HARD_TO_EASY_LENGTHS = {
    "max_subarray": [2, 3, 4],
    "lis": [2, 3, 4],
    "knapsack_01": [1, 2, 3],
}

# Combined for backward compat
EVAL_LENGTHS = {
    task: sorted(set(
        EVAL_IID_LENGTHS[task]
        + EVAL_EASY_TO_HARD_LENGTHS[task]
        + EVAL_HARD_TO_EASY_LENGTHS[task]
    ))
    for task in TRAIN_LENGTHS
}


# ============================================================================
# Dataset generation
# ============================================================================

def generate_instances(task, lengths, n_per_length, seed):
    rng = random.Random(seed)
    instances = []
    for n in lengths:
        for _ in range(n_per_length):
            inst = task.generate(n, rng)
            answer, _ = task.solve(inst)
            instances.append((inst, n, answer))
    return instances


DATA_SOURCE_MAP = {
    "train": "dp_lengthgen",
    "test": "dp_lengthgen",
    "eval_iid": "lengthgen_iid",
    "eval_easy_to_hard": "lengthgen_e2h",
    "eval_hard_to_easy": "lengthgen_h2e",
}


def make_dataset(task, condition, split, instances, few_shot_k=3):
    data_source = DATA_SOURCE_MAP.get(split, f"lengthgen_{split}")
    rows = []
    for idx, (inst, n, answer) in enumerate(instances):
        prompt_text = build_prompt(task, inst, condition, k=few_shot_k)
        rows.append({
            "data_source": data_source,
            "prompt": [{"role": "user", "content": prompt_text}],
            "ability": "math",
            "reward_model": {"style": "rule", "ground_truth": str(answer)},
            "extra_info": {
                "task": task.name,
                "n": n,
                "condition": condition,
                "split": split,
                "index": idx,
            },
        })
    return datasets.Dataset.from_list(rows)


def _distribute_total(total, n_buckets):
    """Distribute total evenly across n_buckets, remainder goes to last."""
    per = total // n_buckets
    return [per] * (n_buckets - 1) + [total - per * (n_buckets - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=list(TASKS.keys()))
    parser.add_argument("--condition", required=True, choices=["cot", "code"])
    parser.add_argument("--output_dir", default="data/lengthgen")
    parser.add_argument("--n_train_total", type=int, default=50000,
                        help="Total training instances (distributed across lengths)")
    parser.add_argument("--warmup_fraction", type=float, default=0.1,
                        help="Fraction of training data for warmup lengths")
    parser.add_argument("--n_eval_total", type=int, default=500,
                        help="Total eval instances per split")
    parser.add_argument("--few_shot_k", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    task = TASKS[args.task]
    out_dir = os.path.join(args.output_dir, f"{args.task}_{args.condition}")
    os.makedirs(out_dir, exist_ok=True)

    warmup_lengths = WARMUP_LENGTHS[args.task]
    train_lengths = TRAIN_LENGTHS[args.task]

    # Split training budget: warmup_fraction for warmup, rest for main
    n_warmup_total = int(args.n_train_total * args.warmup_fraction)
    n_main_total = args.n_train_total - n_warmup_total
    warmup_per_len = _distribute_total(n_warmup_total, len(warmup_lengths))
    main_per_len = _distribute_total(n_main_total, len(train_lengths))

    warmup_instances = []
    for length, count in zip(warmup_lengths, warmup_per_len):
        warmup_instances += generate_instances(task, [length], count, seed=args.seed)
    main_instances = []
    for length, count in zip(train_lengths, main_per_len):
        main_instances += generate_instances(task, [length], count, seed=args.seed + 1)

    train_instances = warmup_instances + main_instances
    train_ds = make_dataset(task, args.condition, "train", train_instances,
                            few_shot_k=args.few_shot_k)
    train_ds.to_parquet(os.path.join(out_dir, "train.parquet"))

    # Generate eval splits — n_eval_total per split, distributed across lengths
    eval_splits = {
        "eval_iid": EVAL_IID_LENGTHS[args.task],
        "eval_easy_to_hard": EVAL_EASY_TO_HARD_LENGTHS[args.task],
        "eval_hard_to_easy": EVAL_HARD_TO_EASY_LENGTHS[args.task],
    }
    for split_name, lengths in eval_splits.items():
        per_len = _distribute_total(args.n_eval_total, len(lengths))
        instances = []
        for length, count in zip(lengths, per_len):
            instances += generate_instances(task, [length], count,
                                            seed=args.seed + 100 + hash(split_name) % 1000)
        ds = make_dataset(task, args.condition, split_name, instances,
                          few_shot_k=args.few_shot_k)
        ds.to_parquet(os.path.join(out_dir, f"{split_name}.parquet"))

    # Small IID test.parquet for verl validation during training
    iid_lengths = EVAL_IID_LENGTHS[args.task]
    n_val = min(200, args.n_eval_total)
    val_per_len = _distribute_total(n_val, len(iid_lengths))
    val_instances = []
    for length, count in zip(iid_lengths, val_per_len):
        val_instances += generate_instances(task, [length], count, seed=args.seed + 200)
    val_ds = make_dataset(task, args.condition, "test", val_instances,
                          few_shot_k=args.few_shot_k)
    val_ds.to_parquet(os.path.join(out_dir, "test.parquet"))

    print(f"Task:      {args.task}")
    print(f"Condition: {args.condition}")
    print(f"Output:    {out_dir}")
    print(f"Train:     {len(train_ds):,} instances -> train.parquet")
    print(f"  Warmup:  {len(warmup_instances):,} ({warmup_lengths})")
    print(f"  Main:    {len(main_instances):,} ({train_lengths})")
    print(f"Eval splits:")
    for split_name, lengths in eval_splits.items():
        path = os.path.join(out_dir, f"{split_name}.parquet")
        n = sum(_distribute_total(args.n_eval_total, len(lengths)))
        print(f"  {split_name:20s}: {n:5d} instances, lengths {lengths}")
    print(f"  {'test (verl val)':20s}: {len(val_ds):5d} instances")

    # Print a sample prompt for inspection
    sample = train_ds[len(warmup_instances)]  # first main-training instance
    print(f"\n--- Sample prompt (first main-training, n={sample['extra_info']['n']}) ---")
    print(sample["prompt"][0]["content"][:2000])
    print("...")


if __name__ == "__main__":
    main()
