"""Score recall-probe rollouts per op — the gate before stage-2 GPU time.

Reads rollout parquets (rollout_stage1.py output: prompt/responses/reward_model/
extra_info) from one or more labeled dirs, scores every response with
reward_fn_codeexec, and prints a per-op accuracy table (one column per label).

Usage:
    python examples/compositional_trainer/score_probe.py \
        --in stage15=checkpoints/.../probe_stage15 baseline=checkpoints/.../probe_stage1 \
        --out analysis/probe_recall_stage15.md
"""

import argparse
import glob
import os
import sys

import pandas as pd

os.environ.setdefault("COMPOSITIONAL_NUM_EXAMINE", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import operators as ops_mod  # noqa: E402
from reward_fn_codeexec import compute_score  # noqa: E402

ID_TO_REAL = {v: k for k, v in ops_mod.func_name_mapping.items()}
TRAIN_OPS = {ops_mod.func_name_mapping[k] for k in ops_mod.PAPER_TRAIN_SET}


def score_dir(d):
    files = sorted(glob.glob(os.path.join(d, "*.parquet")))
    assert files, f"no parquets under {d}"
    acc = {}
    for f in files:
        df = pd.read_parquet(f)
        for _, r in df.iterrows():
            op = r["extra_info"]["op"]
            for resp in r["responses"]:
                res = compute_score(r["data_source"], resp,
                                    r["reward_model"]["ground_truth"],
                                    {**dict(r["extra_info"]), "split": "val"})
                acc.setdefault(op, []).append(res["correctness"])
    return {op: sum(v) / len(v) for op, v in acc.items()}, \
           {op: len(v) for op, v in acc.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="ins", nargs="+", required=True, metavar="LABEL=DIR")
    ap.add_argument("--out", default=None, help="also write the table to this markdown file")
    args = ap.parse_args()

    labeled = [s.split("=", 1) for s in args.ins]
    results = {label: score_dir(d) for label, d in labeled}
    labels = [label for label, _ in labeled]

    ops = sorted({op for label in labels for op in results[label][0]},
                 key=lambda f: int(f.split("_")[1]))
    lines = ["| op | name | split | n | " + " | ".join(labels) + " |",
             "|---|---|---|---|" + "---|" * len(labels)]
    for op in ops:
        split = "train" if op in TRAIN_OPS else "EVAL"
        n = next(results[label][1].get(op, 0) for label in labels)
        cells = " | ".join(f"{results[label][0].get(op, float('nan')):.3f}" for label in labels)
        lines.append(f"| {op} | {ID_TO_REAL[op]} | {split} | {n} | {cells} |")
    for subset, name in [(ops, "ALL"),
                         ([o for o in ops if o in TRAIN_OPS], "train ops"),
                         ([o for o in ops if o not in TRAIN_OPS], "eval ops")]:
        if not subset:
            continue
        cells = " | ".join(
            f"{sum(results[label][0][o] for o in subset) / len(subset):.3f}" for label in labels)
        lines.append(f"| — | **mean {name}** | | | {cells} |")

    table = "\n".join(lines)
    print(table)
    below = {label: [ID_TO_REAL[o] for o in ops if results[label][0].get(o, 0) < 0.9]
             for label in labels}
    for label in labels:
        print(f"\n[{label}] ops below 0.9 gate ({len(below[label])}): {', '.join(below[label]) or 'none'}")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            f.write("# Per-op depth-1 recall probe (greedy@1, hidden bodies)\n\n" + table + "\n")
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
