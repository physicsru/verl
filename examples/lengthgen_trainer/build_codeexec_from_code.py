"""Build the CODE-EXECUTION ablation datasets from the EXISTING `*_code` data.

For a clean ablation, code_exec must train/eval on the *identical* instances and
prompts as the `code` condition. This script copies each row of
`data/lengthgen/{task}_code/*.parquet` verbatim and only:
  * sets extra_info["condition"] = "code_exec"
  * adds extra_info["call_args"] = JSON positional args for the model's solver,
    recovered by parsing the actual problem input out of the prompt.

Every row is validated: we reconstruct the instance from the parsed input, solve
it with the canonical task solver, and assert the result equals the stored
ground_truth. Any mismatch aborts (means the parse was wrong).

Usage:
    python examples/lengthgen_trainer/build_codeexec_from_code.py --task lis
    python examples/lengthgen_trainer/build_codeexec_from_code.py --task knapsack_01
    python examples/lengthgen_trainer/build_codeexec_from_code.py --task max_subarray

Output: data/lengthgen/{task}_code_exec/*.parquet  (same file set as *_code)
"""

import argparse
import ast
import json
import os
import re
import sys

import datasets

# Import the canonical tasks for validation (read-only).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_data as gd  # noqa: E402
from tasks import MaxSubarrayInstance, LISInstance, KnapsackInstance  # noqa: E402

SPLITS = ["train", "test", "eval_iid", "eval_easy_to_hard", "eval_hard_to_easy"]

_ARR_RE = re.compile(r"Given the (?:array|sequence)\s*(\[[^\]]*\])")
_KNAP_ITEMS_RE = re.compile(r"Items \(weight, value\):\s*(\[[^\]]*\])")
_KNAP_W_RE = re.compile(r"capacity W\s*=\s*(\d+)")


def _last_problem(prompt_content: str) -> str:
    """Return the tail of the prompt containing the ACTUAL problem (the last
    'Problem:' block), so we don't parse a few-shot example by mistake."""
    return prompt_content.rsplit("Problem:", 1)[-1]


def parse_and_validate(task_name, prompt_content, ground_truth):
    """Return (call_args_json, solved_answer). Raises on parse/solve mismatch."""
    tail = _last_problem(prompt_content)
    if task_name in ("lis", "max_subarray"):
        m = _ARR_RE.search(tail)
        if not m:
            raise ValueError(f"{task_name}: could not find input array in prompt tail")
        arr = [int(x) for x in ast.literal_eval(m.group(1))]
        call_args = [arr]
        inst = (LISInstance(arr=arr) if task_name == "lis"
                else MaxSubarrayInstance(arr=arr))
        answer, _ = (gd.TASKS[task_name]).solve(inst)
    elif task_name == "knapsack_01":
        mi = _KNAP_ITEMS_RE.search(tail)
        mw = _KNAP_W_RE.search(tail)
        if not (mi and mw):
            raise ValueError("knapsack_01: could not find items/W in prompt tail")
        items = [[int(w), int(v)] for (w, v) in ast.literal_eval(mi.group(1))]
        W = int(mw.group(1))
        call_args = [items, W]
        inst = KnapsackInstance(items=[tuple(it) for it in items], W=W)
        answer, _ = gd.TASKS["knapsack_01"].solve(inst)
    else:
        raise ValueError(f"unknown task {task_name}")

    if str(answer) != str(ground_truth):
        raise AssertionError(
            f"{task_name}: parsed input solves to {answer} but stored gt={ground_truth}; "
            f"prompt tail head={tail[:160]!r}")
    return json.dumps(call_args), answer


def rebuild_split(task_name, code_dir, out_dir, split):
    src = os.path.join(code_dir, f"{task_name}_code", f"{split}.parquet")
    if not os.path.isfile(src):
        print(f"  [skip] {split}: {src} not found")
        return None
    ds = datasets.Dataset.from_parquet(src)
    rows = []
    for row in ds:
        prompt_content = row["prompt"][0]["content"]
        gt = row["reward_model"]["ground_truth"]
        # Use the per-row task (constant for single-task files; varies for the
        # combined all_tasks file).
        row_task = row["extra_info"]["task"]
        call_args_json, _ = parse_and_validate(row_task, prompt_content, gt)
        ei = dict(row["extra_info"])
        ei["condition"] = "code_exec"
        ei["call_args"] = call_args_json
        rows.append({
            "data_source": row["data_source"],
            "prompt": row["prompt"],
            "ability": row["ability"],
            "reward_model": row["reward_model"],
            "extra_info": ei,
        })
    out_ds = datasets.Dataset.from_list(rows)
    os.makedirs(os.path.join(out_dir, f"{task_name}_code_exec"), exist_ok=True)
    out_path = os.path.join(out_dir, f"{task_name}_code_exec", f"{split}.parquet")
    out_ds.to_parquet(out_path)
    print(f"  [ok]   {split:18s}: {len(rows):6d} rows validated -> {out_path}")
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True,
                        choices=["lis", "knapsack_01", "max_subarray", "all_tasks"])
    parser.add_argument("--code_dir", default="data/lengthgen",
                        help="dir containing {task}_code/*.parquet")
    parser.add_argument("--out_dir", default="data/lengthgen")
    args = parser.parse_args()

    print(f"Rebuilding code_exec from code for task={args.task}")
    total = 0
    for split in SPLITS:
        n = rebuild_split(args.task, args.code_dir, args.out_dir, split)
        total += n or 0
    print(f"Done: {total} rows total, all validated against ground truth.")


if __name__ == "__main__":
    main()
