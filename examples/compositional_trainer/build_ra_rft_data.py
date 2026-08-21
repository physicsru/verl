"""Recall-then-assemble RFT step 2/2: verify HARD, strip scaffold, emit SFT data.

Keeps a rollout trajectory only if ALL of:
  1. the response follows the format: one `Recall func_N:` episode (with its own
     code block defining exactly that func) for EVERY distinct func in the given
     skeleton, then an `Assemble:` final block;
  2. the final block executes and main_solution(ref_input) == ref_output
     (reward_fn_codeexec.compute_score, correctness == 1.0);
  3. every individual recall-block def passes UNIT TESTS against the hidden
     reference implementation (operators.py) on probe inputs — per-block
     verification kills lucky-cancellation samples and enforces "every recall
     episode correct", the op-agnostic channel we want RFT to amplify.

The SFT pair uses the ORIGINAL stage-2 prompt (extra_info["orig_prompt"], the
eliciting scaffold stripped) -> the model's own verified response, so the format
becomes default behavior. Optionally mixes in depth-1 closed-book recall REPLAY
rows (all 25 ops) to protect atomic recall from erosion during SFT.

Usage:
    python examples/compositional_trainer/build_ra_rft_data.py \
        --rollout_path data/compositional/paper/ra_rft/iter1/rollouts \
        --out_dir      data/compositional/paper/ra_rft/iter1/sft_data \
        --replay_file  data/compositional/paper/stage15_closedbook_codeexec/train.parquet \
        --replay_n 8000
"""

import argparse
import glob
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from datasets import Dataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("COMPOSITIONAL_NUM_EXAMINE", "0")
import operators as ops_mod  # noqa: E402
from reward_fn_codeexec import compute_score  # noqa: E402

_FUNC_RE = re.compile(r"func_\d+")
_RECALL_RE = re.compile(
    r"Recall (func_\d+):[^\n]*\n+```(?:python|py)?[ \t]*\r?\n(.*?)```",
    re.DOTALL | re.IGNORECASE)
_N_TO_NAME = {v: k for k, v in ops_mod.func_name_mapping.items()}

# Probe-argument conventions per op (mirrors generate_data.random_expr_paper).
_PROBE_STRINGS = ["vlnbm", "aAbBcC z", "qqwweer", "xyz"]
_ARG2 = {
    "repeat_str": [2, 3], "rotate_str": [1, 2], "shift_chars": [1, 3],
    "while_rotate": [1, 2], "loop_concat": [2, 3],
    "backchain_add_digit": [1, 2], "backchain_palindrome": [1, 2],
    "add_prefix": ["ab", "xq"], "add_suffix": ["ab", "xq"],
    "insert_separator": ["-", "_"],
}
_TWO_STR = {"interlace_str", "recursive_interlace"}


def probe_calls(op_name):
    """[(args_tuple, expected_output), ...] from the reference implementation."""
    ref = getattr(ops_mod, op_name)
    calls = []
    for s in _PROBE_STRINGS:
        if op_name in _TWO_STR:
            args = (s, "pqr")
        elif op_name in _ARG2:
            args = (s, _ARG2[op_name][len(calls) % len(_ARG2[op_name])])
        else:
            args = (s,)
        calls.append((args, ref(*args)))
    return calls


_UNIT_DRIVER = """
import sys, json
from math import gcd as _gcd
_cases = json.loads(sys.stdin.read())
_out = []
for _code, _fn, _argsets in _cases:
    # gcd preloaded: operators.py imports it at module level, so a faithful
    # re-implementation may reasonably assume it without an in-block import.
    _ns = {"gcd": _gcd}
    try:
        exec(_code, _ns)
        _f = _ns.get(_fn)
        _res = []
        for _a in _argsets:
            try:
                _res.append(_f(*_a))
            except BaseException as _e:
                _res.append("__ERR__" + type(_e).__name__)
    except BaseException as _e:
        _res = ["__ERR__" + type(_e).__name__] * len(_argsets)
    _out.append(_res)
print(json.dumps(_out))
"""


def unit_test_blocks(blocks):
    """blocks: [(func_n, code)] -> True iff every def matches its reference on all probes."""
    cases, expected = [], []
    for func_n, code in blocks:
        op_name = _N_TO_NAME.get(func_n)
        if op_name is None:
            return False
        pcs = probe_calls(op_name)
        cases.append([code, func_n, [list(a) for a, _ in pcs]])
        expected.append([e for _, e in pcs])
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", "-c", _UNIT_DRIVER],
            input=json.dumps(cases), capture_output=True, text=True, timeout=15)
        got = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return False
    return got == expected


def check_response(resp, gt_json, ds, ei):
    """-> (ok, fail_reason)."""
    gt = json.loads(gt_json)
    needed = set(_FUNC_RE.findall(gt["ref_code"]))
    recalls = _RECALL_RE.findall(resp)
    recalled = {fn for fn, _ in recalls}
    if recalled != needed:
        return False, "recall_set_mismatch"
    if any(f"def {fn}" not in code for fn, code in recalls):
        return False, "recall_block_wrong_def"
    if "Assemble" not in resp:
        return False, "no_assemble"
    res = compute_score(ds, resp, gt_json, {**ei, "split": "train"})
    if res.get("correctness", 0.0) != 1.0:
        return False, f"program_{res.get('_exec_error', 'wrong')}"
    if not unit_test_blocks(recalls):
        return False, "unit_test_fail"
    return True, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollout_path", required=True, help="rollout parquet file or dir")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--val_size", type=int, default=256)
    ap.add_argument("--max_keep_per_problem", type=int, default=2)
    ap.add_argument("--max_chars", type=int, default=8000)
    ap.add_argument("--replay_file", default=None,
                    help="messages-format parquet mixed in as-is (depth-1 recall replay)")
    ap.add_argument("--replay_n", type=int, default=8000)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    files = (sorted(glob.glob(os.path.join(args.rollout_path, "*.parquet")))
             if os.path.isdir(args.rollout_path) else [args.rollout_path])
    tasks = []
    for f in files:
        df = pd.read_parquet(f)
        for i, r in df.iterrows():
            ei = dict(r["extra_info"]) if r["extra_info"] is not None else {}
            seed = ei.get("seed_prefix", "")
            for resp in r["responses"]:
                # Re-attach the prefix-forced seed so the verified/stored
                # assistant message is the COMPLETE formatted answer.
                tasks.append((f"{f}:{i}", seed + resp, r["reward_model"]["ground_truth"],
                              r["data_source"], ei))

    reasons = Counter()
    by_problem = {}
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for (pid, resp, gt, ds, ei), (ok, why) in zip(
                tasks, ex.map(lambda t: check_response(t[1], t[2], t[3], t[4]), tasks)):
            reasons[why] += 1
            if ok and len(resp) <= args.max_chars:
                by_problem.setdefault(pid, (ei, []))[1].append(resp)

    rng = random.Random(args.seed)
    rows = []
    for pid, (ei, resps) in by_problem.items():
        orig = ei.pop("orig_prompt", None)
        ei.pop("seed_prefix", None)
        if not orig:
            reasons["no_orig_prompt"] += 1
            continue
        rng.shuffle(resps)
        for resp in resps[: args.max_keep_per_problem]:
            rows.append({"messages": [{"role": "user", "content": orig},
                                      {"role": "assistant", "content": resp}],
                         "extra_info": ei})

    n_rft = len(rows)
    if args.replay_file and args.replay_n > 0:
        rdf = pd.read_parquet(args.replay_file)
        idx = rng.sample(range(len(rdf)), min(args.replay_n, len(rdf)))
        for i in idx:
            r = rdf.iloc[i]
            rows.append({"messages": [dict(m) for m in r["messages"]],
                         "extra_info": dict(r["extra_info"]) if r["extra_info"] is not None else {}})

    rng.shuffle(rows)
    os.makedirs(args.out_dir, exist_ok=True)
    val = rows[: args.val_size] if args.val_size > 0 else []
    train = rows[args.val_size:] if args.val_size > 0 else rows
    Dataset.from_list(train).to_parquet(os.path.join(args.out_dir, "train.parquet"))
    if val:
        Dataset.from_list(val).to_parquet(os.path.join(args.out_dir, "test.parquet"))

    print(f"[ra-rft] responses={len(tasks)} verdicts={dict(reasons)}")
    print(f"[ra-rft] problems_with_keep={len(by_problem)} rft_traces={n_rft} "
          f"replay={len(rows) - n_rft} -> train={len(train)} val={len(val)} @ {args.out_dir}")
    if n_rft == 0:
        print("[ra-rft][ERROR] nothing survived verification — inspect a few rollouts "
              "for format compliance before rerunning.")
        sys.exit(2)


if __name__ == "__main__":
    main()
