"""Recall-then-assemble RFT step 0: build ELICITATION prompts.

The interference finding (WALKTHROUGH §11-12): atomic closed-book recall of
every held-out op is perfect (x_i = 1.0), yet writing k defs in one program
degrades per-op reliability to ~0.4-0.6 — the model's multi-def emission is
entangled with the practiced op set. This pipeline teaches an op-agnostic
FORMAT that reduces a composition to sequential isolated atomic recalls:

    Recall func_A: <one sentence>          <- one recall episode per op,
    ```python                                 mirroring the (perfect) depth-1
    def func_A(...): ...                      recall shape
    ```
    ... (one block per distinct func) ...
    Assemble:
    ```python
    <all defs again + main_solution verbatim>   <- LAST block = the program the
    ```                                            grader executes (compatible
                                                   with reward_fn_codeexec)

This script takes existing stage-2 codeexec TRAIN rows (train ops only,
depth >= 2), and wraps each prompt with the format instruction plus one worked
example (train-op bodies only — never a held-out op). The ORIGINAL prompt is
stashed in extra_info["orig_prompt"]; build_ra_rft_data.py strips the scaffold
so the SFT pair is (original stage-2 prompt -> model's own verified formatted
response) and the format becomes default behavior, not instruction-following.

Usage:
    python examples/compositional_trainer/build_ra_elicit_data.py \
        --in_path data/compositional/paper/stage2_level1to4_codeexec/train.parquet \
        --out_path data/compositional/paper/ra_rft/elicit.parquet \
        --min_depth 2 --max_depth 4
"""

import argparse
import inspect
import json
import re
import sys
import os

import pandas as pd
from datasets import Dataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import operators as ops_mod  # noqa: E402

_MARKER = "\n\nStep 1 - Plan:"


def renamed_source(op_name):
    """Reference body renamed to its stable func_N (self-references included)."""
    func_n = ops_mod.func_name_mapping[op_name]
    src = inspect.getsource(getattr(ops_mod, op_name))
    return re.sub(rf"\b{op_name}\b", func_n, src).strip()


def build_example():
    """One worked depth-2 example using TRAIN ops only (func_1, func_3)."""
    f1 = renamed_source("repeat_str")   # func_1, train set
    f3 = renamed_source("sort_chars")   # func_3, train set
    skeleton = "def main_solution(x):\n    return func_3(func_1(x, 2))"
    return (
        "Example.\n"
        "Code:\n"
        f"{skeleton}\n"
        'Task: determine the output of `main_solution("dbca")`.\n'
        "Answer:\n"
        "Recall func_1: repeat the string s exactly n times.\n"
        f"```python\n{f1}\n```\n"
        "Recall func_3: sort the characters in the string.\n"
        f"```python\n{f3}\n```\n"
        "Assemble:\n"
        f"```python\n{f1}\n\n{f3}\n\n{skeleton}\n```"
    )


RA_INSTRUCTIONS = (
    "Answer in the RECALL-THEN-ASSEMBLE format:\n"
    "- For EACH helper function used by `main_solution`, one at a time, write one "
    "recall episode: a line `Recall func_N: <one sentence stating exactly what it "
    "does>` followed by one ```python code block containing ONLY that function's "
    "definition. Treat each recall episode as its own isolated task; do not think "
    "about the other functions while writing it.\n"
    "- Then write `Assemble:` followed by ONE final ```python code block containing "
    "every helper definition again plus `main_solution` exactly as given, "
    "self-contained with any imports it needs. The grader executes ONLY this final "
    "block once and submits its `main_solution` return value as your answer.\n\n"
)


def per_problem_template(funcs):
    """Literal fill-in skeleton for THIS problem — one section per distinct op.

    Only op NAMES are enumerated (they already appear in the given code); no
    semantics are leaked. This is the compliance hammer: smoke 2487685 showed
    an abstract instruction + one example gets 0/800 per-op code blocks out of
    stage15b (its single-program-block habit is too strong), so the required
    structure is spelled out per problem.
    """
    parts = ["Your answer MUST follow exactly this structure, filling in the blanks:\n"]
    for fn in funcs:
        parts.append(f"Recall {fn}: <one sentence: what it does>\n"
                     f"```python\ndef {fn}(...):\n    <implementation>\n```")
    parts.append("Assemble:\n```python\n<every definition above, then main_solution "
                 "exactly as given>\n```")
    return "\n".join(parts) + "\n\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in_path", required=True)
    ap.add_argument("--out_path", required=True)
    ap.add_argument("--min_depth", type=int, default=2)
    ap.add_argument("--max_depth", type=int, default=4)
    ap.add_argument("--max_rows", type=int, default=-1, help="-1 = all (after depth filter)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    example = build_example()
    df = pd.read_parquet(args.in_path)
    rows, skipped = [], 0
    for _, r in df.iterrows():
        ei = dict(r["extra_info"]) if r["extra_info"] is not None else {}
        depth = int(ei.get("depth", -1))
        if not (args.min_depth <= depth <= args.max_depth):
            continue
        orig = r["prompt"][0]["content"] if not isinstance(r["prompt"], str) else r["prompt"]
        if _MARKER not in orig:
            skipped += 1
            continue
        head = orig.split(_MARKER)[0]
        gt = json.loads(r["reward_model"]["ground_truth"])
        funcs = sorted(set(re.findall(ops_mod.FUNC_RE_STR, gt["ref_code"])),
                       key=lambda f: gt["ref_code"].index(f))
        if not funcs:   # rare literal/.upper()-only skeletons — nothing to recall
            skipped += 1
            continue
        # Prefix-forcing: the prompt ENDS with the answer's first recall line
        # already begun, so generation starts inside the required pattern
        # (smoke 2488107: template alone -> only 4.9% full structural
        # compliance; the failure is the first line sliding back into prose).
        # build_ra_rft_data.py re-attaches seed_prefix before verifying and
        # storing, so the SFT assistant message is complete.
        seed = f"Recall {funcs[0]}:"
        elicit = (f"{example}\n\n{head}\n\n{RA_INSTRUCTIONS}"
                  f"{per_problem_template(funcs)}Answer:\n{seed}")
        ei["orig_prompt"] = orig
        ei["seed_prefix"] = seed
        ei["condition"] = "recall_assemble"
        rows.append({
            "prompt": [{"role": "user", "content": elicit}],
            "reward_model": {"ground_truth": r["reward_model"]["ground_truth"]},
            "extra_info": ei,
            "data_source": "compositional-codeexec-ra",
        })

    if args.max_rows > 0 and len(rows) > args.max_rows:
        import random
        random.Random(args.seed).shuffle(rows)
        rows = rows[: args.max_rows]

    os.makedirs(os.path.dirname(os.path.abspath(args.out_path)), exist_ok=True)
    Dataset.from_list(rows).to_parquet(args.out_path)
    print(f"[ra-elicit] wrote {len(rows)} rows (skipped {skipped} marker-less) -> {args.out_path}")


if __name__ == "__main__":
    main()
