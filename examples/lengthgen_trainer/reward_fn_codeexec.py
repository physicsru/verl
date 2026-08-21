"""Reward function for the CODE-EXECUTION ablation (length-generalization GRPO).

This is a BRAND-NEW, standalone pipeline. It does not import or modify the
existing reward_fn.py (cot / code conditions). Use it only for the
`code_exec` runs via:

    reward.custom_reward_function.path=examples/lengthgen_trainer/reward_fn_codeexec.py

How it scores
-------------
The prompt shown to the model is identical to the existing "code" condition
(abstract -> Python function -> apply). The difference is the ANSWER SOURCE:
instead of reading the model's hand-computed \\boxed{} value, we
  1. extract the first fenced code block that defines a function,
  2. execute it in an isolated, resource-limited subprocess,
  3. call it on the real input carried in extra_info["call_args"]
     (a JSON list of positional args), and
  4. compare the program's integer output to the ground truth.

This isolates "can the model write correct code" from "can it mentally run
it", and is length-invariant: a correct function generalizes to any n. Because
the function appears early (Step 2), even responses that truncate during the
verbose Step-3 trace usually still yield a runnable function.

Returns 1.0 for a correct integer answer, 0.0 otherwise; +0.1 method bonus when
the abstract->code->apply form is followed (mirrors the "code" condition so the
two are directly comparable).
"""

import json  # noqa: F401  (kept for symmetry / potential debugging)
import os
import re
import subprocess
import sys
import threading

_BOXED_RE = re.compile(r"\\boxed\{([^}]*)\}")
# Fenced code block: ```python\n ... ``` (language tag optional).
_CODE_BLOCK_RE = re.compile(r"```[ \t]*(?:python|py)?[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)

_print_lock = threading.Lock()
_print_counter: dict[str, int] = {}
_last_print_time: float = 0
NUM_EXAMINE = int(os.environ.get("LENGTHGEN_NUM_EXAMINE", "3"))
FORMAT_BONUS = 0.1

# --- sandbox limits (applied INSIDE the child; thread-safe, no preexec_fn) ---
EXEC_TIMEOUT_S = float(os.environ.get("LENGTHGEN_EXEC_TIMEOUT", "5"))
EXEC_MEM_MB = int(os.environ.get("LENGTHGEN_EXEC_MEM_MB", "2048"))
EXEC_CPU_S = int(os.environ.get("LENGTHGEN_EXEC_CPU", str(int(EXEC_TIMEOUT_S) + 1)))

_EXEC_PREAMBLE = (
    "import resource as _R\n"
    f"_R.setrlimit(_R.RLIMIT_CPU,({EXEC_CPU_S},{EXEC_CPU_S}))\n"
    f"_R.setrlimit(_R.RLIMIT_AS,({EXEC_MEM_MB}*1024*1024,{EXEC_MEM_MB}*1024*1024))\n"
    "_R.setrlimit(_R.RLIMIT_CORE,(0,0))\n"
)
# Prefer a function named `solve`; else the last top-level user-defined function
# (the "code" prompt names solvers e.g. lis_length / knapsack_01 / max_subarray_sum).
_EXEC_DRIVER = (
    "\nimport sys as _S, json as _J, types as _T, builtins as _B\n"
    "_args = _J.loads(_S.stdin.read())\n"
    "_cands = [v for k, v in list(globals().items())\n"
    "          if isinstance(v, _T.FunctionType) and not k.startswith('_')]\n"
    "_fn = globals().get('solve') or (_cands[-1] if _cands else None)\n"
    "if _fn is None:\n"
    "    _B.print('__LGEN_ERR__ no_function')\n"
    "else:\n"
    "    try:\n"
    "        _B.print('__LGEN_RESULT__', int(_fn(*_args)))\n"
    "    except _B.BaseException as _e:\n"
    "        _B.print('__LGEN_ERR__', type(_e).__name__)\n"
)


def _extract_boxed_answer(text: str) -> str | None:
    matches = _BOXED_RE.findall(text)
    if not matches:
        return None
    raw = matches[-1].strip().replace(",", "").replace(" ", "")
    return raw if raw else None


def _extract_code(text: str) -> str | None:
    """First fenced code block that defines a function (else the first block)."""
    blocks = _CODE_BLOCK_RE.findall(text)
    for b in blocks:
        if "def " in b:
            return b
    return blocks[0] if blocks else None


def _execute_code(code: str, call_args_json: str):
    """Run `code` in an isolated subprocess; call its solver on the JSON args.

    Returns (result_int_or_None, error_str_or_None).
    """
    script = _EXEC_PREAMBLE + code + _EXEC_DRIVER
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", "-c", script],
            input=call_args_json,
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception as e:  # noqa: BLE001 - report spawn failures, never raise
        return None, f"spawn_error:{type(e).__name__}"
    for line in (proc.stdout or "").splitlines():
        if line.startswith("__LGEN_RESULT__"):
            try:
                return int(line.split()[1]), None
            except (IndexError, ValueError):
                return None, "parse_error"
        if line.startswith("__LGEN_ERR__"):
            return None, line[len("__LGEN_ERR__"):].strip() or "runtime_error"
    return None, "no_output"


def _maybe_print_sample(extra_info, solution_str, ground_truth, score_dict):
    if NUM_EXAMINE <= 0:
        return
    import time
    global _last_print_time
    task = extra_info.get("task", "?")
    condition = extra_info.get("condition", "code_exec")
    n = extra_info.get("n", "?")
    key = f"{task}_{condition}"
    with _print_lock:
        now = time.time()
        if now - _last_print_time > 30:
            _print_counter.clear()
        _last_print_time = now
        count = _print_counter.get(key, 0)
        if count >= NUM_EXAMINE:
            return
        _print_counter[key] = count + 1
        print(f"\n{'='*70}")
        print(f"[SAMPLE {count+1}/{NUM_EXAMINE}] task={task} condition={condition} n={n}")
        print(f"[GROUND TRUTH] {ground_truth}")
        print(f"[SCORE] {score_dict['score']:.2f} (correctness={score_dict['correctness']:.0f} "
              f"has_code={score_dict['has_code']:.0f} follows_method={score_dict['follows_method']:.0f} "
              f"exec_ok={score_dict['exec_ok']:.0f} exec_result={score_dict['_exec_result']} "
              f"exec_error={score_dict['_exec_error']})")
        resp_tail = solution_str[-800:] if len(solution_str) > 800 else solution_str
        if len(solution_str) > 800:
            resp_tail = "..." + resp_tail
        print(f"[RESPONSE TAIL]\n{resp_tail}")
        print(f"{'='*70}\n")


def compute_score(data_source, solution_str, ground_truth, extra_info=None, **kwargs):
    extra_info = extra_info or {}
    n = extra_info.get("n", -1)
    task = extra_info.get("task", "unknown")

    # format flags (same definitions as the "code" condition, for comparability)
    has_code = 1.0 if "```python" in solution_str and "def " in solution_str else 0.0
    has_abstract = 1.0 if "abstract" in solution_str.lower() or "general" in solution_str.lower() else 0.0
    has_apply = 1.0 if "apply" in solution_str.lower() or "applying" in solution_str.lower() else 0.0
    follows_method = 1.0 if has_code and has_apply else 0.0
    has_boxed = 1.0 if _extract_boxed_answer(solution_str) is not None else 0.0

    code = _extract_code(solution_str)
    call_args = extra_info.get("call_args")
    exec_ok = 0.0
    exec_result = None
    exec_error = None
    correctness = 0.0

    if code is None:
        exec_error = "no_code_block"
    elif call_args is None:
        exec_error = "no_call_args"
    else:
        exec_result, exec_error = _execute_code(code, call_args)
        if exec_result is not None:
            exec_ok = 1.0
            try:
                correctness = 1.0 if int(exec_result) == int(ground_truth) else 0.0
            except (ValueError, TypeError):
                correctness = 0.0

    if correctness > 0 and follows_method:
        score = correctness + FORMAT_BONUS
    else:
        score = correctness

    result = {
        "score": score,
        "n": n,
        "task": task,
        "correctness": correctness,
        "has_code": has_code,
        "has_boxed": has_boxed,
        "has_abstract": has_abstract,
        "follows_method": follows_method,
        "exec_ok": exec_ok,
        # underscore keys are for the sample printout only; stripped before return.
        "_exec_result": exec_result if exec_result is not None else -1,
        "_exec_error": exec_error or "ok",
    }
    _maybe_print_sample(extra_info, solution_str, ground_truth, result)
    result.pop("_exec_result", None)
    result.pop("_exec_error", None)
    return result


if __name__ == "__main__":
    lis_code = (
        "Step 1 - Abstract: longest strictly increasing subsequence.\n"
        "Step 2 - Code:\n```python\n"
        "def lis_length(arr):\n"
        "    n = len(arr); dp = [1]*n\n"
        "    for i in range(1, n):\n"
        "        for j in range(i):\n"
        "            if arr[j] < arr[i]: dp[i] = max(dp[i], dp[j]+1)\n"
        "    return max(dp)\n"
        "```\nStep 3 - Apply: \\boxed{999}\n"  # deliberately WRONG boxed value
    )
    knap_code = (
        "```python\n"
        "def knapsack_01(items, W):\n"
        "    n = len(items); dp = [[0]*(W+1) for _ in range(n+1)]\n"
        "    for i in range(1, n+1):\n"
        "        w, v = items[i-1]\n"
        "        for c in range(W+1):\n"
        "            dp[i][c] = dp[i-1][c]\n"
        "            if c >= w: dp[i][c] = max(dp[i][c], dp[i-1][c-w]+v)\n"
        "    return dp[n][W]\n```\napplying it\n"
    )
    infinite = "```python\ndef solve(arr):\n    while True:\n        pass\n```\napply"
    syntax = "```python\ndef solve(arr)\n    return 1\n```\napply"
    nocode = "I think the answer is 5."

    tests = [
        (lis_code, "3", json.dumps([[3, 1, 2, 5, 4]]), 1.0, "lis correct (boxed was wrong!)"),
        (lis_code, "4", json.dumps([[3, 1, 2, 5, 4]]), 0.0, "lis wrong gt"),
        (knap_code, "7", json.dumps([[[2, 3], [3, 4], [4, 5], [5, 6]], 5]), 1.0, "knapsack correct"),
        (infinite, "1", json.dumps([[1, 2, 3]]), 0.0, "infinite loop -> timeout"),
        (syntax, "1", json.dumps([[1, 2, 3]]), 0.0, "syntax error"),
        (nocode, "5", json.dumps([[1]]), 0.0, "no code block"),
    ]
    for text, gt, args, expect, note in tests:
        r = compute_score("dp_lengthgen", text, gt,
                          extra_info={"condition": "code_exec", "task": "lis", "n": 5, "call_args": args})
        status = "PASS" if abs(r["correctness"] - expect) < 1e-6 else "FAIL"
        print(f"  [{status}] correctness={r['correctness']} score={r['score']:.2f} exec_ok={r['exec_ok']:.0f}  ({note})")
    print("All reward_fn_codeexec tests done.")
