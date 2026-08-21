"""Compositionality Index (CI) — how much atomic skill survives composition.

In the code-exec condition a depth-n program succeeds iff every distinct
`func_i` it references is re-implemented correctly (the composition skeleton is
GIVEN in the prompt, so no structural inference is required). If op i is
recalled correctly with probability x_i when tested alone (depth 1), then
perfect compositional mastery predicts a depth-n program containing ops S
succeeds with probability

    bound = prod_{i in S} x_i         (distinct ops — duplicated calls reuse one def)

and the Compositionality Index

    CI(n) = observed_acc(n) / mean bound(n)

measures the fraction of independently-available skill that survives being
composed. CI ~ 1 = true mastery; CI decaying with n = interference (the model
cannot recall k items at once even though it can recall each alone). Because a
def's correctness does not depend on the input string, the bound is not
confounded by intermediate values growing with depth (unlike the CoT condition).

Also reported: implied per-op reliability p(n) = obs(n)^(1/k(n)) — the constant
per-op success rate that WOULD produce the observed accuracy under independent
compounding. p falling with n is the interference signature.

Two input modes:

  1. Rollout sweep (exact, per-op x_i), from rollout_stage1.py output dirs:
       python examples/compositional_trainer/compositionality_index.py \
           --sweep stage15b=checkpoints/compositional/probe_stage15b/depth_sweep_stage15b \
           --out analysis/ci_stage15b.md

  2. Training log (approximate, uniform x = depth-1 score), from a verl job log
     plus the test parquet (for k(n) = mean distinct ops per depth):
       python examples/compositional_trainer/compositionality_index.py \
           --log comp-s2cx-v3.o2465997 \
           --test-parquet data/compositional/paper/stage2_level1to8_codeexec/test.parquet
     Prints CI at the first and last validation step (--all-steps for every one).
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

import pandas as pd

os.environ.setdefault("COMPOSITIONAL_NUM_EXAMINE", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_FUNC_RE = re.compile(r"func_\d+")


def _ops_of(ref_code):
    return sorted(set(_FUNC_RE.findall(ref_code)))


def _geo(vals):
    p = 1.0
    for v in vals:
        p *= v
    return p


# ---------------------------------------------------------------------------
# Mode 1 — rollout sweep parquets: exact per-op x_i and per-program bounds
# ---------------------------------------------------------------------------


def score_sweep(d):
    from reward_fn_codeexec import compute_score

    rows = []
    files = sorted(glob.glob(os.path.join(d, "*.parquet")))
    assert files, f"no parquets under {d}"
    for f in files:
        df = pd.read_parquet(f)
        for _, r in df.iterrows():
            gt = r["reward_model"]["ground_truth"]
            ops = _ops_of(json.loads(gt)["ref_code"])
            depth = int(r["extra_info"]["depth"])
            for resp in r["responses"]:
                res = compute_score(r["data_source"], resp, gt,
                                    {**dict(r["extra_info"]), "split": "val"})
                rows.append((depth, ops, res["correctness"], res["exec_ok"]))
    return rows


def ci_from_sweep(rows):
    # x_i from the depth-1 slice (rows whose program is a single distinct op)
    per_op = defaultdict(list)
    d1_all = []   # ALL depth-1 rows incl. funcless — the "depth-1 success rate"
    for depth, ops, acc, _ in rows:
        if depth == 1:
            d1_all.append(acc)
            if len(ops) == 1:
                per_op[ops[0]].append(acc)
    x = {op: sum(v) / len(v) for op, v in per_op.items()}
    x_bar = sum(x.values()) / len(x) if x else 1.0
    # Uniform theoretical reference: p_bar = overall depth-1 accuracy;
    # ubound(k) = p_bar^k = "each op as reliable as at depth 1, independently".
    p_bar = sum(d1_all) / len(d1_all) if d1_all else 1.0

    stats = defaultdict(lambda: {"acc": [], "exec": [], "bound": [], "k": []})
    for depth, ops, acc, ok in rows:
        s = stats[depth]
        s["acc"].append(acc)
        s["exec"].append(ok)
        s["bound"].append(_geo([x.get(op, x_bar) for op in ops]))
        s["k"].append(len(ops))

    table = []
    for depth in sorted(stats):
        s = stats[depth]
        n = len(s["acc"])
        acc = sum(s["acc"]) / n
        ok = sum(s["exec"]) / n
        bound = sum(s["bound"]) / n
        k = sum(s["k"]) / n
        ci = acc / bound if bound > 0 else float("nan")
        ubound = p_bar ** k
        ci_u = acc / ubound if ubound > 0 else float("nan")
        p = acc ** (1 / k) if acc > 0 and k > 0 else float("nan")
        table.append((depth, n, k, acc, ok, bound, ci, ubound, ci_u, p))
    return x, p_bar, table


# ---------------------------------------------------------------------------
# Mode 2 — verl job log: uniform-x approximation over the val trajectory
# ---------------------------------------------------------------------------

_LOG_METRIC_RE = re.compile(
    r"val-aux/compositional-codeexec-[\w-]*depth(\d)/(score|exec_ok)/mean@1:([\d.eE+-]+)")


def parse_log(path):
    """[(step, {depth: {'score':v,'exec_ok':v}}), ...] sorted by step."""
    out = []
    for ln in open(path, errors="ignore"):
        if "val-aux/compositional" not in ln:
            continue
        m = re.search(r"step:(\d+) - ", ln)
        if not m:
            continue
        d = defaultdict(dict)
        for depth, key, val in _LOG_METRIC_RE.findall(ln):
            d[int(depth)][key] = float(val)
        if d:
            out.append((int(m.group(1)), dict(d)))
    out.sort()
    return out


def k_per_depth(test_parquet):
    df = pd.read_parquet(test_parquet)
    ks = defaultdict(list)
    for _, r in df.iterrows():
        code = json.loads(r["reward_model"]["ground_truth"])["ref_code"]
        ks[int(r["extra_info"]["depth"])].append(len(_ops_of(code)))
    return {d: sum(v) / len(v) for d, v in ks.items()}


def ci_from_log_step(metrics, kmap):
    x = metrics.get(1, {}).get("score", float("nan"))
    table = []
    for depth in sorted(kmap):
        k = kmap[depth]
        acc = metrics.get(depth, {}).get("score", float("nan"))
        ok = metrics.get(depth, {}).get("exec_ok", float("nan"))
        bound = x ** k       # log mode is already the uniform reference
        ci = acc / bound if bound > 0 else float("nan")
        p = acc ** (1 / k) if acc > 0 and k > 0 else float("nan")
        table.append((depth, None, k, acc, ok, bound, ci, bound, ci, p))
    return table


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def fmt_table(table, label, p_bar=None):
    tag = f" (p̄₁ = {p_bar:.3f})" if p_bar is not None else ""
    lines = [f"### {label}{tag}", "",
             "| depth | n | k (distinct ops) | acc | exec_ok | bound | **CI** | "
             "p̄₁^k | acc/p̄₁^k | implied per-op p |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for depth, n, k, acc, ok, bound, ci, ubound, ci_u, p in table:
        lines.append(
            f"| {depth} | {n if n is not None else '—'} | {k:.2f} | {acc:.3f} | "
            f"{ok:.3f} | {bound:.3f} | **{ci:.3f}** | {ubound:.3f} | {ci_u:.3f} | "
            f"{p:.2f}".replace("nan", "—") + " |")
    return "\n".join(lines)


def fmt_ops(x):
    lines = ["### Per-op depth-1 recall x_i", "", "| op | x_i |", "|---|---|"]
    for op in sorted(x, key=lambda o: int(o.split("_")[1])):
        lines.append(f"| {op} | {x[op]:.3f} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", nargs="+", default=None, metavar="LABEL=DIR",
                    help="rollout dirs (exact mode)")
    ap.add_argument("--log", default=None, help="verl job log (approx mode)")
    ap.add_argument("--test-parquet", default=None,
                    help="test set for k(n); required with --log")
    ap.add_argument("--all-steps", action="store_true",
                    help="log mode: every validation step, not just first/last")
    ap.add_argument("--out", default=None, help="also write markdown here")
    args = ap.parse_args()

    blocks = []
    if args.sweep:
        for spec in args.sweep:
            label, d = spec.split("=", 1)
            x, p_bar, table = ci_from_sweep(score_sweep(d))
            blocks += [fmt_table(table, f"{label} (per-op bounds)", p_bar), fmt_ops(x)]
    if args.log:
        assert args.test_parquet, "--log requires --test-parquet for k(n)"
        kmap = k_per_depth(args.test_parquet)
        traj = parse_log(args.log)
        assert traj, f"no validation metrics found in {args.log}"
        picks = traj if args.all_steps else [traj[0], traj[-1]]
        for step, metrics in picks:
            blocks.append(fmt_table(ci_from_log_step(metrics, kmap),
                                    f"{os.path.basename(args.log)} @ step {step} "
                                    f"(uniform x = depth-1 score)"))
    if not blocks:
        ap.error("nothing to do: pass --sweep and/or --log")

    doc = "# Compositionality Index\n\n" + "\n\n".join(blocks) + "\n"
    print(doc)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            f.write(doc)
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
