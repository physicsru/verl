# Copyright 2026 verl contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
"""Preprocess DeepScaleR-Preview-Dataset into verl's RL-parquet schema.

DeepScaleR ships a single train split (~40K competition math problems). We
materialize ``train.parquet`` from rows [0, N-holdout) and ``test.parquet`` from
the last ``--holdout`` rows so the example launch scripts have something
in-distribution to validate against. Swap in MATH-500 / AIME24 / GPQA at
training time by pointing TEST_FILE elsewhere.

Usage:
    python examples/data_preprocess/deepscaler.py \
        --local_save_dir /work/go39/b20033/code/generalization/verl/data/deepscaler \
        --holdout 500
"""

import argparse
import json
import os

import datasets


INSTRUCTION = "Let's think step by step and output the final answer within \\boxed{}."


def make_map_fn(split: str):
    def process_fn(example, idx):
        question = example.pop("problem")
        answer = example.pop("answer")
        example.pop("solution", None)  # drop the worked solution — RLVR uses only the answer
        return {
            "data_source": "agentica-org/DeepScaleR-Preview-Dataset",
            "prompt": [{"role": "user", "content": question + " " + INSTRUCTION}],
            "ability": "math",
            "reward_model": {"style": "rule", "ground_truth": answer},
            "extra_info": {"split": split, "index": idx},
        }

    return process_fn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--local_save_dir",
        default="/work/go39/b20033/code/generalization/verl/data/deepscaler",
        help="Destination directory for train.parquet / test.parquet.",
    )
    parser.add_argument(
        "--holdout",
        type=int,
        default=500,
        help="Number of trailing rows reserved as the held-out test split.",
    )
    parser.add_argument(
        "--data_source",
        default="agentica-org/DeepScaleR-Preview-Dataset",
        help="HuggingFace dataset id.",
    )
    args = parser.parse_args()

    print(f"Loading {args.data_source} from huggingface...", flush=True)
    raw = datasets.load_dataset(args.data_source, split="train")
    n_total = len(raw)
    holdout = max(0, min(args.holdout, n_total - 1))
    n_train = n_total - holdout
    print(f"  total={n_total}  train={n_train}  test(holdout)={holdout}", flush=True)

    train_raw = raw.select(range(n_train))
    test_raw = raw.select(range(n_train, n_total))

    train_ds = train_raw.map(make_map_fn("train"), with_indices=True, remove_columns=train_raw.column_names)
    test_ds = test_raw.map(make_map_fn("test"), with_indices=True, remove_columns=test_raw.column_names)

    out_dir = os.path.expanduser(args.local_save_dir)
    os.makedirs(out_dir, exist_ok=True)

    train_path = os.path.join(out_dir, "train.parquet")
    test_path = os.path.join(out_dir, "test.parquet")
    train_ds.to_parquet(train_path)
    test_ds.to_parquet(test_path)
    print(f"wrote {train_path} ({len(train_ds)} rows)")
    print(f"wrote {test_path} ({len(test_ds)} rows)")

    # Save one example per split as JSON so the schema is grep-able.
    with open(os.path.join(out_dir, "train_example.json"), "w") as f:
        json.dump(train_ds[0], f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, "test_example.json"), "w") as f:
        json.dump(test_ds[0], f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
