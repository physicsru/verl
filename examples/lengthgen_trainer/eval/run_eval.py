"""Evaluate length generalization of trained checkpoints.

Runs inference on three eval splits:
  - iid:           same length range as training
  - easy_to_hard:  longer than training (length generalization)
  - hard_to_easy:  shorter than training

Usage:
    python examples/lengthgen_trainer/eval/run_eval.py \
        --model_path checkpoints/max_subarray_code/step_500 \
        --task max_subarray --condition code \
        --output_dir results/lengthgen

    # Single split:
    python examples/lengthgen_trainer/eval/run_eval.py \
        --model_path ... --task max_subarray --condition code \
        --split easy_to_hard

Requires: vllm, transformers
"""

import argparse
import json
import os
import random
import re
import sys

TASK_PKG = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "length_generalization",
))
sys.path.insert(0, os.environ.get("LENGTHGEN_TASK_PKG", TASK_PKG))

from tasks import TASKS

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from generate_data import (
    build_prompt,
    EVAL_IID_LENGTHS,
    EVAL_EASY_TO_HARD_LENGTHS,
    EVAL_HARD_TO_EASY_LENGTHS,
    TRAIN_LENGTHS,
)

BOXED_RE = re.compile(r"\\boxed\{([^}]*)\}")

SPLIT_LENGTHS = {
    "iid": EVAL_IID_LENGTHS,
    "easy_to_hard": EVAL_EASY_TO_HARD_LENGTHS,
    "hard_to_easy": EVAL_HARD_TO_EASY_LENGTHS,
}


def extract_answer(text):
    matches = BOXED_RE.findall(text)
    if not matches:
        return None
    raw = matches[-1].strip().replace(",", "").replace(" ", "")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def eval_at_lengths(llm, sampling_params, task, condition, lengths,
                    n_per_length, seed_base):
    results = []
    for n in lengths:
        rng = random.Random(seed_base + n)
        prompts = []
        ground_truths = []

        for _ in range(n_per_length):
            inst = task.generate(n, rng)
            answer, _ = task.solve(inst)
            prompt = build_prompt(task, inst, condition)
            prompts.append(prompt)
            ground_truths.append(answer)

        outputs = llm.generate(prompts, sampling_params)

        correct = 0
        for out, gt in zip(outputs, ground_truths):
            text = out.outputs[0].text
            pred = extract_answer(text)
            if pred is not None and pred == gt:
                correct += 1

        accuracy = correct / len(prompts)
        results.append({
            "task": task.name,
            "condition": condition,
            "n": n,
            "accuracy": accuracy,
            "correct": correct,
            "n_total": len(prompts),
        })
        print(f"    n={n:4d}  accuracy={accuracy:.3f}  ({correct}/{len(prompts)})")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--task", required=True, choices=list(TASKS.keys()))
    parser.add_argument("--condition", required=True, choices=["cot", "code"])
    parser.add_argument("--output_dir", default="results/lengthgen")
    parser.add_argument("--split", default="all",
                        choices=["all", "iid", "easy_to_hard", "hard_to_easy"])
    parser.add_argument("--n_per_length", type=int, default=500)
    parser.add_argument("--max_tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=999)
    parser.add_argument("--tp", type=int, default=1)
    args = parser.parse_args()

    task = TASKS[args.task]
    splits = list(SPLIT_LENGTHS.keys()) if args.split == "all" else [args.split]

    from vllm import LLM, SamplingParams

    llm = LLM(model=args.model_path, tensor_parallel_size=args.tp,
              trust_remote_code=True)
    sampling_params = SamplingParams(
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        top_p=1.0 if args.temperature == 0.0 else 0.95,
    )

    os.makedirs(args.output_dir, exist_ok=True)

    all_results = []
    for split_name in splits:
        lengths = SPLIT_LENGTHS[split_name][args.task]
        print(f"\n=== {split_name} (lengths: {lengths}) ===")
        results = eval_at_lengths(
            llm, sampling_params, task, args.condition, lengths,
            args.n_per_length, seed_base=args.seed + hash(split_name) % 1000,
        )
        for r in results:
            r["split"] = split_name
            r["model_path"] = args.model_path
        all_results.extend(results)

    out_file = os.path.join(args.output_dir, f"{args.task}_{args.condition}.jsonl")
    with open(out_file, "w") as f:
        for entry in all_results:
            f.write(json.dumps(entry) + "\n")

    # Print summary table
    train_max = max(TRAIN_LENGTHS[args.task])
    print(f"\n{'='*60}")
    print(f"Task: {args.task} | Condition: {args.condition} | Train max n: {train_max}")
    print(f"{'Split':<16} {'n':>4} {'Accuracy':>10} {'Correct':>8}")
    print(f"{'-'*60}")
    for r in all_results:
        ood = " (OOD)" if r["n"] > train_max else ""
        print(f"{r['split']:<16} {r['n']:>4} {r['accuracy']:>10.3f} "
              f"{r['correct']:>4}/{r['n_total']:<4}{ood}")
    print(f"\nResults written to {out_file}")


if __name__ == "__main__":
    main()
