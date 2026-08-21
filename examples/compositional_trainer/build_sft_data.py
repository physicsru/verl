"""Build NTP/SFT Stage-1 data for the compositional pipeline (the paper's recipe).

The RL-Compositionality paper acquires atomic skills via NTP/RFT in Stage 1
(*not* RL): it shows the operator definitions and supervises on correct
reasoning traces, so the model memorises ``func_N -> behaviour`` and can later
*recall* held-out operators with the bodies hidden (Stage 2). Our GRPO Stage-1
did not instil that recall (held-out Level-1 ~0.4 vs the paper's ~0.9), which
capped the whole paper-pool baseline. This script produces the SFT data to fix
that.

Faithful RFT samples the base model's own correct rollouts. Generating rollouts
on our multinode setup is heavy, so we use the cheap deterministic analog: take
the existing Stage-1 (bodies-shown, depth-1) problems and attach a short, always
-correct trace ending in the gold ``{"output": ...}``. Over many examples with a
*stable* ``func_N`` naming, NTP learns each operator as a function — the same
mechanism RFT relies on.

Output is the ``messages`` format our SFT trainer expects
(``verl.trainer.sft_trainer`` + ``MultiTurnSFTDataset``):

    {"messages": [{"role": "user", "content": <prompt>},
                  {"role": "assistant", "content": <trace>}],
     "extra_info": {...}}

``--hide_body_frac`` hides the operator bodies in a fraction of the prompts
(reconstructing the Stage-2 body-hidden prompt from ``ref_code``). For those
**closed-book** prompts the assistant target is a *recall trace*: it restates the
``def func_N`` body the prompt no longer shows, then computes. This is the whole
point of the fix — our masked-completion SFT/RFT only trains on the assistant
turn, so with the bodies sitting in the (masked) prompt the model got **zero
gradient on the definitions** and never memorised ``func_N -> behaviour`` (held-out
Level-1 recall stuck ~0.34). Moving the definition into the assistant turn puts it
in the **loss**, closed-book, so recall actually forms in the weights. Run with
``--hide_body_frac 1.0`` for a pure closed-book recall stage.

Usage:
    python build_sft_data.py --pool paper \
        --in_dir  data/compositional/paper/stage1_level1 \
        --out_dir data/compositional/paper/stage1_sft
"""

import argparse
import json
import os
import random

from datasets import Dataset

# Kept identical to generate_data.py / the original string_data.py so a
# body-hidden reconstruction matches what Stage 2 shows.
FORWARD_PROMPT = (
    "You are given a code:\n\n{code}\n\nCan you predict the output of "
    "`main_solution(\"{input}\")` without writing any code? Please reason and "
    "put your final answer in the following json format: {{\"output\": <your "
    "output>}}, where <your output> should be the final string."
)


def _prompt_content(prompt):
    """Stage-1 parquet stores prompt as a list of {role, content} dicts."""
    if isinstance(prompt, str):
        return prompt
    try:
        return "".join(m["content"] for m in prompt)
    except Exception:
        return str(prompt)


def _expr_from_ref_code(ref_code):
    """main_solution body, e.g. 'func_5(\\'jbn\\', \\'ck\\')'.

    For Stage-1 the ref_code inlines the operator definitions too, so main_solution
    is the LAST def and its `return` (the last one) is the composition expr.
    """
    if "def main_solution" in ref_code:
        ref_code = "def main_solution" + ref_code.split("def main_solution", 1)[1]
    if "return" in ref_code:
        return ref_code.rsplit("return", 1)[1].strip()
    return ref_code.strip()


def _hidden_prompt(ref_code, ref_input):
    expr = _expr_from_ref_code(ref_code)
    code = f"def main_solution(x):\n    return {expr}"
    x = ref_input.get("x") if isinstance(ref_input, dict) else ref_input
    return FORWARD_PROMPT.format(code=code, input=x)


def _trace(ref_code, ref_output):
    """Short deterministic, always-correct target trace (bodies-shown case:
    the prompt already shows the code, so the trace can just read + compute)."""
    expr = _expr_from_ref_code(ref_code)
    out = ref_output
    return (
        f"Let me trace `main_solution` step by step.\n"
        f"It returns `{expr}`, which evaluates to {out!r}.\n"
        f"{json.dumps({'output': out})}"
    )


def _split_defs(ref_code):
    """Split ref_code into (operator-definitions text, main_solution block).

    Stage-1 ref_code inlines each ``def func_N`` before ``def main_solution``.
    defs is empty for inlined base-case ops (e.g. ``return (x + 'oss')``).
    """
    marker = "def main_solution"
    if marker in ref_code:
        i = ref_code.index(marker)
        return ref_code[:i].strip(), ref_code[i:]
    return "", ref_code


def _recall_trace(ref_code, ref_output):
    """Closed-book target: RECALL the operator bodies (which the body-hidden
    prompt no longer shows), then compute. Putting the ``def func_N`` text in the
    assistant turn forces it into the SFT loss, so the model memorises
    ``func_N -> body`` and can recall held-out operators with the body hidden —
    the signal masked-prompt SFT/RFT was dropping."""
    defs, _ = _split_defs(ref_code)
    expr = _expr_from_ref_code(ref_code)
    out = ref_output
    if defs:
        return (
            f"Let me recall the operator definitions used by `main_solution`:\n\n"
            f"{defs}\n\n"
            f"So `main_solution` returns `{expr}`, which evaluates to {out!r}.\n"
            f"{json.dumps({'output': out})}"
        )
    # inlined base case: nothing to recall, just compute.
    return (
        f"`main_solution` returns `{expr}`, which evaluates to {out!r}.\n"
        f"{json.dumps({'output': out})}"
    )


def build_split(in_path, hide_body_frac, rng, recall_trace=True):
    import pandas as pd

    df = pd.read_parquet(in_path)
    rows = []
    n_hidden = 0
    for _, r in df.iterrows():
        gt = r["reward_model"]["ground_truth"]
        gt = json.loads(gt) if isinstance(gt, str) else gt
        ref_code = gt["ref_code"]
        ref_output = gt["ref_output"]
        ref_input = gt.get("ref_input", {})

        if hide_body_frac > 0 and rng.random() < hide_body_frac:
            # Closed-book: hide the body in the prompt, RECALL it in the target.
            user = _hidden_prompt(ref_code, ref_input)
            trace = _recall_trace(ref_code, ref_output) if recall_trace else _trace(ref_code, ref_output)
            n_hidden += 1
        else:
            # Bodies shown in the prompt: the trace can just read + compute.
            user = _prompt_content(r["prompt"])
            trace = _trace(ref_code, ref_output)

        ei = dict(r["extra_info"]) if r["extra_info"] is not None else {}
        rows.append(
            {
                "messages": [
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": trace},
                ],
                "extra_info": ei,
            }
        )
    return rows, n_hidden


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="paper")
    ap.add_argument("--in_dir", required=True, help="dir with stage1 train.parquet/test.parquet")
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--hide_body_frac", type=float, default=0.0,
                    help="fraction of prompts with bodies HIDDEN -> closed-book recall target "
                         "(use 1.0 for a pure recall stage)")
    ap.add_argument("--recall_trace", type=lambda s: s.lower() not in ("0", "false", "no"),
                    default=True,
                    help="for hidden prompts, RECALL the def in the target (default True). "
                         "False = shallow I/O-only trace (ablation)")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.out_dir, exist_ok=True)
    for split in ("train", "test"):
        in_path = os.path.join(args.in_dir, f"{split}.parquet")
        if not os.path.exists(in_path):
            print(f"[skip] {in_path} not found")
            continue
        rows, n_hidden = build_split(in_path, args.hide_body_frac, rng, recall_trace=args.recall_trace)
        out_path = os.path.join(args.out_dir, f"{split}.parquet")
        Dataset.from_list(rows).to_parquet(out_path)
        print(f"[{split}] wrote {len(rows)} rows -> {out_path} "
              f"(bodies hidden: {n_hidden}/{len(rows)})")


if __name__ == "__main__":
    main()
