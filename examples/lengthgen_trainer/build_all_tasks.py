"""Concatenate the per-task `{task}_{condition}` datasets into `all_tasks_{condition}`.

The combined multi-task dataset is just the union of the three per-task DP files
(lis, knapsack_01, max_subarray) for a single condition, with the TRAIN split
deterministically shuffled so tasks are interleaved batch-to-batch (matches the
original all_tasks layout). Eval splits are concatenated in task order (order is
irrelevant for validation metrics).

Run AFTER generate_data.py has produced the per-task `{task}_{condition}` dirs.
For the code_exec condition use build_codeexec_from_code.py --task all_tasks
instead (it reads all_tasks_code and attaches call_args), so this script only
handles the cot / code conditions.

Usage:
    python examples/lengthgen_trainer/build_all_tasks.py --condition code
    python examples/lengthgen_trainer/build_all_tasks.py --condition cot
"""

import argparse
import os

import datasets

TASKS = ["lis", "knapsack_01", "max_subarray"]
SPLITS = ["train", "test", "eval_iid", "eval_easy_to_hard", "eval_hard_to_easy"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", required=True, choices=["cot", "code"])
    parser.add_argument("--data_dir", default="data/lengthgen")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_dir = os.path.join(args.data_dir, f"all_tasks_{args.condition}")
    os.makedirs(out_dir, exist_ok=True)
    print(f"Building all_tasks_{args.condition} -> {out_dir}")

    for split in SPLITS:
        parts = []
        for task in TASKS:
            path = os.path.join(args.data_dir, f"{task}_{args.condition}", f"{split}.parquet")
            if not os.path.isfile(path):
                print(f"  [skip] {split}: missing {path}")
                continue
            parts.append(datasets.Dataset.from_parquet(path))
        if not parts:
            print(f"  [skip] {split}: no source files found")
            continue
        ds = datasets.concatenate_datasets(parts)
        if split == "train":
            ds = ds.shuffle(seed=args.seed)
        out_path = os.path.join(out_dir, f"{split}.parquet")
        ds.to_parquet(out_path)
        print(f"  [ok]   {split:20s} {len(ds):7d} rows -> {out_path}")


if __name__ == "__main__":
    main()
