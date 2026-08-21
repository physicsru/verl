"""RFT step 1/2: roll out the CURRENT model on Stage-1 (bodies-shown) problems.

Generates ``--n_samples`` completions per problem with vLLM. The base model is
used for iteration 1; later iterations pass the previous RFT checkpoint. The raw
prompt text is fed directly (our base-model format is the concatenate template,
i.e. just the prompt content) — no chat template applied here.

Output parquet (one row per problem) feeds build_rft_data.py:
    {prompt: <str>, responses: [<str>...], reward_model: {...}, extra_info: {...},
     data_source: <str>}

Usage:
    python rollout_stage1.py --model Qwen/Qwen3-4B-Base \
        --in_path data/compositional/paper/stage1_level1/train.parquet \
        --out_path data/compositional/paper/stage1_rft/iter1/rollout.parquet \
        --n_samples 8 --max_problems 4000
"""

import argparse
import os

import pandas as pd
from datasets import Dataset


def _prompt_content(p):
    if isinstance(p, str):
        return p
    try:
        return "".join(m["content"] for m in p)
    except Exception:
        return str(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--in_path", required=True)
    ap.add_argument("--out_path", required=True)
    ap.add_argument("--n_samples", type=int, default=8)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top_p", type=float, default=1.0)
    ap.add_argument("--max_tokens", type=int, default=1024)
    ap.add_argument("--max_model_len", type=int, default=4096)
    ap.add_argument("--max_problems", type=int, default=-1, help="-1 = all (GLOBAL, before sharding)")
    ap.add_argument("--shard_id", type=int, default=0, help="this process's shard (data-parallel rollout)")
    ap.add_argument("--num_shards", type=int, default=1, help="total shards (e.g. #nodes)")
    ap.add_argument("--gpu_memory_utilization", type=float, default=0.85)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    df = pd.read_parquet(args.in_path)
    # Select the SAME global subset on every shard (fixed seed), then take a
    # disjoint stride so the union across shards == the global subset exactly.
    if args.max_problems > 0 and args.max_problems < len(df):
        df = df.sample(n=args.max_problems, random_state=args.seed).reset_index(drop=True)
    if args.num_shards > 1:
        df = df.iloc[args.shard_id :: args.num_shards].reset_index(drop=True)
    prompts = [_prompt_content(p) for p in df["prompt"]]
    print(f"[rollout] shard {args.shard_id}/{args.num_shards}: "
          f"{len(prompts)} problems x {args.n_samples} samples from {args.model}")

    # Import vLLM lazily so the rest of the module is importable without a GPU.
    from vllm import LLM, SamplingParams

    llm = LLM(
        model=args.model,
        gpu_memory_utilization=args.gpu_memory_utilization,
        max_model_len=args.max_model_len,
        seed=args.seed,
    )
    sp = SamplingParams(
        n=args.n_samples,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        seed=args.seed,
    )
    outputs = llm.generate(prompts, sp)

    rows = []
    for i, out in enumerate(outputs):
        r = df.iloc[i]
        rows.append(
            {
                "prompt": prompts[i],
                "responses": [o.text for o in out.outputs],
                "reward_model": {"ground_truth": r["reward_model"]["ground_truth"]},
                "extra_info": dict(r["extra_info"]) if r["extra_info"] is not None else {},
                "data_source": r.get("data_source", "compositional-forward"),
            }
        )
    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)
    Dataset.from_list(rows).to_parquet(args.out_path)
    print(f"[rollout] wrote {len(rows)} rows -> {args.out_path}")


if __name__ == "__main__":
    main()
