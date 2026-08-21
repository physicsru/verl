"""Score depth-sweep rollouts per depth — the pre-RL compositional baseline.

Companion to score_probe.py (which groups by op at depth 1): reads
rollout_stage1.py output parquets from labeled dirs, scores every response
with reward_fn_codeexec, and prints per-DEPTH accuracy. Run on the held-out
stage2_level1to8_codeexec test set BEFORE stage-2 RL to separate "SFT installs
multi-helper robustness" from "RL adds composition": the delta between this
table and the RL run's validation curve is RL's contribution.

Also reports mean response length (chars) per depth — the smoking gun for the
EOS fix: pre-fix models cap-fill every budget, so length ~= max_tokens
everywhere; a fixed model's correct responses terminate around ~2-4k chars.

Usage:
    python examples/compositional_trainer/score_depth_sweep.py \
        --in stage15b=checkpoints/.../depth_sweep_stage15b \
        --out analysis/depth_sweep_stage15b.md
"""

import argparse
import glob
import os
import sys
from collections import defaultdict

import pandas as pd

os.environ.setdefault("COMPOSITIONAL_NUM_EXAMINE", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reward_fn_codeexec import compute_score  # noqa: E402


def score_dir(d):
    files = sorted(glob.glob(os.path.join(d, "*.parquet")))
    assert files, f"no parquets under {d}"
    acc, lens = defaultdict(list), defaultdict(list)
    for f in files:
        df = pd.read_parquet(f)
        for _, r in df.iterrows():
            depth = int(r["extra_info"]["depth"])
            for resp in r["responses"]:
                res = compute_score(r["data_source"], resp,
                                    r["reward_model"]["ground_truth"],
                                    {**dict(r["extra_info"]), "split": "val"})
                acc[depth].append(res["correctness"])
                lens[depth].append(len(resp))
    return acc, lens


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="ins", nargs="+", required=True, metavar="LABEL=DIR")
    ap.add_argument("--out", default=None, help="also write the table to this markdown file")
    args = ap.parse_args()

    labeled = [s.split("=", 1) for s in args.ins]
    results = {label: score_dir(d) for label, d in labeled}
    labels = [label for label, _ in labeled]

    depths = sorted({d for label in labels for d in results[label][0]})
    header = "| depth | n | " + " | ".join(f"{la} acc | {la} len" for la in labels) + " |"
    lines = [header, "|---|---|" + "---|---|" * len(labels)]
    for depth in depths:
        n = len(next(iter(results.values()))[0].get(depth, []))
        cells = []
        for la in labels:
            a, ln = results[la]
            cells.append(f"{sum(a[depth]) / len(a[depth]):.3f}" if depth in a else "—")
            cells.append(f"{sum(ln[depth]) / len(ln[depth]):.0f}" if depth in ln else "—")
        lines.append(f"| {depth} | {n} | " + " | ".join(cells) + " |")

    table = "\n".join(lines)
    print(table)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            f.write("# Held-out-op depth sweep (greedy@1, code-exec, pre-RL)\n\n" + table + "\n")
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
