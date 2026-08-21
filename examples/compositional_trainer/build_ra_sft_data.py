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

Two row families, one output dataset:
  - COMPS  (train ops only, depth 2-4, from stage2_level1to4_codeexec):
      one recall episode per distinct func + Assemble block. Teaches
      multi-episode emission — the failing channel.
  - ATOMICS (ALL 25 ops, depth 1, from stage15_closedbook_codeexec prompts):
      single recall episode + Assemble. Held-out ops thereby practice the RA
      episode shape ATOMICALLY (never inside a composition — the held-out
      purity of the benchmark is preserved), so at eval time "a held-out op's
      episode inside an RA answer" is in-distribution.

Every stitched row is verified with the SAME gate used for RFT rollouts
(build_ra_rft_data.check_response): full-program execution + per-episode unit
tests. Correct by construction, verified anyway.

Usage:
    python examples/compositional_trainer/build_ra_sft_data.py \
        --comp_path data/compositional/paper/stage2_level1to4_codeexec/train.parquet \
        --atomic_path data/compositional/paper/stage15_closedbook_codeexec/train.parquet \
        --out_dir data/compositional/paper/ra_rft/sft_bootstrap \
        --n_comp 16000 --n_atomic 10000
"""

import argparse
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
from build_ra_rft_data import check_response  # noqa: E402

_FUNC_RE = re.compile(r"func_\d+")
_N_TO_NAME = {v: k for k, v in ops_mod.func_name_mapping.items()}
_SKEL_RE = re.compile(r"You are given a code:\n\n(.*?)\n\nYour task", re.DOTALL)
_INPUT_RE = re.compile(r"`main_solution\(\"(.*?)\"\)`")


def gloss(func_n):
    """One-sentence semantics = the reference docstring (stage15's phrasing)."""
    src = renamed_source(func_n and _N_TO_NAME[func_n] or "")
    m = re.search(r'"""(.*?)"""', src, re.DOTALL)
    return m.group(1).strip().splitlines()[0] if m else "as learned in training."


def stitch(skeleton, funcs):
    """RA-format response for `skeleton` needing `funcs` (order of appearance)."""
    defs = [renamed_source(_N_TO_NAME[fn]) for fn in funcs]
    parts = ["Step 1 - Plan: I will recall each helper function in isolation, "
             "then assemble the final program.\n"]
    for fn, d in zip(funcs, defs):
        parts.append(f"Recall {fn}: {gloss(fn)}\n```python\n{d}\n```")
    imports = "from math import gcd\n\n" if "func_0" in funcs else ""
    body = "\n\n".join(defs)
    parts.append("Assemble:\n```python\n" + imports + body + "\n\n\n" + skeleton.strip() + "\n```")
    return "\n".join(parts)


def ordered_funcs(skeleton):
    return sorted(set(_FUNC_RE.findall(skeleton)), key=skeleton.index)


def atomic_ground_truth(skeleton, ref_input):
    """Execute the reference skeleton to synthesize a gt json for verification."""
    ns = {"gcd": __import__("math").gcd}
    for fn in ordered_funcs(skeleton):
        exec(renamed_source(_N_TO_NAME[fn]), ns)  # noqa: S102 - our own reference code
    exec(skeleton, ns)  # noqa: S102
    out = ns["main_solution"](ref_input)
    return json.dumps({"ref_input": {"x": ref_input}, "ref_output": out,
                       "ref_code": skeleton, "funcname": "main_solution"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comp_path", required=True)
    ap.add_argument("--atomic_path", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--n_comp", type=int, default=16000, help="0 = atomics only")
    ap.add_argument("--min_comp_depth", type=int, default=2)
    ap.add_argument("--max_comp_depth", type=int, default=4,
                    help="depth-range ablation knob (WALKTHROUGH §15)")
    ap.add_argument("--n_atomic", type=int, default=10000)
    ap.add_argument("--val_size", type=int, default=256)
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    cands = []   # (user_prompt, response, gt_json, extra_info)

    cdf = pd.read_parquet(args.comp_path)
    cdf = cdf[[args.min_comp_depth <= int(e["depth"]) <= args.max_comp_depth
               for e in cdf["extra_info"]]]
    cdf = cdf.sample(n=min(args.n_comp, len(cdf)), random_state=args.seed)
    for _, r in cdf.iterrows():
        gt_json = r["reward_model"]["ground_truth"]
        skeleton = json.loads(gt_json)["ref_code"]
        funcs = ordered_funcs(skeleton)
        if not funcs:
            continue
        prompt = r["prompt"][0]["content"] if not isinstance(r["prompt"], str) else r["prompt"]
        ei = dict(r["extra_info"]); ei["condition"] = "recall_assemble_sft"
        cands.append((prompt, stitch(skeleton, funcs), gt_json, ei))

    adf = pd.read_parquet(args.atomic_path)
    adf = adf.sample(n=min(args.n_atomic, len(adf)), random_state=args.seed)
    for _, r in adf.iterrows():
        prompt = r["messages"][0]["content"]
        skel_m, in_m = _SKEL_RE.search(prompt), _INPUT_RE.search(prompt)
        if not skel_m or not in_m:
            continue
        skeleton = skel_m.group(1)
        funcs = ordered_funcs(skeleton)
        if not funcs:
            continue
        gt_json = atomic_ground_truth(skeleton, in_m.group(1))
        ei = dict(r["extra_info"]); ei["condition"] = "recall_assemble_sft"
        cands.append((prompt, stitch(skeleton, funcs), gt_json, ei))

    # Verify every stitched row with the RFT gate.
    verdicts = Counter()
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for (prompt, resp, gt_json, ei), (ok, why) in zip(
                cands, ex.map(lambda c: check_response(c[1], c[2], "compositional-codeexec-ra", c[3]),
                              cands)):
            verdicts[why] += 1
            if ok:
                rows.append({"messages": [{"role": "user", "content": prompt},
                                          {"role": "assistant", "content": resp}],
                             "extra_info": ei})

    rng.shuffle(rows)
    os.makedirs(args.out_dir, exist_ok=True)
    val = rows[: args.val_size] if args.val_size > 0 else []
    train = rows[args.val_size:] if args.val_size > 0 else rows
    Dataset.from_list(train).to_parquet(os.path.join(args.out_dir, "train.parquet"))
    if val:
        Dataset.from_list(val).to_parquet(os.path.join(args.out_dir, "test.parquet"))
    print(f"[ra-sft] candidates={len(cands)} verdicts={dict(verdicts)} "
          f"-> train={len(train)} val={len(val)} @ {args.out_dir}")
    if verdicts["ok"] != len(cands):
        print("[ra-sft][WARN] some stitched rows failed verification — inspect above.")


if __name__ == "__main__":
    main()
