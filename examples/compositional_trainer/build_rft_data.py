"""RFT step 2/2: filter rollouts for correctness -> SFT (messages) parquet.

Mirrors the paper's procedure (and the original ``string_manipulation_sft.py``):
keep only the model's CORRECT trajectories, optionally drop problems that were
already fully solved (no learning signal), cap the number kept per problem, then
write a `messages`-format dataset the SFT primitive (_sft_launch.sh) consumes.

Scoring reuses this pipeline's own reward (reward_fn.compute_score), so "correct"
means exactly what training/eval mean.

Usage:
    python build_rft_data.py \
        --rollout_path data/compositional/paper/stage1_rft/iter1/rollout.parquet \
        --out_dir      data/compositional/paper/stage1_rft/iter1/sft_data \
        --val_size 256 --max_keep_per_problem 4
"""

import argparse
import glob
import importlib
import json
import os
import random
import sys

import pandas as pd
from datasets import Dataset

# The correctness filter reuses one of this pipeline's rewards (--reward_module):
# reward_fn (CoT forward, default) or reward_fn_codeexec (one-shot code exec).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _iter_rollout_files(path):
    if os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "*.parquet")))
    return [path]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollout_path", required=True, help="rollout parquet file or dir")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--val_size", type=int, default=256)
    ap.add_argument("--max_keep_per_problem", type=int, default=4)
    ap.add_argument("--drop_if_all_correct", action="store_true",
                    help="skip problems where every sample is correct (already mastered)")
    ap.add_argument("--max_chars", type=int, default=6000,
                    help="drop a kept trace if longer than this (avoid SFT overlong)")
    ap.add_argument("--reward_module", default="reward_fn",
                    help="module in this dir providing compute_score "
                         "(reward_fn | reward_fn_codeexec)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    compute_score = importlib.import_module(args.reward_module).compute_score

    rng = random.Random(args.seed)
    rows = []
    n_problems = n_with_correct = n_traces = 0
    correct_counts = []

    for f in _iter_rollout_files(args.rollout_path):
        df = pd.read_parquet(f)
        for _, r in df.iterrows():
            n_problems += 1
            gt = r["reward_model"]["ground_truth"]
            ei = dict(r["extra_info"]) if r["extra_info"] is not None else {}
            ds = r.get("data_source", "compositional-forward")
            prompt = r["prompt"]
            responses = list(r["responses"])

            correct = []
            for resp in responses:
                try:
                    res = compute_score(ds, resp, gt, ei)
                    ok = (res.get("correctness", 0.0) == 1.0) if isinstance(res, dict) else (res == 1.0)
                except Exception:
                    ok = False
                if ok and len(resp) <= args.max_chars:
                    correct.append(resp)
            correct_counts.append(len(correct))
            if not correct:
                continue
            if args.drop_if_all_correct and len(correct) == len(responses):
                continue
            n_with_correct += 1

            rng.shuffle(correct)
            for resp in correct[: args.max_keep_per_problem]:
                n_traces += 1
                rows.append({
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": resp},
                    ],
                    "extra_info": ei,
                })

    rng.shuffle(rows)
    os.makedirs(args.out_dir, exist_ok=True)
    val = rows[: args.val_size] if args.val_size > 0 else []
    train = rows[args.val_size:] if args.val_size > 0 else rows
    Dataset.from_list(train).to_parquet(os.path.join(args.out_dir, "train.parquet"))
    if val:
        Dataset.from_list(val).to_parquet(os.path.join(args.out_dir, "test.parquet"))

    avg_correct = sum(correct_counts) / max(1, len(correct_counts))
    print(f"[rft] problems={n_problems} with>=1 correct={n_with_correct} "
          f"(avg correct/problem={avg_correct:.2f}) -> traces={n_traces} "
          f"(train={len(train)}, val={len(val)}) @ {args.out_dir}")
    if n_with_correct == 0:
        print("[rft][WARN] no correct trajectories — model too weak / prompt mismatch. "
              "Bootstrap with build_sft_data.py (synthetic) or lower difficulty.")


if __name__ == "__main__":
    main()
