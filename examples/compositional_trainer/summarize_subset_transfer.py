"""Subset-transfer readout (H0 vs H1): per-op episode-ok for treated vs untreated held-out ops.

Reads analysis/cls_ra_abl_<cell>[_s<seed>]_b3072.md (per-op episode table written by
classify_ra_failures.py), data/compositional/paper/ra_rft/sft_bootstrap_<cell>/treated_ops.json
and analysis/ci_ra_abl_<cell>[_s<seed>]_b3072.md, and prints per cell: whole-model held-out
d4/d8, mean episode-ok over treated ops, over untreated ops, and the untreated ops' change
relative to sub0 (same ops, same seed) — H1 predicts the last column rises with K.

    python examples/compositional_trainer/summarize_subset_transfer.py [--cells sub0,sub3,sub6,sub9] [--seeds 1,7,123]
"""
import argparse
import json
import os
import re
import statistics as st

RE_OP = re.compile(r"^\| (func_\S+) \| (\d+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|")
RE_CI = re.compile(r"^\| (\d) \| \d+ \| [\d.]+ \| [\d.]+ \| [\d.]+ \| [\d.]+ \| \*\*([\d.]+)\*\*")


def per_op(path):
    ok, inside = {}, False
    for line in open(path):
        if "per-op episode verdicts" in line:
            inside = True
        elif line.startswith("### "):
            inside = False
        m = RE_OP.match(line) if inside else None
        if m:
            ok[m.group(1)] = float(m.group(3))
    return ok


def ci(path):
    d = {}
    for line in open(path):
        m = RE_CI.match(line)
        if m:
            d[int(m.group(1))] = float(m.group(2))
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", default="sub0,sub3,sub6,sub9")
    ap.add_argument("--seeds", default="1,7,123")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    seeds = a.seeds.split(",")
    tag = lambda s: "" if s == "1" else f"_s{s}"
    base = {}  # seed -> per-op ok of sub0
    for s in seeds:
        f = os.path.join(a.root, f"analysis/cls_ra_abl_sub0{tag(s)}_b3072.md")
        if os.path.exists(f):
            base[s] = per_op(f)
    print(f"{'cell':6s} {'seed':5s} {'d4':>6s} {'d8':>6s} {'treated ok':>11s} {'untreated ok':>13s} {'untreated - sub0':>17s}  treated ops")
    for cell in a.cells.split(","):
        tj = os.path.join(a.root, f"data/compositional/paper/ra_rft/sft_bootstrap_{cell}/treated_ops.json")
        treated = set(json.load(open(tj))["treated"]) if os.path.exists(tj) else set()
        rows = []
        for s in seeds:
            cf = os.path.join(a.root, f"analysis/cls_ra_abl_{cell}{tag(s)}_b3072.md")
            cif = os.path.join(a.root, f"analysis/ci_ra_abl_{cell}{tag(s)}_b3072.md")
            if not (os.path.exists(cf) and os.path.exists(cif)):
                continue
            ok, c = per_op(cf), ci(cif)
            tr = [v for o, v in ok.items() if o in treated]
            un = [v for o, v in ok.items() if o not in treated]
            delta = st.mean(ok[o] - base[s][o] for o in ok if o not in treated and o in base.get(s, {})) if s in base and un else float("nan")
            rows.append((s, c.get(4), c.get(8), st.mean(tr) if tr else float("nan"), st.mean(un) if un else float("nan"), delta))
            print(f"{cell:6s} {s:5s} {c.get(4, float('nan')):6.3f} {c.get(8, float('nan')):6.3f} {rows[-1][3]:11.3f} {rows[-1][4]:13.3f} {delta:17.3f}  {','.join(sorted(treated, key=lambda x: int(x.split('_')[1])))}")
        if len(rows) > 1:
            vals = lambda i: [r[i] for r in rows if r[i] is not None and r[i] == r[i]]
            m = lambda i: st.mean(vals(i)) if vals(i) else float("nan")
            sd = lambda i: st.pstdev(vals(i)) if vals(i) else float("nan")
            print(f"{cell:6s} {'mean':5s} {m(1):6.3f} {m(2):6.3f} {m(3):11.3f} {m(4):13.3f} {m(5):17.3f}  (n={len(rows)}, sd d4 {sd(1):.3f}, untreated {sd(4):.3f})")


if __name__ == "__main__":
    main()
