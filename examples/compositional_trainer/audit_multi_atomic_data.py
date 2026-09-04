"""Audit multi-atomic (co-occurrence) SFT data: where held-out defs sit, and with whom.

Prints, per data dir, the MEASURED properties quoted in analysis/RESULTS_PROVENANCE.md
section (3): share of held-out atomic defs practised under load (multi-def answers)
vs in single-task rows, their position inside the answer (head / mid / tail), the
group-size distribution, and the partner-slot composition (train vs held-out).
Composition rows (ra_family == "comp") never contain held-out ops and are skipped.

    python examples/compositional_trainer/audit_multi_atomic_data.py \
        data/compositional/paper/ra_rft/sft_bootstrap_{eco,eptr,epho,pfirst,plast}

Respects COMPOSITIONAL_NAME_SCHEME via operators.FUNC_RE_STR / func_name_mapping; the held-out
set follows COMPOSITIONAL_POOL (paper | paper50, default paper).
"""
import argparse
import collections
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import operators as ops  # noqa: E402

HELDOUT = {ops.func_name_mapping[n] for n in ops.POOLS[os.environ.get("COMPOSITIONAL_POOL", "paper")]["eval"]}
RECALL_RE = re.compile(rf"Recall ({ops.FUNC_RE_STR}):")


def audit(path: str) -> None:
    df = pd.read_parquet(os.path.join(path, "train.parquet"))
    fam = df["extra_info"].apply(lambda e: (e or {}).get("ra_family"))
    single = multi = 0
    pos, partner, sizes = collections.Counter(), collections.Counter(), collections.Counter()
    for f, msgs in zip(fam, df["messages"]):
        if f == "comp":
            continue
        resp = next(m["content"] for m in msgs if m["role"] == "assistant")
        names = RECALL_RE.findall(resp)
        hos = [n for n in names if n in HELDOUT]
        if not hos:
            continue
        if len(names) == 1:
            single += 1
            continue
        multi += len(hos)
        for i, n in enumerate(names):
            if n not in HELDOUT:
                continue
            pos["head" if i == 0 else ("tail" if i == len(names) - 1 else "mid")] += 1
            sizes[len(names)] += 1
            for j, o in enumerate(names):
                if j != i:
                    partner["heldout" if o in HELDOUT else "train"] += 1
    tot = single + multi
    print(f"{os.path.basename(path.rstrip('/'))}: rows={len(df)} families={dict(collections.Counter(fam))}")
    print(f"  held-out atomic defs {tot}: under load {multi} ({multi / tot:.0%}), "
          f"single-task {single} ({single / tot:.0%})")
    if multi:
        print(f"  position of held-out defs: head {pos['head'] / multi:.0%} / mid {pos['mid'] / multi:.0%} / "
              f"tail {pos['tail'] / multi:.0%}; group sizes {dict(sorted(sizes.items()))}")
        print(f"  partner slots: train {partner['train']} : held-out {partner['heldout']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+", help="SFT data dirs containing train.parquet")
    for d in ap.parse_args().dirs:
        audit(d)
