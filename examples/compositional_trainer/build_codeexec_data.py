"""Derive ONE-SHOT CODE-EXEC datasets from existing baseline parquets.

Rewrites only the PROMPT (from the ground truth already stored in each row:
ref_code + ref_input.x); programs, inputs and ref_outputs stay byte-identical
to the CoT baseline, so the two conditions differ ONLY in prompt + reward.
Scored by reward_fn_codeexec.py: the model plans in text, then commits to ONE
self-contained Python program; the grader executes it exactly once and takes
`main_solution(x)`'s return value as the answer. In Stage 2 the func_N bodies
are hidden, so the program must re-implement them from Stage-1 knowledge —
an explicit, executable compositional function.

Usage
-----
# Convert every known baseline dir of a pool (train+test where present):
python examples/compositional_trainer/build_codeexec_data.py --pool paper
python examples/compositional_trainer/build_codeexec_data.py --pool lenpres

# Or a single explicit file:
python examples/compositional_trainer/build_codeexec_data.py \
    --in data/compositional/paper/stage2_level1to2/train.parquet \
    --out data/compositional/paper/stage2_level1to2_codeexec/train.parquet

Outputs land next to the source dir with a ``_codeexec`` suffix. Stage-1 rows
(bodies shown) are additionally validated end-to-end: the shown code itself,
wrapped as a model response, must score 1.0 under reward_fn_codeexec.
"""

import argparse
import json
import os
import sys

import pandas as pd
from datasets import Dataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reward_fn_codeexec import compute_score  # noqa: E402

# Baseline dirs eligible for conversion (rollout/SFT intermediates excluded).
KNOWN_DIRS = [
    "stage1_level1",
    "stage2_level1to2",
    "stage2_level1to8",
    "eval_iid",
    "eval_easy",
    "eval_medium",
    "eval_hard",
]

_BODIES_SHOWN = "Every function used is fully defined above, so you can rely on those exact definitions."
_BODIES_HIDDEN = (
    "The definitions of the helper functions are hidden here, but you know all of "
    "them from prior training: recall exactly what each one does and re-implement it faithfully."
)

CODEEXEC_PROMPT = (
    "You are given a code:\n\n{code}\n\n"
    "Your task is to determine the output of `main_solution(\"{input}\")`. {bodies}\n\n"
    "You may use Python, under one rule: your program will be executed exactly ONCE, "
    "and you will never see its output — whatever `main_solution(\"{input}\")` returns "
    "in your program is submitted directly as your final answer. There is no second "
    "attempt and no way to test or debug, so plan carefully before you write any code.\n\n"
    "Step 1 - Plan: in plain text, state what each function used by `main_solution` "
    "does and how you will implement it.\n"
    "Step 2 - Program: write ONE complete, self-contained Python program in a single "
    "```python code block, including any imports it needs. It must define `main_solution` "
    "(same behavior as the given code) together with every helper function it needs. The "
    "grader runs this block once and calls `main_solution(\"{input}\")`."
)


def convert_row(row):
    gt_str = row["reward_model"]["ground_truth"]
    gt = json.loads(gt_str)
    ei = dict(row["extra_info"]) if row["extra_info"] is not None else {}
    stage = int(ei.get("stage", 2))
    x = gt["ref_input"]["x"]
    prompt = CODEEXEC_PROMPT.format(
        code=gt["ref_code"], input=x,
        bodies=_BODIES_SHOWN if stage == 1 else _BODIES_HIDDEN,
    )
    # numpy scalars from parquet -> plain python types
    new_ei = {k: (v.item() if hasattr(v, "item") else v) for k, v in ei.items()}
    new_ei["condition"] = "code_exec"
    return {
        "data_source": str(row["data_source"]).replace("compositional-forward", "compositional-codeexec"),
        "prompt": [{"role": "user", "content": prompt}],
        "ability": "reasoning",
        "reward_model": {"style": "rule", "ground_truth": gt_str},
        "extra_info": new_ei,
    }


def validate_stage1(rows, n):
    """Bodies-shown rows: the given code itself must score 1.0 when executed."""
    checked = 0
    for r in rows:
        if int(r["extra_info"].get("stage", 2)) != 1 or checked >= n:
            continue
        gt = json.loads(r["reward_model"]["ground_truth"])
        # The shown code assumes operators.py's module context (deterministic_shuffle
        # uses `gcd`); a CORRECT model answer must add that import itself — the prompt
        # demands a self-contained program — so the simulated answer does too.
        fake_response = ("Step 1 - Plan: all definitions are shown; I will reproduce them verbatim "
                         "and add the imports they rely on.\n"
                         f"Step 2 - Program:\n```python\nfrom math import gcd\n\n{gt['ref_code']}\n```\n")
        res = compute_score(r["data_source"], fake_response, r["reward_model"]["ground_truth"],
                            {**r["extra_info"], "split": "train"})
        assert res["correctness"] == 1.0, (
            f"stage-1 self-validation failed (exec of shown code != ref_output):\n{gt['ref_code']}")
        checked += 1
    return checked


def convert_file(in_path, out_path, n_validate):
    df = pd.read_parquet(in_path)
    rows = [convert_row(r) for _, r in df.iterrows()]
    n_checked = validate_stage1(rows, n_validate)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    Dataset.from_list(rows).to_parquet(out_path)
    tag = f", validated {n_checked} stage-1 rows by execution" if n_checked else ""
    print(f"[codeexec] {in_path} -> {out_path} ({len(rows)} rows{tag})")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", choices=["paper", "lenpres"], help="convert all known baseline dirs of this pool")
    ap.add_argument("--data_root", default="data/compositional")
    ap.add_argument("--in", dest="in_path", help="single input parquet (alternative to --pool)")
    ap.add_argument("--out", dest="out_path", help="output parquet for --in")
    ap.add_argument("--validate", type=int, default=8,
                    help="per file: execute the shown code of up to N stage-1 rows and require score 1.0")
    args = ap.parse_args()

    if args.in_path:
        if not args.out_path:
            ap.error("--out is required with --in")
        rows = convert_file(args.in_path, args.out_path, args.validate)
    elif args.pool:
        rows = None
        for d in KNOWN_DIRS:
            src_dir = os.path.join(args.data_root, args.pool, d)
            for split_file in ("train.parquet", "test.parquet"):
                src = os.path.join(src_dir, split_file)
                if not os.path.exists(src):
                    continue
                dst = os.path.join(src_dir + "_codeexec", split_file)
                rows = convert_file(src, dst, args.validate)
    else:
        ap.error("pass --pool or --in/--out")

    if rows:
        print("\n--- sample prompt ---")
        print(rows[len(rows) // 2]["prompt"][0]["content"][:1500])


if __name__ == "__main__":
    main()
