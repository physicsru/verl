"""Synthesize CLOSED-BOOK CODE-EXEC SFT data (stage 1.5) — atomic recall for all 25 ops.

Why: the stage-2 code-exec run showed RL cannot install absent memories — GRPO
groups where all rollouts fail have zero advantage, so ops the model never
recalls correctly get zero gradient forever (train ops saturated ~0.5 depth-1
after 500 steps; never-trained eval ops decayed). The tool that installs
memories regardless of sampling is supervised learning. Here the prompt is the
exact stage-2 hidden-body code-exec prompt (depth-1, one hidden op) and the
target is SYNTHESIZED from operators.py: a short recall plan + one ```python
block containing the verbatim reference body (renamed to func_N) plus the
unchanged main_solution. The target never states the output string — the
grader executes — so every target is correct by construction (and verified by
execution here anyway).

Usage
-----
# 1. generate hidden-body depth-1 source pools over both op splits (CPU):
python examples/compositional_trainer/generate_data.py --pool paper --stage 2 \
    --split train --min_level 1 --max_level 1 --data_num 30000 \
    --dedup program_input --seed 20260715 --save_path <tmp>/cb_src_trainops.parquet
python examples/compositional_trainer/generate_data.py --pool paper --stage 2 \
    --split test  --min_level 1 --max_level 1 --data_num 30000 \
    --dedup program_input --seed 20260716 --save_path <tmp>/cb_src_evalops.parquet

# 2. synthesize balanced SFT data (this script):
python examples/compositional_trainer/build_closedbook_codeexec.py \
    --src <tmp>/cb_src_trainops.parquet <tmp>/cb_src_evalops.parquet \
    --out_dir data/compositional/paper/stage15_closedbook_codeexec \
    --per_op 800 --val_per_op 16 --seed 7

Stage 1.5b (multi-helper): additionally pass --comp_src with depth-2..4
TRAIN-op composition parquets (generate_data.py --stage 2 --split train
--min_level 2 --max_level 4). Each sampled composition becomes one SFT row:
one recall-plan sentence per distinct hidden helper + ONE block with every
helper body + the unchanged main_solution. This attacks the v2 failure mode
(per-mention recall corrupting to ~0.85-0.9 under multi-helper load) while
eval-op COMPOSITIONS stay held out — eval ops only ever appear alone at
depth 1, so held-out-op composition accuracy remains a valid generalization
metric.

Output is the ``messages`` format our SFT trainer expects
(``verl.trainer.sft_trainer`` + ``MultiTurnSFTDataset``), same as
build_sft_data.py / stage1_closedbook.
"""

import argparse
import inspect
import json
import os
import random
import re
import sys
from collections import defaultdict

import pandas as pd
from datasets import Dataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import operators as ops_mod  # noqa: E402
from build_codeexec_data import _BODIES_HIDDEN, CODEEXEC_PROMPT  # noqa: E402
from reward_fn_codeexec import compute_score  # noqa: E402

# func_N -> (real name, callable)
FUNC_BY_ID = {mapped: (real, ops_mod.PAPER_ALL_SET[real])
              for real, mapped in ops_mod.func_name_mapping.items()}
# func_N ids of TRAIN ops — multi-helper SFT rows must never compose eval ops.
TRAIN_FUNC_IDS = {ops_mod.func_name_mapping[real] for real in ops_mod.PAPER_TRAIN_SET}

# Recall-plan phrasing pools. The semantics sentence is the op's docstring —
# canonical, already public in stage-1 bodies-shown prompts, and it never
# contains a real op name (checked in _op_meta), so nothing leaks.
_RECALL_FRAMES = [
    "I remember `{sig}` from training: {desc}",
    "Recalling `{sig}`: {desc}",
    "From prior training, `{sig}` does the following: {desc}",
    "`{sig}` is the helper that I know as: {desc}",
]
_CLOSERS = [
    "I will re-implement {it} exactly as recalled and keep `main_solution` unchanged.",
    "I will write {that} definition faithfully and leave `main_solution` as given.",
    "My program defines {it} exactly that way, together with the unchanged `main_solution`.",
]


def _op_meta(func_id):
    real, fn = FUNC_BY_ID[func_id]
    sig = f"{func_id}{inspect.signature(fn)}"
    desc = (fn.__doc__ or "").strip().splitlines()[0]
    assert desc, f"{real} has no docstring"
    for other in ops_mod.func_name_mapping:
        assert other not in desc, f"docstring of {real} leaks op name {other}"
    return sig, desc


def _rename(code):
    for real, mapped in ops_mod.func_name_mapping.items():
        code = code.replace(real, mapped)
    return code


def _helpers_source(func_ids):
    parts = []
    for fid in sorted(func_ids, key=ops_mod.FUNC_ORDER.__getitem__):
        _, fn = FUNC_BY_ID[fid]
        parts.append(inspect.getsource(fn).rstrip())
    return _rename("\n\n\n".join(parts))


def build_target(func_ids, ref_code, rng):
    """Plan (recall each hidden op) + one code block (reference bodies + main_solution)."""
    ordered = sorted(func_ids, key=ops_mod.FUNC_ORDER.__getitem__)
    sentences = []
    for fid in ordered:
        sig, desc = _op_meta(fid)
        sentences.append(rng.choice(_RECALL_FRAMES).format(sig=sig, desc=desc))
    it, that = ("them", "each") if len(ordered) > 1 else ("it", "that")
    plan = " ".join(sentences) + " " + rng.choice(_CLOSERS).format(it=it, that=that)

    code = _helpers_source(func_ids) + "\n\n\n" + ref_code.strip()
    if ops_mod.GCD_FUNC in func_ids:  # deterministic_shuffle needs gcd
        code = "from math import gcd\n\n" + code
    return f"Step 1 - Plan: {plan}\n\nStep 2 - Program:\n```python\n{code}\n```"


def validate_inprocess(code, x, ref_output):
    env = {}
    exec(code, env)  # our own reference code — trusted
    return env["main_solution"](x) == ref_output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", nargs="+", required=True,
                    help="stage-2 depth-1 source parquets (train-op and eval-op pools)")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--per_op", type=int, default=800, help="train rows per op")
    ap.add_argument("--val_per_op", type=int, default=16, help="held-out SFT-val rows per op")
    ap.add_argument("--comp_src", nargs="*", default=[],
                    help="stage-2 depth-2..4 TRAIN-op composition parquets (stage 1.5b multi-helper rows)")
    ap.add_argument("--comp_per_depth", type=int, default=4000, help="train rows per composition depth")
    ap.add_argument("--comp_min_depth", type=int, default=2,
                    help="ignore comp-source rows shallower than this. Guard against a level-1..4 source: "
                         "the 2026-09-01 paper_alt build took 4,000 depth-1 rows from its comp source as "
                         "'comps' (RESULTS_PROVENANCE issue #7)")
    ap.add_argument("--comp_val_per_depth", type=int, default=64,
                    help="held-out SFT-val rows per composition depth")
    ap.add_argument("--validate_e2e", type=int, default=32,
                    help="additionally run N random rows through reward_fn_codeexec end-to-end")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    by_op = defaultdict(list)
    n_src = n_primitive = 0
    for src in args.src:
        df = pd.read_parquet(src)
        for _, row in df.iterrows():
            n_src += 1
            gt = json.loads(row["reward_model"]["ground_truth"])
            ids = frozenset(re.findall(ops_mod.FUNC_RE_STR, gt["ref_code"]))
            if not ids:  # primitive-only program: nothing to recall
                n_primitive += 1
                continue
            ei = dict(row["extra_info"]) if row["extra_info"] is not None else {}
            key = min(ids, key=ops_mod.FUNC_ORDER.__getitem__)
            by_op[key].append((ids, gt, str(ei.get("split", ""))))
    print(f"[closedbook-cx] {n_src} source rows -> {sum(map(len, by_op.values()))} "
          f"with >=1 hidden op ({n_primitive} primitive-only skipped), {len(by_op)} ops")

    missing = set(FUNC_BY_ID) - set(by_op)
    assert not missing, f"ops absent from source pools: {sorted(missing)} — regenerate with larger --data_num"

    rng = random.Random(args.seed)
    need = args.per_op + args.val_per_op
    train_rows, val_rows = [], []
    for fid in sorted(by_op, key=ops_mod.FUNC_ORDER.__getitem__):
        cand = by_op[fid]
        assert len(cand) >= need, (
            f"{fid}: only {len(cand)} candidates < per_op+val_per_op={need} — "
            f"regenerate source pools with larger --data_num")
        picked = rng.sample(cand, need)
        for i, (ids, gt, op_split) in enumerate(picked):
            x = gt["ref_input"]["x"]
            target = build_target(ids, gt["ref_code"], rng)
            code = target.split("```python\n", 1)[1].rsplit("```", 1)[0]
            assert validate_inprocess(code, x, gt["ref_output"]), \
                f"synthesized program wrong for {fid}: {gt['ref_code']}"
            prompt = CODEEXEC_PROMPT.format(code=gt["ref_code"], input=x, bodies=_BODIES_HIDDEN)
            row = {
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": target},
                ],
                "extra_info": {
                    "pool": "paper", "stage": 1, "depth": 1, "op": fid,
                    "op_split": op_split, "condition": "code_exec_closedbook",
                },
            }
            (val_rows if i < args.val_per_op else train_rows).append(row)

    # --- Stage 1.5b: multi-helper composition rows (train ops only) ---------
    if args.comp_src:
        by_depth = defaultdict(list)
        mention_counts = defaultdict(int)
        n_shallow = 0
        for src in args.comp_src:
            df = pd.read_parquet(src)
            for _, row in df.iterrows():
                gt = json.loads(row["reward_model"]["ground_truth"])
                ids = frozenset(re.findall(ops_mod.FUNC_RE_STR, gt["ref_code"]))
                if not ids:
                    continue
                bad = ids - TRAIN_FUNC_IDS
                assert not bad, f"eval op(s) {sorted(bad)} in comp source {src} — must be --split train"
                ei = dict(row["extra_info"]) if row["extra_info"] is not None else {}
                if int(ei["depth"]) < args.comp_min_depth:
                    n_shallow += 1
                    continue
                by_depth[int(ei["depth"])].append((ids, gt))
        print(f"[closedbook-cx] comp sources: "
              + ", ".join(f"depth {d}: {len(v)}" for d, v in sorted(by_depth.items()))
              + f" ({n_shallow} rows below --comp_min_depth={args.comp_min_depth} skipped)")

        need = args.comp_per_depth + args.comp_val_per_depth
        for depth in sorted(by_depth):
            cand = by_depth[depth]
            assert len(cand) >= need, (
                f"depth {depth}: only {len(cand)} candidates < comp_per_depth+comp_val_per_depth={need} — "
                f"regenerate comp sources with larger --data_num")
            for i, (ids, gt) in enumerate(rng.sample(cand, need)):
                x = gt["ref_input"]["x"]
                target = build_target(ids, gt["ref_code"], rng)
                code = target.split("```python\n", 1)[1].rsplit("```", 1)[0]
                assert validate_inprocess(code, x, gt["ref_output"]), \
                    f"synthesized program wrong at depth {depth}: {gt['ref_code']}"
                prompt = CODEEXEC_PROMPT.format(code=gt["ref_code"], input=x, bodies=_BODIES_HIDDEN)
                row = {
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": target},
                    ],
                    "extra_info": {
                        "pool": "paper", "stage": 1, "depth": depth,
                        "op": "+".join(sorted(ids, key=ops_mod.FUNC_ORDER.__getitem__)),
                        "op_split": "train", "condition": "code_exec_closedbook",
                    },
                }
                (val_rows if i < args.comp_val_per_depth else train_rows).append(row)
                for fid in ids:
                    mention_counts[fid] += 1
        print(f"[closedbook-cx] comp rows: {args.comp_per_depth}+{args.comp_val_per_depth} per depth; "
              f"helper coverage: " + ", ".join(f"{f}:{mention_counts[f]}" for f in
                                               sorted(mention_counts, key=ops_mod.FUNC_ORDER.__getitem__)))

    # End-to-end spot check: the synthesized response must score 1.0 under the
    # actual reward function (extraction + sandbox exec + grading).
    for row in rng.sample(train_rows, min(args.validate_e2e, len(train_rows))):
        prompt = row["messages"][0]["content"]
        m = re.search(r"You are given a code:\n\n(.*?)\n\nYour task is to determine the output "
                      r"of `main_solution\(\"(.*?)\"\)`", prompt, re.S)
        ref_code, x = m.group(1), m.group(2)
        env = {}
        exec("from math import gcd\n\n"
             + _rename("\n\n".join(inspect.getsource(fn) for fn in ops_mod.PAPER_ALL_SET.values()))
             + "\n\n" + ref_code, env)
        gt = json.dumps({"ref_input": {"x": x}, "ref_output": env["main_solution"](x),
                         "ref_code": ref_code, "funcname": "main_solution"})
        res = compute_score("compositional-codeexec-paper-depth1", row["messages"][1]["content"],
                            gt, {"split": "val"})
        assert res["correctness"] == 1.0, f"e2e validation failed:\n{ref_code}"
    print(f"[closedbook-cx] all {len(train_rows) + len(val_rows)} targets exec-validated, "
          f"{min(args.validate_e2e, len(train_rows))} rows e2e through reward_fn_codeexec")

    os.makedirs(args.out_dir, exist_ok=True)
    rng.shuffle(train_rows)
    Dataset.from_list(train_rows).to_parquet(os.path.join(args.out_dir, "train.parquet"))
    Dataset.from_list(val_rows).to_parquet(os.path.join(args.out_dir, "test.parquet"))
    print(f"[closedbook-cx] {len(train_rows)} train + {len(val_rows)} val rows -> {args.out_dir} "
          f"({len(by_op)} ops x {args.per_op}/{args.val_per_op})")

    sample = train_rows[0]
    print("\n--- sample user ---\n" + sample["messages"][0]["content"][:900])
    print("\n--- sample assistant ---\n" + sample["messages"][1]["content"][:1200])


if __name__ == "__main__":
    main()
