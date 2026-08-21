"""Generate parquet datasets for the compositional-generalization pipeline.

Forward task: "predict the output of ``main_solution(x)``". Mirrors the row
schema of RL-Compositionality's ``string_data.py`` (so the ``paper`` pool is a
faithful baseline) but is pool-aware and supports the length-preserving deep
track.

Stage 1 (``--stage 1``): operator bodies are INLINED in the prompt -> the model
learns the atomic skills. Uses the pool's ``all`` split.
Stage 2 (``--stage 2``): only ``def main_solution(x): return <expr>`` is shown,
bodies HIDDEN -> the model must recall+compose. ``--split train`` uses the
train ops, ``--split test`` uses the disjoint held-out ops.

Examples
--------
# Baseline (paper pool), faithful to string_data.py:
python generate_data.py --pool paper --stage 1 --split train --min_level 1 --max_level 1 \
    --data_num 50000 --save_path data/compositional/paper/stage1_level1/train.parquet
python generate_data.py --pool paper --stage 2 --split train --min_level 1 --max_level 2 \
    --data_num 50000 --save_path data/compositional/paper/stage2_level1to2/train.parquet
python generate_data.py --pool paper --stage 2 --split test --min_level 1 --max_level 8 \
    --data_num 2048 --save_path data/compositional/paper/stage2_level1to8/test.parquet

# Deep track (length-preserving), held-out ops at depth 100:
python generate_data.py --pool lenpres --stage 2 --split test --min_level 100 --max_level 100 \
    --data_num 512 --save_path data/compositional/lenpres/eval_depth100/test.parquet
"""

import argparse
import inspect
import json
import os
import random
import string

import datasets

import operators as ops_mod
from executor import safe_execute

FORWARD_PROMPT = (
    "You are given a code:\n\n{code}\n\nCan you predict the output of "
    "`main_solution(\"{input}\")` without writing any code? Please reason and "
    "put your final answer in the following json format: {{\"output\": <your "
    "output>}}, where <your output> should be the final string."
)


# ---------------------------------------------------------------------------
# Expression builders
# ---------------------------------------------------------------------------

def _rand_literal(rng, k_lo=3, k_hi=6):
    return ''.join(rng.choices(string.ascii_lowercase, k=rng.randint(k_lo, k_hi)))


def random_expr_paper(depth, custom_functions, rng):
    """Port of string_data.random_expr — random nested expr over ``custom_functions``.

    Constants are baked at generation time so the final program is deterministic.
    """
    if depth == 0:
        if rng.random() < 0.5:
            return "x"
        return f"'{_rand_literal(rng)}'"

    if rng.random() < 0.2:  # binary branch
        left = random_expr_paper(depth - 1, custom_functions, rng)
        right = random_expr_paper(depth - 1, custom_functions, rng)
        if rng.random() < 0.5:
            return f"({left} + {right})"
        if "interlace_str" in custom_functions:
            return f"interlace_str({left}, {right})"
        if "recursive_interlace" in custom_functions:
            return f"recursive_interlace({left}, {right})"
        return f"({left} + {right})"

    # unary branch
    r = rng.random()
    if r < 0.02:
        op = rng.choice(["upper", "lower", "capitalize", "swapcase"])
        sub = random_expr_paper(depth - 1, custom_functions, rng)
        return f"({sub}).{op}()"

    no_param = [
        "deterministic_shuffle", "remove_vowels", "sort_chars", "reverse_words", "mirror_str", "alternate_case",
        "vowel_to_number", "duplicate_every_char", "fancy_brackets", "compress_repeats", "recursive_reverse",
        "loop_filter_nonalpha", "verify_even_length",
    ]
    param = [
        "repeat_str", "add_prefix", "add_suffix", "rotate_str", "shift_chars", "insert_separator",
        "while_rotate", "loop_concat", "backchain_add_digit", "backchain_palindrome",
    ]
    no_param = [x for x in no_param if x in custom_functions]
    param = [x for x in param if x in custom_functions]

    if (rng.random() < 0.5 and no_param) or not param:
        op = rng.choice(no_param)
        return f"{op}({random_expr_paper(depth - 1, custom_functions, rng)})"

    op = rng.choice(param)
    sub = random_expr_paper(depth - 1, custom_functions, rng)
    if op == "repeat_str":
        return f"repeat_str({sub}, {rng.randint(2, 4)})"
    if op == "add_prefix":
        return f"add_prefix({sub}, '{_rand_literal(rng, 2, 4)}')"
    if op == "add_suffix":
        return f"add_suffix({sub}, '{_rand_literal(rng, 2, 4)}')"
    if op == "rotate_str":
        return f"rotate_str({sub}, {rng.randint(1, 3)})"
    if op == "shift_chars":
        return f"shift_chars({sub}, {rng.randint(1, 5)})"
    if op == "insert_separator":
        return f"insert_separator({sub}, '{rng.choice(['-', '_', '|'])}')"
    if op == "while_rotate":
        return f"while_rotate({sub}, {rng.randint(1, 3)})"
    if op == "loop_concat":
        return f"loop_concat({sub}, {rng.randint(2, 4)})"
    if op == "backchain_add_digit":
        return f"backchain_add_digit({sub}, {rng.randint(1, 3)})"
    if op == "backchain_palindrome":
        return f"backchain_palindrome({sub}, {rng.randint(1, 3)})"
    return "x"


def random_expr_unary(depth, custom_functions, rng):
    """Length-preserving deep track: unary-wrap x exactly ``depth`` times.

    Every op is unary and length-preserving, so |output| == |input| at any
    depth. Parameterized ops get a baked numeric constant.
    """
    names = list(custom_functions)
    expr = "x"
    for _ in range(depth):
        name = rng.choice(names)
        if name in ops_mod.LENPRES_PARAM:
            _, lo, hi = ops_mod.PARAM_SPECS[name]
            expr = f"{name}({expr}, {rng.randint(lo, hi)})"
        else:
            expr = f"{name}({expr})"
    return expr


def build_expr(pool, depth, custom_functions, rng):
    if depth == 0:
        return "x"
    if pool == "lenpres":
        return random_expr_unary(depth, custom_functions, rng)
    return random_expr_paper(depth, custom_functions, rng)


# ---------------------------------------------------------------------------
# Full-code rendering (stage 1 shows bodies, stage 2 hides them) + renaming
# ---------------------------------------------------------------------------

def generate_full_code(expr, custom_functions, stage):
    used = [name for name in custom_functions if name in expr]
    if stage == 1:
        parts = []
        for name in used:
            try:
                parts.append(inspect.getsource(custom_functions[name]))
            except Exception:
                pass
        full_code = "\n\n".join(parts) + f"\n\ndef main_solution(x):\n    return {expr}"
    else:
        full_code = f"def main_solution(x):\n    return {expr}"
    # Rename real names -> opaque func_N everywhere (incl. recursive calls).
    for real, mapped in ops_mod.func_name_mapping.items():
        full_code = full_code.replace(real, mapped)
    return full_code


def generate_feasible_input(custom_functions, expr, rng, attempts=100, min_len=3, max_len=10,
                            max_output_len=100000):
    for _ in range(attempts):
        x = ''.join(rng.choices(string.ascii_lowercase, k=rng.randint(min_len, max_len)))
        if safe_execute(custom_functions, expr, x, max_len=max_output_len) is not None:
            return x
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pool", choices=list(ops_mod.POOLS), required=True)
    p.add_argument("--stage", type=int, choices=[1, 2], required=True)
    p.add_argument("--split", choices=["train", "test"], required=True)
    p.add_argument("--min_level", type=int, default=1)
    p.add_argument("--max_level", type=int, default=1)
    p.add_argument("--data_num", type=int, default=50000)
    p.add_argument("--min_input_len", type=int, default=3)
    p.add_argument("--max_input_len", type=int, default=10)
    p.add_argument("--max_output_len", type=int, default=None,
                   help="discard (and retry) any composition whose output exceeds this many chars. "
                        "Default is pool-aware: paper -> 10_000_000 (faithful baseline: no real sample is "
                        "filtered, just an OOM-safe ceiling), lenpres -> 100_000 (never fires; "
                        "output length == input length). Pass an explicit value to override.")
    p.add_argument("--dedup", choices=["program", "program_input"], default=None,
                   help="program = unique programs only, one input each (faithful to string_data.py; "
                        "fine for large pools like paper). program_input = unique (program,input) pairs "
                        "so each skill is seen on many inputs (needed for small pools like lenpres, which "
                        "have few unique programs at shallow depth). Default: paper->program, lenpres->program_input.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--save_path", required=True)
    args = p.parse_args()

    # Pool-aware default output cap. Paper baseline is faithful (no real sample
    # filtered; ceiling only guards against pathological OOM at extreme depth).
    # lenpres never hits the cap (output length == input length).
    if args.max_output_len is None:
        args.max_output_len = 10_000_000 if args.pool == "paper" else 100_000
    # Small pools (lenpres) have few unique programs at shallow depth -> need
    # input diversity; large pools (paper) keep program-level dedup for fidelity.
    if args.dedup is None:
        args.dedup = "program" if args.pool == "paper" else "program_input"
    print(f"[config] pool={args.pool} dedup={args.dedup} max_output_len={args.max_output_len:,}")

    # Stage 1 = atomic skills over the pool's full op set; stage 2 uses the
    # train ops for --split train and the disjoint held-out ops for --split test.
    op_split = "all" if args.stage == 1 else ("train" if args.split == "train" else "eval")
    custom_functions = ops_mod.get_ops(args.pool, op_split)

    depths = list(range(args.min_level, args.max_level + 1))
    assert args.data_num % len(depths) == 0, \
        f"--data_num {args.data_num} must be divisible by #levels {len(depths)}"
    num_per_depth = args.data_num // len(depths)

    rng = random.Random(args.seed)
    rows = []
    generated = set()
    for depth in depths:
        count = 0
        tries = 0
        n_dup = n_no_input = n_discard = 0  # transparency: why tries were spent
        max_tries = num_per_depth * 200 + 1000
        print(f"[{args.pool}] stage{args.stage} {args.split}: generating depth {depth} ...")
        while count < num_per_depth and tries < max_tries:
            tries += 1
            expr = build_expr(args.pool, depth, custom_functions, rng)
            # In program-dedup mode, skip a seen program before the costly input
            # search. In program_input mode we keep sampling new inputs per program.
            if args.dedup == "program" and expr in generated:
                n_dup += 1
                continue
            x = generate_feasible_input(custom_functions, expr, rng,
                                        min_len=args.min_input_len, max_len=args.max_input_len,
                                        max_output_len=args.max_output_len)
            if x is None:
                n_no_input += 1
                continue
            output = safe_execute(custom_functions, expr, x, max_len=args.max_output_len)
            if output is None:  # oversize (> max_output_len) / error / timeout -> retry
                n_discard += 1
                continue
            key = expr if args.dedup == "program" else (expr, x)
            if key in generated:
                n_dup += 1
                continue
            generated.add(key)
            full_code = generate_full_code(expr, custom_functions, args.stage)
            rows.append({
                "data_source": f"compositional-forward-{args.pool}-depth{depth}",
                "prompt": [{"role": "user", "content": FORWARD_PROMPT.format(code=full_code, input=x)}],
                "ability": "reasoning",
                "reward_model": {
                    "style": "rule",
                    "ground_truth": json.dumps({
                        "ref_input": {"x": x},
                        "ref_output": output,
                        "ref_code": full_code,
                        "funcname": "main_solution",
                    }),
                },
                "extra_info": {
                    "index": len(rows),
                    "pool": args.pool,
                    "stage": args.stage,
                    "split": args.split,
                    "depth": depth,
                },
            })
            count += 1
            if count % 1000 == 0:
                print(f"  depth {depth}: {count}/{num_per_depth}")
        print(f"  depth {depth}: kept={count}/{num_per_depth} | discarded(oversize/err)={n_discard} "
              f"no_feasible_input={n_no_input} duplicate={n_dup} (tries={tries})")
        if count < num_per_depth:
            print(f"  WARNING depth {depth}: only {count}/{num_per_depth} unique samples "
                  f"after {tries} tries (operator pool too small / max_output_len too low for this depth)")

    os.makedirs(os.path.dirname(os.path.abspath(args.save_path)), exist_ok=True)
    ds = datasets.Dataset.from_list(rows)
    ds.to_parquet(args.save_path)
    print(f"Saved {len(ds)} rows -> {args.save_path}")
    if rows:
        print("\n--- sample prompt ---")
        print(rows[len(rows) // 2]["prompt"][0]["content"][:1200])


if __name__ == "__main__":
    main()
