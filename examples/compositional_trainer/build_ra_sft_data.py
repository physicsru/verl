"""Recall-then-assemble BOOTSTRAP SFT data — synthetically stitched targets.

Elicitation of the RA format from stage15b failed (smokes 2487685/2488107/
2488215: 0.4% verified yield — the SFT-installed "prose plan + ONE code block"
habit resists instructions, per-problem templates, and prefix seeding). So the
format is installed by SFT on STITCHED targets instead: the response content is
exactly the phrasing stage15b was already trained to produce at depth 1
(docstring gloss + verbatim renamed reference body), recomposed into the RA
structure. Only the STRUCTURE is new — which is precisely what we want to
teach. After this SFT the model emits RA answers natively and later iterations
can switch to on-policy prompted RFT (run_ra_rft.sh).

Row families, one output dataset:
  - COMPS  (train ops only, depth 2-4, from stage2_level1to4_codeexec):
      one recall episode per distinct func + Assemble block. Teaches
      multi-episode emission — the failing channel.
  - ATOMICS (ALL 25 ops, depth 1, from stage15_closedbook_codeexec prompts):
      single recall episode + Assemble. Held-out ops thereby practice the RA
      episode shape ATOMICALLY (never inside a composition — the held-out
      purity of the benchmark is preserved), so at eval time "a held-out op's
      episode inside an RA answer" is in-distribution.
  - FUNCLESS (--n_funcless, v2 default 1500; any depth of the comp set):
      skeletons with NO helper call (literal / `+` / `.upper()`-only, ~14% of
      depth-1 rows and ~10% of every test set) — "no helpers" plan + Assemble.
      Absent from the v1 data, which made their preservation seed-dependent
      (WALKTHROUGH §16, d12 p̄₁ = 0.87 artifact).

Two target formats (--format; COMPOSITIONAL_HISTORY §10.3):
  v1  the original: plan sentence, `Recall func_N: <gloss>` episodes in order
      of textual appearance, Assemble = defs + skeleton copied verbatim.
  v2  targets the three measured failure modes of v1 (§16 classification):
      ① plan line ENUMERATES the helpers with a count ("3 helper functions to
        recall, in order: func_20, func_3, func_19.") — against tail omission /
        episode-count leakage;
      ② episode header restates the CALL SITE and ARITY, derived from the
        skeleton ("Recall func_20: (called as func_20('hhxshm', …) — 2
        parameters) <gloss>") — against the 46% wrong-signature TypeErrors on
        held-out ops;
      ③ SEQUENTIAL Assemble: `main_solution` is linearized inner→outer into
        `t1 = …; t2 = …; return tN`, one call per line — never copies the nested
        parens (`'(' was never closed` errors); episode order = this data-flow
        order;
      ④ --self-check: `Check: func_N(<probe>) -> <ref output>` after each def
        (reference-computed, outside the graded block) — optional habit.
      Everything the grader / CI tool / RFT gate rely on is unchanged: the
      `Recall func_N:` regex still matches, the LAST fenced block is still the
      full program.

Every stitched row is verified with the SAME gate used for RFT rollouts
(build_ra_rft_data.check_response): full-program execution + per-episode unit
tests. Correct by construction, verified anyway.

Usage:
    python examples/compositional_trainer/build_ra_sft_data.py \
        --comp_path data/compositional/paper/stage2_level1to4_codeexec/train.parquet \
        --atomic_path data/compositional/paper/stage15_closedbook_codeexec/train.parquet \
        --out_dir data/compositional/paper/ra_rft/sft_bootstrap_v2 \
        --format v2 [--self-check] --n_comp 16000 --n_atomic 10000 --n_funcless 1500
    (--format v1 --n_funcless 0 reproduces the original sft_bootstrap* data.)
"""

import argparse
import ast
import json
import os
import random
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from datasets import Dataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("COMPOSITIONAL_NUM_EXAMINE", "0")
import operators as ops_mod  # noqa: E402
from build_ra_elicit_data import renamed_source  # noqa: E402
from build_ra_rft_data import check_response, probe_calls, unit_test_blocks, _RECALL_RE  # noqa: E402
from build_codeexec_data import _BODIES_HIDDEN  # noqa: E402
from reward_fn_codeexec import _execute_once, _extract_code_blocks  # noqa: E402

_FUNC_RE = re.compile(ops_mod.FUNC_RE_STR)
_N_TO_NAME = {v: k for k, v in ops_mod.func_name_mapping.items()}
_SKEL_RE = re.compile(r"You are given a code:\n\n(.*?)\n\nYour task", re.DOTALL)
_INPUT_RE = re.compile(r"`main_solution\(\"(.*?)\"\)`")

PLAN_FUNCLESS = "Step 1 - Plan: no helper functions are used."


def gloss(func_n):
    """One-sentence semantics = the reference docstring (stage15's phrasing)."""
    src = renamed_source(func_n and _N_TO_NAME[func_n] or "")
    m = re.search(r'"""(.*?)"""', src, re.DOTALL)
    return m.group(1).strip().splitlines()[0] if m else "as learned in training."


def _imports(funcs):
    return "from math import gcd\n\n" if ops_mod.GCD_FUNC in funcs else ""


# ---------------------------------------------------------------------------
# v1 — verbatim-copy Assemble (kept byte-identical for reproducibility)
# ---------------------------------------------------------------------------

def ordered_funcs(skeleton):
    """Distinct funcs in order of FIRST textual appearance (v1 episode order).

    (The original `sorted(set(...), key=skeleton.index)` tied `func_1` with
    `func_15` — `str.index` matches the prefix — and broke ties by set order,
    i.e. by PYTHONHASHSEED; ~1.5% of rows were run-dependent. finditer order is
    what was intended and is deterministic.)
    """
    return list(dict.fromkeys(_FUNC_RE.findall(skeleton)))


def stitch_v1(skeleton, funcs):
    """RA-v1 response for `skeleton` needing `funcs` (order of appearance)."""
    defs = [renamed_source(_N_TO_NAME[fn]) for fn in funcs]
    if funcs:
        parts = ["Step 1 - Plan: I will recall each helper function in isolation, "
                 "then assemble the final program.\n"]
    else:
        parts = [PLAN_FUNCLESS + "\n"]
    for fn, d in zip(funcs, defs):
        parts.append(f"Recall {fn}: {gloss(fn)}\n```python\n{d}\n```")
    body = "\n\n".join(defs)
    parts.append("Assemble:\n```python\n" + _imports(funcs) + body
                 + ("\n\n\n" if body else "") + skeleton.strip() + "\n```")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# v2 — enumerated plan, arity cue, sequential Assemble, optional self-check
# ---------------------------------------------------------------------------

def linearize(skeleton):
    """Sequentialize `main_solution`'s return expression (HISTORY §10.4 pt. 3).

    Post-order walk: every `Call` (helper or `.upper()`-style method) and
    `BinOp` (the `+` branch) first linearizes its children, then is assigned to
    the next `tN`; leaves (`x`, constants) stay inline; `return tN` (or the
    leaf itself for a funcless literal / identity skeleton).

    Returns (main_solution_source, calls) where calls = [(func_N, ast.Call)]
    for every helper call in data-flow (inner→outer, left→right) order —
    duplicates included; the caller dedups for the episode order / arity cue.
    Semantic equivalence to the skeleton is additionally enforced by the RFT
    gate (full-program execution vs the reference output).
    """
    tree = ast.parse(skeleton.strip())
    fdef = tree.body[-1]
    if not (isinstance(fdef, ast.FunctionDef) and fdef.name == "main_solution"
            and len(fdef.body) == 1 and isinstance(fdef.body[0], ast.Return)):
        raise ValueError(f"unexpected skeleton shape:\n{skeleton}")
    stmts, calls = [], []

    def lin(node):
        if isinstance(node, (ast.Name, ast.Constant)):
            return node
        if isinstance(node, ast.Call):
            if node.keywords:
                raise ValueError(f"keyword args unsupported: {ast.unparse(node)}")
            if isinstance(node.func, ast.Name) and _FUNC_RE.fullmatch(node.func.id):
                func = node.func
            elif isinstance(node.func, ast.Attribute):
                func = ast.Attribute(value=lin(node.func.value), attr=node.func.attr,
                                     ctx=ast.Load())
            else:
                raise ValueError(f"unsupported call: {ast.unparse(node)}")
            args = [lin(a) for a in node.args]   # children first = post-order
            if isinstance(func, ast.Name):
                calls.append((func.id, node))
            new = ast.Call(func=func, args=args, keywords=[])
        elif isinstance(node, ast.BinOp):
            new = ast.BinOp(left=lin(node.left), op=node.op, right=lin(node.right))
        else:
            raise ValueError(f"unsupported node {type(node).__name__}: {ast.unparse(node)}")
        name = f"t{len(stmts) + 1}"
        stmts.append(f"    {name} = {ast.unparse(new)}")
        return ast.Name(id=name, ctx=ast.Load())

    last = lin(fdef.body[0].value)
    stmts.append(f"    return {ast.unparse(last)}")
    header = f"def {fdef.name}({ast.unparse(fdef.args)}):"
    return "\n".join([header] + stmts), calls


def arity_cue(func_n, call):
    """`(called as func_20('hhxshm', …) — 2 parameters)` from the FIRST call site.

    Constant args are shown verbatim (the model must reproduce them anyway);
    data-flow args (`x`, nested calls, `+`) become `…`. Arity is visible in the
    prompt for free — this restates it right where the def is written, the
    46% wrong-signature mode of held-out failures (WALKTHROUGH §16).
    """
    shown = [ast.unparse(a) if isinstance(a, ast.Constant) else "…" for a in call.args]
    n = len(call.args)
    return f"(called as {func_n}({', '.join(shown)}) — {n} parameter{'s' if n != 1 else ''})"


def _lit(v):
    return json.dumps(v, ensure_ascii=False)


def check_line(func_n):
    """`Check: func_20("vlnbm", "pqr") -> "vplqnrbm"` — first RFT-gate probe."""
    args, out = probe_calls(_N_TO_NAME[func_n])[0]
    return f"Check: {func_n}({', '.join(_lit(a) for a in args)}) -> {_lit(out)}"


def plan_line_v2(funcs):
    k = len(funcs)
    if k == 0:
        return PLAN_FUNCLESS
    if k == 1:
        return f"Step 1 - Plan: 1 helper function to recall: {funcs[0]}."
    return f"Step 1 - Plan: {k} helper functions to recall, in order: {', '.join(funcs)}."


def stitch_v2(skeleton, self_check=False):
    """RA-v2 response for `skeleton` (COMPOSITIONAL_HISTORY §10.3). -> (text, funcs)."""
    main_src, calls = linearize(skeleton)
    first = {}
    for fn, c in calls:
        first.setdefault(fn, c)
    funcs = list(first)
    defs = [renamed_source(_N_TO_NAME[fn]) for fn in funcs]
    parts = [plan_line_v2(funcs) + "\n"]
    for fn, d in zip(funcs, defs):
        parts.append(f"Recall {fn}: {arity_cue(fn, first[fn])} {gloss(fn)}\n```python\n{d}\n```")
        if self_check:
            parts.append(check_line(fn))
    body = "\n\n".join(defs)
    parts.append("Assemble:\n```python\n" + _imports(funcs) + body
                 + ("\n\n\n" if body else "") + main_src + "\n```")
    return "\n".join(parts), funcs


def stitch(skeleton, fmt="v1", self_check=False):
    """Format dispatcher -> (response_text, funcs_in_episode_order)."""
    if fmt == "v1":
        funcs = ordered_funcs(skeleton)
        return stitch_v1(skeleton, funcs), funcs
    if fmt == "v2":
        return stitch_v2(skeleton, self_check=self_check)
    raise ValueError(fmt)


MULTI_PROMPT_HEAD = "You are given {n} independent code snippets, each with its own input:\n\n"
MULTI_PROMPT_TASK = "Task {i}:\n{code}\nInput: `main_solution(\"{input}\")`\n\n"
MULTI_PROMPT_TAIL = (
    "For each task, determine the output of its `main_solution` call. {bodies}\n\n"
    "You may use Python, under one rule: each program will be executed exactly ONCE, and you "
    "will never see its output — whatever `main_solution` returns in your program for a task is "
    "submitted directly as your answer for that task. There is no second attempt and no way to "
    "test or debug, so plan carefully before you write any code.\n\n"
    "Step 1 - Plan: in plain text, state what each function used by the tasks does and how you "
    "will implement it.\n"
    "Step 2 - Program: for EACH task, in order, write ONE complete, self-contained Python program "
    "in its own ```python code block, including any imports it needs. It must define "
    "`main_solution` (same behavior as the given code) together with every helper function it "
    "needs. The grader runs each block once and calls its `main_solution` with that task's input."
)


def multi_prompt(tasks):
    """tasks: [(skeleton, input_str)] -> multi-task prompt (E-co, WALKTHROUGH §19)."""
    body = "".join(MULTI_PROMPT_TASK.format(i=i + 1, code=sk.strip(), input=x) for i, (sk, x) in enumerate(tasks))
    return MULTI_PROMPT_HEAD.format(n=len(tasks)) + body + MULTI_PROMPT_TAIL.format(bodies=_BODIES_HIDDEN)


def stitch_multi(tasks):
    """RA-v1-shaped answer for several INDEPENDENT atomic tasks: one recall
    episode per distinct func (task order), then one Assemble block per task.
    The ops never share data flow — only the answer context. -> (text, funcs)"""
    funcs = list(dict.fromkeys(fn for sk, _ in tasks for fn in ordered_funcs(sk)))
    defs = {fn: renamed_source(_N_TO_NAME[fn]) for fn in funcs}
    parts = ["Step 1 - Plan: I will recall each helper function in isolation, "
             "then assemble one program per task.\n"]
    for fn in funcs:
        parts.append(f"Recall {fn}: {gloss(fn)}\n```python\n{defs[fn]}\n```")
    for i, (sk, _) in enumerate(tasks):
        need = ordered_funcs(sk)
        body = "\n\n".join(defs[fn] for fn in need)
        parts.append(f"Assemble (Task {i + 1}):\n```python\n" + _imports(need) + body
                     + ("\n\n\n" if body else "") + sk.strip() + "\n```")
    return "\n".join(parts), funcs


def check_multi(resp, gt_list):
    """Gate for multi-task rows: every needed func recalled, every task block
    executes to its reference output, every episode passes unit tests."""
    needed = {fn for gt in gt_list for fn in _FUNC_RE.findall(gt["ref_code"])}
    recalls = _RECALL_RE.findall(resp)
    if {fn for fn, _ in recalls} != needed:
        return False, "multi_recall_set_mismatch"
    blocks = _extract_code_blocks(resp)
    if len(blocks) < len(gt_list) + len(recalls):
        return False, "multi_block_count"
    for block, gt in zip(blocks[-len(gt_list):], gt_list):
        out, _ = _execute_once(block, "main_solution", gt["ref_input"]["x"])
        if out != gt["ref_output"]:
            return False, "multi_program_wrong"
    if not unit_test_blocks(recalls):
        return False, "unit_test_fail"
    return True, "ok"


def is_serial_chain(skeleton):
    """True iff the return expression is a pure nesting chain of >=2 helper calls:
    every call has exactly one non-constant argument (the inner call or x) and
    there is no `+` / method call anywhere."""
    try:
        node = ast.parse(skeleton.strip()).body[-1].body[0].value
    except Exception:  # noqa: BLE001
        return False
    n_calls = 0
    while True:
        if isinstance(node, ast.Name):
            return n_calls >= 2
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and _FUNC_RE.fullmatch(node.func.id)):
            return False
        flow = [a for a in node.args if not isinstance(a, ast.Constant)]
        if len(flow) != 1:
            return False
        n_calls += 1
        node = flow[0]


def atomic_ground_truth(skeleton, ref_input):
    """Execute the reference skeleton to synthesize a gt json for verification."""
    ns = {"gcd": __import__("math").gcd}
    for fn in ordered_funcs(skeleton):
        exec(renamed_source(_N_TO_NAME[fn]), ns)  # noqa: S102 - our own reference code
    exec(skeleton, ns)  # noqa: S102
    out = ns["main_solution"](ref_input)
    return json.dumps({"ref_input": {"x": ref_input}, "ref_output": out,
                       "ref_code": skeleton, "funcname": "main_solution"})


def _prompt_of(row):
    p = row["prompt"]
    return p[0]["content"] if not isinstance(p, str) else p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comp_path", required=True)
    ap.add_argument("--atomic_path", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--format", choices=["v1", "v2"], default="v1",
                    help="v1 = original stitched format; v2 = HISTORY §10.3 "
                         "(enumerated plan, arity cue, sequential Assemble)")
    ap.add_argument("--self-check", "--self_check", dest="self_check", action="store_true",
                    help="v2 only: `Check: func_N(probe) -> out` line after each def")
    ap.add_argument("--n_comp", type=int, default=16000, help="0 = atomics only")
    ap.add_argument("--min_comp_depth", type=int, default=2)
    ap.add_argument("--max_comp_depth", type=int, default=4,
                    help="depth-range ablation knob (WALKTHROUGH §15)")
    ap.add_argument("--n_atomic", type=int, default=10000)
    ap.add_argument("--heldout_atomic_per_op", type=int, default=0,
                    help="C5 frequency control (WALKTHROUGH §21): after the gate, duplicate each "
                         "HELD-OUT op's atomic rows to reach N answers per op (single-task context, "
                         "matching the train ops' ~4k def occurrences). Off by default.")
    ap.add_argument("--n_funcless", type=int, default=None,
                    help="helper-free skeletons from the comp set (ANY depth); "
                         "default 1500 for v2, 0 for v1 (reproducibility)")
    ap.add_argument("--multi_atomic", action="store_true",
                    help="E-co (WALKTHROUGH §19): group atomic rows into multi-task answers — each "
                         "base atomic task gets U{0..max_extra_tasks} extra independent atomic tasks "
                         "(1-4 defs per answer), op frequencies unchanged, ops never composed")
    ap.add_argument("--max_extra_tasks", type=int, default=3)
    ap.add_argument("--heldout_position", choices=["any", "first", "last"], default="any",
                    help="multi-atomic grouping: place HELD-OUT ops' tasks at this position inside "
                         "each group (partners otherwise random) — disentangles position from partner "
                         "identity in the eptr/epho contrast (HISTORY §17).")
    ap.add_argument("--partner_split", choices=["any", "train", "test"], default="any",
                    help="multi-atomic grouping: restrict PARTNER tasks to ops of this split "
                         "(base tasks stay unrestricted; per-op def counts unchanged). "
                         "'train' = held-out ops only ever co-occur with strong (composed) partners; "
                         "'test' = only with other held-out ops. (HISTORY §17 co-occurrence decomposition)")
    ap.add_argument("--partner_reuse", action="store_true",
                    help="with --partner_split: when the partner pool runs out, draw the missing partners "
                         "again from the full partner list (with replacement across groups) instead of "
                         "letting the remaining bases become single-task rows. Without it, eptr-style "
                         "builds leave ~46%% of held-out tasks single-task (RESULTS_PROVENANCE issue #6). "
                         "Raises the partner ops' atomic def counts; the build prints the audit stats.")
    ap.add_argument("--min_extra_tasks", type=int, default=0,
                    help="e.g. 1 with --max_extra_tasks 1 = every atomic answer has exactly 2 tasks (width-2)")
    ap.add_argument("--comp_structure", choices=["any", "serial"], default="any",
                    help="serial = keep only pure nesting chains f(g(...(x))) (no `+`/method calls, "
                         ">=2 calls) among the comp rows — the minimal depth-2 primitive (WALKTHROUGH §20)")
    ap.add_argument("--val_size", type=int, default=256)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    if args.self_check and args.format != "v2":
        ap.error("--self-check requires --format v2")
    if args.n_funcless is None:
        args.n_funcless = 1500 if args.format == "v2" else 0

    rng = random.Random(args.seed)
    cands = []   # (user_prompt, response, gt_json, extra_info)
    tag = f"recall_assemble_sft_{args.format}{'_sc' if args.self_check else ''}"

    def add(prompt, skeleton, gt_json, ei, family):
        resp, funcs = stitch(skeleton, args.format, args.self_check)
        ei = dict(ei)
        ei.update(condition=tag, ra_format=args.format, ra_family=family,
                  n_helpers=len(funcs))
        cands.append((prompt, resp, gt_json, ei))

    cdf_all = pd.read_parquet(args.comp_path)
    cdf_all["_skel"] = [json.loads(g["ground_truth"])["ref_code"] for g in cdf_all["reward_model"]]
    cdf_all["_has_func"] = [bool(_FUNC_RE.search(s)) for s in cdf_all["_skel"]]

    # COMPS: depth-filtered sample, helper-free rows skipped (v1-identical sampling).
    cdf = cdf_all[[args.min_comp_depth <= int(e["depth"]) <= args.max_comp_depth
                   for e in cdf_all["extra_info"]]]
    if args.comp_structure == "serial":
        cdf = cdf[[is_serial_chain(sk) for sk in cdf["_skel"]]]
        print(f"[ra-sft] comp_structure=serial: {len(cdf)} pure chains in depth range")
    cdf = cdf.sample(n=min(args.n_comp, len(cdf)), random_state=args.seed)
    for _, r in cdf.iterrows():
        if not r["_has_func"]:
            continue
        add(_prompt_of(r), r["_skel"], r["reward_model"]["ground_truth"], r["extra_info"], "comp")

    # ATOMICS: all 25 ops, depth 1.
    adf = pd.read_parquet(args.atomic_path)
    adf = adf.sample(n=min(args.n_atomic, len(adf)), random_state=args.seed)
    atomics = []   # (prompt, skeleton, input, extra_info)
    for _, r in adf.iterrows():
        prompt = r["messages"][0]["content"]
        skel_m, in_m = _SKEL_RE.search(prompt), _INPUT_RE.search(prompt)
        if not skel_m or not in_m:
            continue
        skeleton = skel_m.group(1)
        if not _FUNC_RE.search(skeleton):
            continue
        atomics.append((prompt, skeleton, in_m.group(1), r["extra_info"]))
    multi_cands = []   # (prompt, resp, [gt dicts], extra_info)
    if not args.multi_atomic:
        for prompt, skeleton, x, ei in atomics:
            add(prompt, skeleton, atomic_ground_truth(skeleton, x), ei, "atomic")
    else:
        pool = list(atomics)
        rng.shuffle(pool)
        n_reused = 0
        if args.partner_split != "any":
            partners = [a for a in pool if str(a[3].get("op_split")) == args.partner_split]
            bases = [a for a in pool if str(a[3].get("op_split")) != args.partner_split]
            rng.shuffle(partners)
            partner_src = list(partners)   # --partner_reuse draws from here once `partners` is spent
        while pool or (args.partner_split != "any" and (bases or partners)):
            if args.partner_split == "any":
                base = pool.pop()
                k = min(rng.randint(args.min_extra_tasks, args.max_extra_tasks), len(pool))
                group = [base] + [pool.pop() for _ in range(k)]
            else:
                # bases from the non-partner split first; leftover partners become single-task rows
                # (unless --partner_reuse, which tops groups up from the full partner list)
                from_bases = bool(bases)
                base = bases.pop() if bases else partners.pop()
                k = rng.randint(args.min_extra_tasks, args.max_extra_tasks)
                extra = [partners.pop() for _ in range(min(k, len(partners)))]
                if args.partner_reuse and from_bases:
                    # top up from the full partner list (with replacement across groups, never
                    # the same task twice inside one group); leftover partners used as bases
                    # after the bases are spent stay single-task as before
                    while len(extra) < k:
                        cand = partner_src[rng.randrange(len(partner_src))]
                        if all(cand is not e for e in extra):
                            extra.append(cand)
                            n_reused += 1
                group = [base] + extra
                pool = bases + partners   # loop condition bookkeeping
            if k == 0:
                prompt, skeleton, x, ei = base
                add(prompt, skeleton, atomic_ground_truth(skeleton, x), ei, "atomic")
                continue
            if args.heldout_position != "any":
                ho = [g for g in group if str(g[3].get("op_split")) == "test"]
                tr = [g for g in group if str(g[3].get("op_split")) != "test"]
                group = (ho + tr) if args.heldout_position == "first" else (tr + ho)
            tasks = [(sk, x) for _, sk, x, _ in group]
            resp, funcs = stitch_multi(tasks)
            gts = [json.loads(atomic_ground_truth(sk, x)) for sk, x in tasks]
            ei = dict(base[3])
            ei.update(condition=tag + "_multi", ra_format=args.format, ra_family="multi_atomic",
                      n_helpers=len(funcs), n_tasks=len(tasks), op="+".join(funcs))
            multi_cands.append((multi_prompt(tasks), resp, gts, ei))

    # FUNCLESS: helper-free skeletons from the comp set, any depth (HISTORY §10.2 C2).
    n_funcless = 0
    if args.n_funcless > 0:
        fdf = cdf_all[~cdf_all["_has_func"]]
        fdf = fdf.sample(n=min(args.n_funcless, len(fdf)), random_state=args.seed)
        for _, r in fdf.iterrows():
            add(_prompt_of(r), r["_skel"], r["reward_model"]["ground_truth"],
                r["extra_info"], "funcless")
            n_funcless += 1

    # Verify every stitched row with the RFT gate. The gate runs sandboxed
    # subprocesses with a wall-clock timeout, and compute_score collapses every
    # failure (timeouts included) into "program_wrong" — so on a loaded login
    # node a parallel pass yields spurious failures. Failures are therefore
    # re-checked SEQUENTIALLY once; a row is dropped only if it fails twice.
    def _gate(c):
        return check_response(c[1], c[2], "compositional-codeexec-ra", c[3])

    def _gate_multi(c):
        return check_multi(c[1], c[2])

    verdicts, retried = Counter(), Counter()
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(_gate, cands))
        results_m = list(ex.map(_gate_multi, multi_cands))
    for i, (ok, why) in enumerate(results):
        if not ok:
            retried[why] += 1
            results[i] = _gate(cands[i])
    for i, (ok, why) in enumerate(results_m):
        if not ok:
            retried[why] += 1
            results_m[i] = _gate_multi(multi_cands[i])
    for (prompt, resp, _, ei), (ok, why) in list(zip(cands, results)) + list(zip(multi_cands, results_m)):
        verdicts[why] += 1
        if ok:
            rows.append({"messages": [{"role": "user", "content": prompt},
                                      {"role": "assistant", "content": resp}],
                         "extra_info": ei})
    cands = cands + multi_cands   # for the summary below

    if args.heldout_atomic_per_op > 0:
        heldout_funcs = {ops_mod.func_name_mapping[n] for n in ops_mod.PAPER_EVAL_SET}
        boosted = []
        per_op = Counter()
        for row in rows:
            ei = row["extra_info"]
            if ei.get("ra_family") == "atomic" and ei.get("op") in heldout_funcs:
                per_op[ei["op"]] += 1
        for row in rows:
            ei = row["extra_info"]
            op = ei.get("op")
            if ei.get("ra_family") == "atomic" and op in heldout_funcs and per_op[op] > 0:
                extra = args.heldout_atomic_per_op // per_op[op] - 1
                boosted.extend([row] * max(extra, 0))
        rows.extend(boosted)
        print(f"[ra-sft] heldout_atomic_per_op={args.heldout_atomic_per_op}: base per-op "
              f"{dict(sorted(per_op.items()))} -> +{len(boosted)} duplicated verified rows")

    rng.shuffle(rows)
    os.makedirs(args.out_dir, exist_ok=True)
    val = rows[: args.val_size] if args.val_size > 0 else []
    train = rows[args.val_size:] if args.val_size > 0 else rows
    Dataset.from_list(train).to_parquet(os.path.join(args.out_dir, "train.parquet"))
    if val:
        Dataset.from_list(val).to_parquet(os.path.join(args.out_dir, "test.parquet"))
    fam = Counter(c[3]["ra_family"] for c in cands)
    lens = sorted(len(c[1]) for c in cands)
    print(f"[ra-sft] format={args.format} self_check={args.self_check} candidates={len(cands)} "
          f"families={dict(fam)} verdicts={dict(verdicts)} "
          f"resp_chars(med/p90/max)={lens[len(lens)//2]}/{lens[int(len(lens)*0.9)]}/{lens[-1]} "
          f"-> train={len(train)} val={len(val)} @ {args.out_dir}")
    if args.multi_atomic:
        if args.partner_split != "any":
            print(f"[ra-sft] --partner_split={args.partner_split} partner_reuse={args.partner_reuse}: "
                  f"{n_reused} partner slots filled by re-drawn tasks")
        # measured co-occurrence properties (what RESULTS_PROVENANCE section (3) quotes)
        import audit_multi_atomic_data
        audit_multi_atomic_data.audit(args.out_dir)
    if retried:
        print(f"[ra-sft] first-pass failures re-checked sequentially: {dict(retried)} "
              f"(load-induced timeouts recover here)")
    if verdicts["ok"] != len(cands):
        print("[ra-sft][WARN] some stitched rows failed verification — inspect above.")
        sys.exit(2)


if __name__ == "__main__":
    main()
