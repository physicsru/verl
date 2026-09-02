"""Failure classification for RA-format greedy sweeps (WALKTHROUGH §16-17).

Per response (depth >= --min_depth) the FIRST matching bucket:
  ok | truncated | plan_omission (v2 plan line misses a needed func AND it is
  also unrecalled) | episode_omission | syntax_error | assembly_wrong (the
  model's own `main_solution` is wrong even with the REFERENCE defs substituted
  — isolates the copy/linearization step from recall) | def_<ExcName> |
  def_wrong_answer.
Plus per-EPISODE statistics over depths 2..8 (every `Recall func_N:` block is
unit-tested with the RFT-gate probes): ok / TypeError (signature) / wrong /
other — the omission-independent measure of per-op recall quality; and, for
v2 sweeps, the arity-cue error rate (cue count != call-site arg count).

    python examples/compositional_trainer/classify_ra_failures.py \
        --sweep v1_s7=data/compositional/paper/ra_rft/ablation_sweep_v1_s7_b3072 \
                v2_s1=data/compositional/paper/ra_rft/ablation_sweep_v2_b3072 \
        [--min_depth 5] [--out analysis/x.md]
"""

import argparse
import ast
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("COMPOSITIONAL_NUM_EXAMINE", "0")
import operators as _ops_mod  # noqa: E402
from build_ra_elicit_data import renamed_source  # noqa: E402
from build_ra_rft_data import _FUNC_RE, _N_TO_NAME, _RECALL_RE, _UNIT_DRIVER, probe_calls  # noqa: E402
from reward_fn_codeexec import _execute_once, _extract_code_blocks, _pick_program  # noqa: E402

_PLAN_RE = re.compile(r"Step 1 - Plan:[^\n]*?(?:in order: |to recall: )([^\n]*?)\.?\n")
_CUE_RE = re.compile(r"Recall (" + _N_TO_NAME and "" or "" + r"func_\d+): \(called as [^\n]*?— (\d) parameters?\)") if False else re.compile(r"Recall (" + __import__("operators").FUNC_RE_STR + r"): \(called as [^\n]*?— (\d) parameters?\)")
BUCKETS = ["ok", "truncated", "plan_omission", "episode_omission", "syntax_error", "assembly_wrong",
           "def_NameError", "def_TypeError", "def_wrong_answer"]


def _model_main(code):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == "main_solution":
            return ast.unparse(n)
    return None


def classify(resp, gt):
    needed = set(_FUNC_RE.findall(gt["ref_code"]))
    if not resp.rstrip().endswith("```") or "Assemble" not in resp:
        return "truncated"
    m = _PLAN_RE.search(resp)
    planned = set(_FUNC_RE.findall(m.group(1))) if m else None
    recalled = {fn for fn, _ in _RECALL_RE.findall(resp)}
    code = _pick_program(_extract_code_blocks(resp))
    x = gt["ref_input"]["x"]
    out, err = _execute_once(code, "main_solution", x)
    if out == gt["ref_output"]:
        return "ok"
    if planned is not None and (needed - planned) & (needed - recalled):
        return "plan_omission"
    if needed - recalled:
        return "episode_omission"
    mm = _model_main(code)
    if mm is None:
        return "syntax_error"
    ref_prog = ("from math import gcd\n" + "\n\n".join(renamed_source(_N_TO_NAME[fn]) for fn in sorted(needed))
                + "\n\n" + mm)
    asm, _ = _execute_once(ref_prog, "main_solution", x)
    if asm != gt["ref_output"]:
        return "assembly_wrong"
    if err and err != "ok":
        e = err.split(":")[0]
        return {"NameError": "def_NameError", "TypeError": "def_TypeError"}.get(e, "def_" + e[:18])
    return "def_wrong_answer"


def episode_verdicts(recalls):
    cases, exp = [], []
    for fn, code in recalls:
        op = _N_TO_NAME.get(fn)
        if op is None:
            continue
        pcs = probe_calls(op)
        cases.append([code, fn, [list(a) for a, _ in pcs]])
        exp.append([e for _, e in pcs])
    if not cases:
        return []
    try:
        proc = subprocess.run([sys.executable, "-I", "-S", "-c", _UNIT_DRIVER], input=json.dumps(cases),
                              capture_output=True, text=True, timeout=20)
        got = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return ["other"] * len(cases)
    out = []
    for g, e in zip(got, exp):
        errs = [v for v in g if isinstance(v, str) and v.startswith("__ERR__")]
        out.append("ok" if g == e else "TypeError" if errs and all(v == "__ERR__TypeError" for v in errs)
                   else "other" if errs else "wrong")
    return out


def _first_call(skel, fn):
    for n in ast.walk(ast.parse(skel)):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == fn:
            return n
    return None


def episode_stats(resp, gt):
    needed = set(_FUNC_RE.findall(gt["ref_code"]))
    m = _PLAN_RE.search(resp)
    planned = set(_FUNC_RE.findall(m.group(1))) if m else None
    recalls = _RECALL_RE.findall(resp)
    recalled = {fn for fn, _ in recalls}
    cues = 0
    cue_err = 0
    for fn, n_cue in _CUE_RE.findall(resp):
        c = _first_call(gt["ref_code"], fn)
        if c is not None:
            cues += 1
            cue_err += int(n_cue) != len(c.args)
    return dict(plan_missing=len(needed - planned) if planned is not None else -1,
                recall_missing=len(needed - recalled), cues=cues, cue_err=cue_err, ep=episode_verdicts(recalls),
                ep_fns=[fn for fn, _ in recalls if _N_TO_NAME.get(fn) is not None])   # aligned with ep


def load(d):
    df = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(os.path.join(d, "*.parquet")))])
    return [(int(r["extra_info"]["depth"]), r["responses"][0], json.loads(r["reward_model"]["ground_truth"]))
            for _, r in df.iterrows()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", nargs="+", required=True, metavar="LABEL=DIR")
    ap.add_argument("--min_depth", type=int, default=5, help="for the failure buckets")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    lines = []

    def emit(s=""):
        print(s)
        lines.append(s)

    for spec in args.sweep:
        label, d = spec.split("=", 1)
        rows = load(d)
        with ThreadPoolExecutor(args.workers) as ex:
            cls = list(ex.map(lambda r: (r[0], classify(r[1], r[2])), [r for r in rows if r[0] >= args.min_depth]))
            eps = list(ex.map(lambda r: (r[0], episode_stats(r[1], r[2])), [r for r in rows if r[0] >= 2]))
        emit(f"\n### {label} — failure buckets (depth >= {args.min_depth}, n per depth)\n")
        emit("| depth | n | " + " | ".join(BUCKETS) + " | other |")
        emit("|---|---|" + "---|" * (len(BUCKETS) + 1))
        tab = defaultdict(Counter)
        for dep, c in cls:
            tab[dep][c] += 1
        for dep in sorted(tab):
            other = sum(v for k, v in tab[dep].items() if k not in BUCKETS)
            emit(f"| {dep} | {sum(tab[dep].values())} | " + " | ".join(str(tab[dep][k]) for k in BUCKETS) + f" | {other} |")
        emit(f"\n### {label} — per-episode statistics (depth 2-8)\n")
        emit("| depth | n | plan_incomplete | recall_incomplete | cue_arity_err | episodes | ep_ok | ep_TypeError | ep_wrong | ep_other |")
        emit("|---|---|---|---|---|---|---|---|---|---|")
        for dep in range(2, 9):
            rs = [a for dd, a in eps if dd == dep]
            n = len(rs)
            if not n:
                continue
            ep = Counter(v for a in rs for v in a["ep"])
            tot = max(sum(ep.values()), 1)
            cues = sum(a["cues"] for a in rs)
            pi = "n/a" if all(a["plan_missing"] < 0 for a in rs) else f"{sum(a['plan_missing'] > 0 for a in rs) / n:.3f}"
            ce = "n/a" if not cues else f"{sum(a['cue_err'] for a in rs) / cues:.3f}"
            emit(f"| {dep} | {n} | {pi} | {sum(a['recall_missing'] > 0 for a in rs) / n:.3f} | {ce} | {tot} | "
                 f"{ep['ok'] / tot:.3f} | {ep['TypeError'] / tot:.3f} | {ep['wrong'] / tot:.3f} | {ep['other'] / tot:.3f} |")
        # per-op binding quality under load: every episode of that op at depth >= 2, whatever its
        # neighbours — the primary readout of the subset-transfer test (treated vs untreated ops)
        emit(f"\n### {label} — per-op episode verdicts (depth 2-8, all episodes of the op)\n")
        emit("| op | episodes | ok | TypeError | wrong | other |")
        emit("|---|---|---|---|---|---|")
        per_op = defaultdict(Counter)
        for _, a in eps:
            for fn, v in zip(a["ep_fns"], a["ep"]):
                per_op[fn][v] += 1
        for fn in sorted(per_op, key=lambda f: _ops_mod.FUNC_ORDER.get(f, 999)):
            c = per_op[fn]
            tot = sum(c.values())
            emit(f"| {fn} | {tot} | {c['ok'] / tot:.3f} | {c['TypeError'] / tot:.3f} | "
                 f"{c['wrong'] / tot:.3f} | {c['other'] / tot:.3f} |")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as f:
            f.write("# RA failure classification\n" + "\n".join(lines) + "\n")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
