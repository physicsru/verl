"""Generate parquet datasets for the CODE-EXECUTION ablation.

BRAND-NEW, standalone generator. It imports the existing renderers/tasks/length
configs from generate_data.py as a READ-ONLY library and does not modify them.

The prompt shown to the model is IDENTICAL to the existing "code" condition
(abstract -> Python function -> apply). The only additions are:
  * extra_info["condition"] = "code_exec"
  * extra_info["call_args"]  = JSON list of positional args to call the model's
    function with at scoring time (executed by reward_fn_codeexec.py):
        max_subarray / lis : [arr]
        knapsack_01        : [items, W]

Usage:
    python examples/lengthgen_trainer/generate_data_codeexec.py \
        --task lis --output_dir data/lengthgen

Produces:
    data/lengthgen/lis_code_exec/{train,test,eval_iid,eval_easy_to_hard,eval_hard_to_easy}.parquet
"""

import argparse
import json
import os
import sys

import datasets

# Import the existing pipeline as a read-only library (no modification).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_data as gd  # noqa: E402

CONDITION = "code_exec"
# code_exec reuses the EXACT "code" prompt/renderer, so the model writes the
# same function; only the answer source (execution vs \boxed) changes.
PROMPT_CONDITION = "code"


def _call_args(task_name, inst):
    """Positional args to call the model's solver with, as a JSON string."""
    if task_name == "knapsack_01":
        items = [[int(w), int(v)] for (w, v) in inst.items]
        return json.dumps([items, int(inst.W)])
    # max_subarray, lis: solver takes the array
    return json.dumps([[int(x) for x in inst.arr]])


def make_dataset(task, split, instances, few_shot_k=3):
    data_source = gd.DATA_SOURCE_MAP.get(split, f"lengthgen_{split}")
    rows = []
    for idx, (inst, n, answer) in enumerate(instances):
        prompt_text = gd.build_prompt(task, inst, PROMPT_CONDITION, k=few_shot_k)
        rows.append({
            "data_source": data_source,
            "prompt": [{"role": "user", "content": prompt_text}],
            "ability": "math",
            "reward_model": {"style": "rule", "ground_truth": str(answer)},
            "extra_info": {
                "task": task.name,
                "n": n,
                "condition": CONDITION,
                "split": split,
                "index": idx,
                "call_args": _call_args(task.name, inst),
            },
        })
    return datasets.Dataset.from_list(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=list(gd.TASKS.keys()))
    parser.add_argument("--output_dir", default="data/lengthgen")
    parser.add_argument("--n_train_total", type=int, default=50000)
    parser.add_argument("--warmup_fraction", type=float, default=0.1)
    parser.add_argument("--n_eval_total", type=int, default=500)
    parser.add_argument("--few_shot_k", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    task = gd.TASKS[args.task]
    out_dir = os.path.join(args.output_dir, f"{args.task}_{CONDITION}")
    os.makedirs(out_dir, exist_ok=True)

    warmup_lengths = gd.WARMUP_LENGTHS[args.task]
    train_lengths = gd.TRAIN_LENGTHS[args.task]

    n_warmup_total = int(args.n_train_total * args.warmup_fraction)
    n_main_total = args.n_train_total - n_warmup_total
    warmup_per_len = gd._distribute_total(n_warmup_total, len(warmup_lengths))
    main_per_len = gd._distribute_total(n_main_total, len(train_lengths))

    warmup_instances = []
    for length, count in zip(warmup_lengths, warmup_per_len):
        warmup_instances += gd.generate_instances(task, [length], count, seed=args.seed)
    main_instances = []
    for length, count in zip(train_lengths, main_per_len):
        main_instances += gd.generate_instances(task, [length], count, seed=args.seed + 1)

    train_instances = warmup_instances + main_instances
    train_ds = make_dataset(task, "train", train_instances, few_shot_k=args.few_shot_k)
    train_ds.to_parquet(os.path.join(out_dir, "train.parquet"))

    # Deterministic per-split seeds (no hash() so runs are reproducible).
    eval_splits = {
        "eval_iid": (gd.EVAL_IID_LENGTHS[args.task], args.seed + 100),
        "eval_easy_to_hard": (gd.EVAL_EASY_TO_HARD_LENGTHS[args.task], args.seed + 200),
        "eval_hard_to_easy": (gd.EVAL_HARD_TO_EASY_LENGTHS[args.task], args.seed + 300),
    }
    for split_name, (lengths, seed) in eval_splits.items():
        per_len = gd._distribute_total(args.n_eval_total, len(lengths))
        instances = []
        for length, count in zip(lengths, per_len):
            instances += gd.generate_instances(task, [length], count, seed=seed)
        ds = make_dataset(task, split_name, instances, few_shot_k=args.few_shot_k)
        ds.to_parquet(os.path.join(out_dir, f"{split_name}.parquet"))

    # Small IID test.parquet for verl validation during training.
    iid_lengths = gd.EVAL_IID_LENGTHS[args.task]
    n_val = min(200, args.n_eval_total)
    val_per_len = gd._distribute_total(n_val, len(iid_lengths))
    val_instances = []
    for length, count in zip(iid_lengths, val_per_len):
        val_instances += gd.generate_instances(task, [length], count, seed=args.seed + 400)
    val_ds = make_dataset(task, "test", val_instances, few_shot_k=args.few_shot_k)
    val_ds.to_parquet(os.path.join(out_dir, "test.parquet"))

    print(f"Task:      {args.task}")
    print(f"Condition: {CONDITION} (prompt identical to 'code'; answer from code execution)")
    print(f"Output:    {out_dir}")
    print(f"Train:     {len(train_ds):,} instances -> train.parquet")
    print(f"  Warmup:  {len(warmup_instances):,} ({warmup_lengths})")
    print(f"  Main:    {len(main_instances):,} ({train_lengths})")
    print("Eval splits:")
    for split_name, (lengths, _seed) in eval_splits.items():
        n = sum(gd._distribute_total(args.n_eval_total, len(lengths)))
        print(f"  {split_name:20s}: {n:5d} instances, lengths {lengths}")
    print(f"  {'test (verl val)':20s}: {len(val_ds):5d} instances")

    sample = train_ds[len(warmup_instances)]
    print(f"\n--- Sample (first main-training, n={sample['extra_info']['n']}) ---")
    print("call_args:", sample["extra_info"]["call_args"][:120])
    print(sample["prompt"][0]["content"][-600:])


if __name__ == "__main__":
    main()
