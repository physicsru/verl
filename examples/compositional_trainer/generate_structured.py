"""Structured composition test sets — the width/depth extrapolation map (WALKTHROUGH §20).

Structures (each over the HELD-OUT 12 ops and, separately, the 13 TRAIN ops):
  serial  d=1..8   pure nesting chain  f1(f2(...fd(x)))            (single program)
  parexpr w=1..8   w independent calls joined by `+`: f1(x) + f2(x) + ...   (single program)
  parmt   w=1..8   w independent atomic TASKS in one multi-task prompt (build_ra_sft_data.multi_prompt)
  gridexpr (w,d)   w depth-d chains joined by `+`          w,d in {2,4}
  gridmt   (w,d)   w depth-d chains as w tasks             w,d in {2,4}
Ops within one program/prompt are distinct (k = number of calls). Constants follow
generate_data.random_expr_paper ranges. Outputs capped at 200k chars.

Rows are codeexec-format (prompt / reward_model.ground_truth / extra_info /
data_source = structured-<family>-<structure>-<size>); multi-task rows carry
ground_truth = {"tasks": [gt, ...]} and are scored by score_structured.py.

    python generate_structured.py --out data/compositional/paper/structured/test.parquet --n 128
"""

import argparse
import json
import math
import os
import random
import string
import sys

from datasets import Dataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import operators as ops_mod  # noqa: E402
from build_codeexec_data import _BODIES_HIDDEN, CODEEXEC_PROMPT  # noqa: E402
from build_ra_elicit_data import renamed_source  # noqa: E402
from build_ra_sft_data import multi_prompt  # noqa: E402

MAP = ops_mod.func_name_mapping
FAMILIES = {"heldout": sorted(ops_mod.PAPER_EVAL_SET), "trainops": sorted(ops_mod.PAPER_TRAIN_SET),
            "allops": sorted(ops_mod.PAPER_ALL_SET)}   # allops: parallel/atomic structures only (never serial)
NUM = {"repeat_str": (2, 4), "rotate_str": (1, 3), "shift_chars": (1, 5), "while_rotate": (1, 3),
       "loop_concat": (2, 4), "backchain_add_digit": (1, 3), "backchain_palindrome": (1, 3)}
STR = {"add_prefix": (2, 4), "add_suffix": (2, 4)}
SEP = {"insert_separator": ["-", "_", "|"]}
TWO = {"interlace_str", "recursive_interlace"}
MAX_OUT = 200_000


def lit(rng, lo=3, hi=6):
    return "".join(rng.choices(string.ascii_lowercase, k=rng.randint(lo, hi)))


def call(op, inner, rng):
    fn = MAP[op]
    if op in NUM:
        return f"{fn}({inner}, {rng.randint(*NUM[op])})"
    if op in STR:
        return f"{fn}({inner}, '{lit(rng, *STR[op])}')"
    if op in SEP:
        return f"{fn}({inner}, '{rng.choice(SEP[op])}')"
    if op in TWO:
        return f"{fn}({inner}, '{lit(rng)}')"
    return f"{fn}({inner})"


def chain(ops, rng):
    expr = "x"
    for op in ops:
        expr = call(op, expr, rng)
    return expr


_NS = {"gcd": math.gcd}
for _name in ops_mod.PAPER_ALL_SET:
    exec(renamed_source(_name), _NS)  # noqa: S102 - our own reference code


def run(skel, x):
    ns = dict(_NS)
    exec(skel, ns)  # noqa: S102
    out = ns["main_solution"](x)
    if not isinstance(out, str) or len(out) > MAX_OUT:
        raise ValueError("bad output")
    return out


def single_row(skel, x, family, structure, size, k, rng):
    out = run(skel, x)
    gt = {"ref_input": {"x": x}, "ref_output": out, "ref_code": skel, "funcname": "main_solution"}
    return {"data_source": f"structured-{family}-{structure}-{size}",
            "prompt": [{"role": "user", "content": CODEEXEC_PROMPT.format(code=skel, input=x, bodies=_BODIES_HIDDEN)}],
            "ability": "reasoning", "reward_model": {"style": "rule", "ground_truth": json.dumps(gt)},
            "extra_info": {"pool": "paper", "stage": 2, "split": "test", "family": family, "structure": structure,
                           "size": str(size), "depth": k, "k": k, "multi": False}}


def multi_row(skels, family, structure, size, k, rng):
    tasks, gts = [], []
    for sk in skels:
        x = lit(rng, 3, 10)
        gts.append({"ref_input": {"x": x}, "ref_output": run(sk, x), "ref_code": sk, "funcname": "main_solution"})
        tasks.append((sk, x))
    return {"data_source": f"structured-{family}-{structure}-{size}",
            "prompt": [{"role": "user", "content": multi_prompt(tasks)}],
            "ability": "reasoning", "reward_model": {"style": "rule", "ground_truth": json.dumps({"tasks": gts})},
            "extra_info": {"pool": "paper", "stage": 2, "split": "test", "family": family, "structure": structure,
                           "size": str(size), "depth": k, "k": k, "multi": True}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=128, help="rows per (family, structure, size)")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--family", default="heldout,trainops", help="comma list of families")
    ap.add_argument("--only", default=None,
                    help="comma list of structure:size to generate (e.g. serial:2,parmt:2); default = the full map")
    ap.add_argument("--split", default="test", help="extra_info.split (train for RL pools)")
    ap.add_argument("--max_out", type=int, default=None,
                    help="reject programs whose output exceeds this many chars (default: module MAX_OUT); the deep-chain "
                         "test uses 1000 so depth measures composition, not string blow-up")
    ap.add_argument("--serial_depths", default="1,2,3,4,5,6,7,8",
                    help="comma list of serial chain depths to generate (default 1..8; e.g. 1,2,4,...,20 for the "
                         "deep-chain test — beyond 12 held-out ops repeat, k saturates at the family size)")
    args = ap.parse_args()
    if args.max_out is not None:
        global MAX_OUT
        MAX_OUT = args.max_out
    rng = random.Random(args.seed)
    rows = []
    only = None if args.only is None else {tuple(x.split(":")) for x in args.only.split(",")}
    fams = [f.strip() for f in args.family.split(",")]
    assert all(f in FAMILIES for f in fams), fams
    for family in fams:
        names = FAMILIES[family]
        def pick(k):
            return rng.sample(names, k) if k <= len(names) else rng.choices(names, k=k)

        def gen(structure, size, make, k):
            if only is not None and (structure, str(size)) not in only:
                return
            if family == "allops" and structure in ("serial", "gridexpr", "gridmt", "parexpr"):
                return   # held-out ops are never composed; allops is for multi-task parallel only
            got, seen, tries = 0, set(), 0
            while got < args.n and tries < args.n * 50:
                tries += 1
                try:
                    row = make()
                except Exception:  # noqa: BLE001 - oversize / error -> retry
                    continue
                key = row["prompt"][0]["content"]
                if key in seen:
                    continue
                seen.add(key)
                row["extra_info"]["k"] = k
                row["extra_info"]["split"] = args.split
                rows.append(row)
                got += 1
            print(f"  {family:9s} {structure:9s} size={size}: {got}/{args.n}")

        for d in [int(x) for x in args.serial_depths.split(",")]:
            gen("serial", d, lambda d=d: single_row(f"def main_solution(x):\n    return {chain(pick(d), rng)}",
                                                     lit(rng, 3, 10), family, "serial", d, d, rng), min(d, len(names)))
        for w in range(1, 9):
            gen("parexpr", w, lambda w=w: single_row(
                "def main_solution(x):\n    return " + " + ".join(call(op, "x", rng) for op in pick(w)),
                lit(rng, 3, 10), family, "parexpr", w, w, rng), w)
            gen("parmt", w, lambda w=w: multi_row(
                [f"def main_solution(x):\n    return {call(op, 'x', rng)}" for op in pick(w)],
                family, "parmt", w, w, rng), w)
        for w in (2, 4):
            for d in (2, 4):
                gen("gridexpr", f"w{w}d{d}", lambda w=w, d=d: single_row(
                    "def main_solution(x):\n    return " + " + ".join(chain(pick(d), rng) for _ in range(w)),
                    lit(rng, 3, 10), family, "gridexpr", f"w{w}d{d}", w * d, rng), w * d)
                gen("gridmt", f"w{w}d{d}", lambda w=w, d=d: multi_row(
                    [f"def main_solution(x):\n    return {chain(pick(d), rng)}" for _ in range(w)],
                    family, "gridmt", f"w{w}d{d}", w * d, rng), w * d)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    Dataset.from_list(rows).to_parquet(args.out)
    print(f"wrote {len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
