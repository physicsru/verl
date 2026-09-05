"""Re-score a sweep under DEFS-ONLY grading: the model's Recall-episode definitions + the GIVEN
skeleton (reference `main_solution`), executed once. Compared with the standard score (which
executes the model's own Assemble block, i.e. its copy of the skeleton), the difference is the
share of failures that are pure transcription errors of the given skeleton.

    python examples/compositional_trainer/rescore_defs_only.py LABEL=<rollout_dir> [...]
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import operators as ops_mod  # noqa: E402
from reward_fn_codeexec import _execute_once, _extract_code_blocks, _pick_program  # noqa: E402

_RECALL_BLOCK = re.compile(r"Recall (" + ops_mod.FUNC_RE_STR + r"):[^\n]*\n```python\n(.*?)```", re.S)


def defs_only_program(resp, ref_code):
    blocks = _RECALL_BLOCK.findall(resp)
    if not blocks:   # no RA episodes: fall back to every def in the graded block
        prog = _pick_program(_extract_code_blocks(resp)) or ""
        defs = re.findall(r"(def (?!main_solution)\w+\(.*?)(?=\ndef |\Z)", prog, re.S)
        body = "\n\n".join(defs)
    else:
        body = "\n\n".join(code.strip() for _, code in blocks)
    return "from math import gcd\n\n" + body + "\n\n" + ref_code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sweeps", nargs="+", metavar="LABEL=DIR")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    lines = []
    for spec in a.sweeps:
        label, d = spec.split("=", 1)
        std = defaultdict(list); alt = defaultdict(list)
        for f in sorted(glob.glob(os.path.join(d, "*.parquet"))):
            df = pd.read_parquet(f)
            for resp, rm, ei in zip(df["responses"], df["reward_model"], df["extra_info"]):
                gt = json.loads(rm["ground_truth"]); depth = int(ei["depth"]); x = gt["ref_input"]["x"]
                prog = _pick_program(_extract_code_blocks(resp[0])) or ""
                r1 = _execute_once(prog, "main_solution", x)
                r2 = _execute_once(defs_only_program(resp[0], gt["ref_code"]), "main_solution", x)
                ok1 = r1[1] is None and r1[0] == gt["ref_output"]   # (result, error)
                ok2 = r2[1] is None and r2[0] == gt["ref_output"]
                std[depth].append(ok1); alt[depth].append(ok2)
        lines.append(f"### {label}: standard (model's Assemble copy) vs defs-only (given skeleton appended)")
        lines.append("| depth | n | standard | defs-only | gain |"); lines.append("|---|---|---|---|---|")
        for dep in sorted(std):
            s = sum(std[dep]) / len(std[dep]); t = sum(alt[dep]) / len(alt[dep])
            lines.append(f"| {dep} | {len(std[dep])} | {s:.3f} | {t:.3f} | {t - s:+.3f} |")
    doc = "\n".join(lines) + "\n"
    print(doc)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write("# Defs-only rescoring\n\n" + doc)


if __name__ == "__main__":
    main()
