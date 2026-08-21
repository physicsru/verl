"""ONE-SHOT CODE-EXECUTION reward for the compositional-generalization pipeline.

New condition alongside the CoT forward task (reward_fn.py): the model may use
Python, but its program is executed exactly ONCE — at reward time, after the
response is complete — and the model never sees the execution output. Whatever
`main_solution(x)` returns in the model's program IS its answer. This forces
"plan, then commit to one explicit compositional program" instead of either
mental execution (CoT condition) or REPL-style guess-and-check.

How it scores
-------------
  1. take the LAST fenced code block that defines a function (the "action";
     earlier text/blocks are the plan),
  2. run it once in an isolated, resource-limited subprocess,
  3. call the entry function (ground_truth["funcname"], i.e. `main_solution`)
     on the real input ground_truth["ref_input"]["x"],
  4. exact-string-compare the returned value to ground_truth["ref_output"].

In Stage 2 the operator bodies are hidden, so a correct program must
RE-IMPLEMENT every `func_N` from what the model learned in Stage 1 and compose
them — an explicit, executable statement of the composition.

Plug in via:
    reward.custom_reward_function.path=examples/compositional_trainer/reward_fn_codeexec.py
    reward.custom_reward_function.name=compute_score

Self-contained on purpose (no import of operators/executor) so it loads cleanly
inside verl reward workers regardless of sys.path.

Env knobs:
    COMPOSITIONAL_EXEC_TIMEOUT     wall-clock seconds per execution (default 5)
    COMPOSITIONAL_EXEC_MEM_MB      address-space rlimit in the child (default 2048)
    COMPOSITIONAL_EXEC_CPU         CPU-time rlimit (default timeout+1)
    COMPOSITIONAL_FORMAT_BONUS     train-split shaping bonus for plan + exactly one
                                   code block (default 0.05; 0 disables). Never
                                   applied on validation splits, so val score ==
                                   pure accuracy and stays comparable to the CoT run.
    COMPOSITIONAL_STRICT_ONE_BLOCK 1 -> responses with != 1 code block score 0
                                   (default 0: soft — only the bonus is withheld)
    COMPOSITIONAL_NUM_EXAMINE      sample printouts per (split, depth) (default 3)
    COMPOSITIONAL_PRINT_VAL_ONLY   1 (default) -> only print validation samples
"""

import json
import os
import re
import subprocess
import sys
import threading

# ---------------------------------------------------------------------------
# Sandboxed one-shot execution (mirrors lengthgen reward_fn_codeexec.py:
# thread-safe — limits are set INSIDE the child, no preexec_fn / signals)
# ---------------------------------------------------------------------------

EXEC_TIMEOUT_S = float(os.environ.get("COMPOSITIONAL_EXEC_TIMEOUT", "5"))
EXEC_MEM_MB = int(os.environ.get("COMPOSITIONAL_EXEC_MEM_MB", "2048"))
EXEC_CPU_S = int(os.environ.get("COMPOSITIONAL_EXEC_CPU", str(int(EXEC_TIMEOUT_S) + 1)))
FORMAT_BONUS = float(os.environ.get("COMPOSITIONAL_FORMAT_BONUS", "0.05"))
STRICT_ONE_BLOCK = os.environ.get("COMPOSITIONAL_STRICT_ONE_BLOCK", "0") in ("1", "true", "True")
# Refuse to ship absurdly large return values through the pipe (paper-pool
# growth ops legitimately reach ~10M chars; 20M is comfortably above that).
MAX_RETURN_CHARS = 20_000_000

_CODE_BLOCK_RE = re.compile(r"```[ \t]*(?:python|py)?[ \t]*\r?\n(.*?)```", re.DOTALL | re.IGNORECASE)

_EXEC_PREAMBLE = (
    "import resource as _R\n"
    f"_R.setrlimit(_R.RLIMIT_CPU,({EXEC_CPU_S},{EXEC_CPU_S}))\n"
    f"_R.setrlimit(_R.RLIMIT_AS,({EXEC_MEM_MB}*1024*1024,{EXEC_MEM_MB}*1024*1024))\n"
    "_R.setrlimit(_R.RLIMIT_CORE,(0,0))\n"
)

# The driver runs AFTER the model's code, so the LAST sentinel line on stdout is
# always the driver's genuine verdict (a model print()ing a fake sentinel is
# just an elaborate way of returning a literal — same expressive power).
_EXEC_DRIVER_TMPL = (
    "\nimport sys as _S, json as _J, builtins as _B\n"
    "_x = _J.loads(_S.stdin.read())\n"
    "_fn = globals().get({funcname!r})\n"
    "if not callable(_fn):\n"
    "    _B.print('__CEXEC_ERR__ no_entry_function')\n"
    "else:\n"
    "    try:\n"
    "        _r = _fn(_x)\n"
    "        if not isinstance(_r, str):\n"
    "            _B.print('__CEXEC_ERR__ non_string_return:' + type(_r).__name__)\n"
    f"        elif len(_r) > {MAX_RETURN_CHARS}:\n"
    "            _B.print('__CEXEC_ERR__ oversize_return')\n"
    "        else:\n"
    "            _B.print('__CEXEC_RESULT__ ' + _J.dumps(_r))\n"
    "    except _B.BaseException as _e:\n"
    "        _B.print('__CEXEC_ERR__ ' + type(_e).__name__)\n"
)


def _extract_code_blocks(text):
    return _CODE_BLOCK_RE.findall(text)


def _pick_program(blocks):
    """The action = the LAST block that defines a function (else the last block)."""
    for b in reversed(blocks):
        if "def " in b:
            return b
    return blocks[-1] if blocks else None


def _has_plan(text):
    """Non-trivial plain text before the first code fence = the plan."""
    fence = text.find("```")
    head = text if fence < 0 else text[:fence]
    return len(head.strip()) >= 30


def _execute_once(code, funcname, x):
    """Run `code` in an isolated subprocess and call funcname(x) exactly once.

    Returns (returned_str_or_None, error_str_or_None).
    """
    if not str(funcname).isidentifier():
        funcname = "main_solution"
    script = _EXEC_PREAMBLE + code + _EXEC_DRIVER_TMPL.format(funcname=funcname)
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-S", "-c", script],
            input=json.dumps(x),
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except Exception as e:  # noqa: BLE001 - report spawn failures, never raise
        return None, f"spawn_error:{type(e).__name__}"

    result = error = None
    for line in (proc.stdout or "").splitlines():
        if line.startswith("__CEXEC_RESULT__"):
            try:
                result, error = json.loads(line[len("__CEXEC_RESULT__"):].strip()), None
            except json.JSONDecodeError:
                result, error = None, "parse_error"
        elif line.startswith("__CEXEC_ERR__"):
            result, error = None, (line[len("__CEXEC_ERR__"):].strip() or "runtime_error")
    if result is None and error is None:
        # No sentinel at all: top-level model code crashed before the driver ran.
        tail = (proc.stderr or "").strip().splitlines()
        error = f"top_level_error:{tail[-1][:80]}" if tail else "no_output"
    return result, error


# ---------------------------------------------------------------------------
# Sample logging (mirrors reward_fn.py behaviour)
# ---------------------------------------------------------------------------

_print_lock = threading.Lock()
_print_counter: dict = {}
_last_print_time = [0.0]
NUM_EXAMINE = int(os.environ.get("COMPOSITIONAL_NUM_EXAMINE", "3"))
PRINT_VAL_ONLY = os.environ.get("COMPOSITIONAL_PRINT_VAL_ONLY", "1") not in ("0", "false", "False")


def _maybe_print_sample(extra_info, solution_str, ref_output, result, ref_code=None, ref_input=None):
    if NUM_EXAMINE <= 0:
        return
    split = str(extra_info.get("split", "train"))
    is_val = split.lower() != "train"
    if PRINT_VAL_ONLY and not is_val:
        return
    import time
    pool = extra_info.get("pool", "?")
    stage = extra_info.get("stage", "?")
    depth = extra_info.get("depth", "?")
    key = f"cx_{pool}_s{stage}_{split}_d{depth}"
    with _print_lock:
        now = time.time()
        if now - _last_print_time[0] > 30:
            _print_counter.clear()
        _last_print_time[0] = now
        count = _print_counter.get(key, 0)
        if count >= NUM_EXAMINE:
            return
        _print_counter[key] = count + 1
        tag = "VAL" if is_val else "TRAIN"
        # VAL: print the WHOLE trajectory (untruncated) so full plan+program are
        # inspectable in the logs; TRAIN prints (if enabled) stay tail-only.
        if is_val:
            shown = solution_str
            resp_label = "[RESPONSE (full)]"
        else:
            shown = solution_str[-800:]
            if len(solution_str) > 800:
                shown = "..." + shown
            resp_label = "[RESPONSE TAIL]"
        # One print() per sample so Ray's per-record log aggregation can't
        # interleave/mispair lines across workers.
        lines = [
            "", "=" * 70,
            f"[{tag} CX-SAMPLE {count + 1}/{NUM_EXAMINE}] pool={pool} stage={stage} "
            f"split={split} depth={depth} score={result['score']:.2f} "
            f"(exec_ok={result['exec_ok']:.0f} exec_error={result['_exec_error']} "
            f"blocks={result['n_code_blocks']:.0f} plan={result['has_plan']:.0f})",
        ]
        if ref_code is not None:
            lines.append(f"[PROGRAM]    {' '.join(str(ref_code).split())[:300]}")
        if ref_input is not None:
            lines.append(f"[INPUT]      {ref_input!r}")
        lines += [
            f"[REF OUTPUT] {str(ref_output)[:2000]!r}",
            f"[EXECUTED]   {str(result['_exec_result'])[:2000]!r}",
            f"{resp_label}\n{shown}",
            "=" * 70, "",
        ]
        print("\n".join(lines), flush=True)


# ---------------------------------------------------------------------------
# verl entry point
# ---------------------------------------------------------------------------


def compute_score(data_source, solution_str, ground_truth, extra_info=None, **kwargs):
    """One-shot code-exec score.

    ground_truth: JSON string with ref_output, ref_input {"x": ...}, funcname
    (and ref_code, unused for scoring) — as emitted by generate_data.py /
    build_codeexec_data.py. Returns a dict with ``score`` plus diagnostics.
    """
    extra_info = extra_info or {}
    ref_code = ref_input = None
    x = funcname = None
    try:
        gt = json.loads(ground_truth) if isinstance(ground_truth, str) else ground_truth
        ref_output = gt["ref_output"]
        ref_code = gt.get("ref_code")
        ref_input = gt.get("ref_input")
        x = (ref_input or {}).get("x")
        funcname = gt.get("funcname", "main_solution")
    except Exception:
        ref_output = ground_truth

    blocks = _extract_code_blocks(solution_str)
    code = _pick_program(blocks)
    has_code = 1.0 if code is not None and "def " in code else 0.0
    one_block = 1.0 if len(blocks) == 1 else 0.0
    has_plan = 1.0 if _has_plan(solution_str) else 0.0
    follows_format = 1.0 if (has_code and one_block and has_plan) else 0.0

    exec_ok = 0.0
    exec_result = None
    exec_error = None
    correctness = 0.0
    if code is None:
        exec_error = "no_code_block"
    elif x is None:
        exec_error = "no_input_in_ground_truth"
    else:
        exec_result, exec_error = _execute_once(code, funcname, x)
        if exec_result is not None:
            exec_ok = 1.0
            correctness = 1.0 if exec_result == ref_output else 0.0

    if STRICT_ONE_BLOCK and len(blocks) != 1:
        correctness = 0.0
        exec_error = (exec_error or "") + "|strict_multi_block"

    # Shaping bonus on the TRAIN split only — val score stays pure accuracy.
    is_train = str(extra_info.get("split", "train")).lower() == "train"
    score = correctness + (FORMAT_BONUS if (is_train and follows_format) else 0.0)

    result = {
        "score": score,
        "correctness": correctness,
        "has_code": has_code,
        "n_code_blocks": float(len(blocks)),
        "one_block": one_block,
        "has_plan": has_plan,
        "follows_format": follows_format,
        "exec_ok": exec_ok,
        "depth": extra_info.get("depth", -1),
        # underscore keys are for the sample printout only; stripped before return.
        "_exec_result": exec_result if exec_result is not None else "<none>",
        "_exec_error": exec_error or "ok",
    }
    _maybe_print_sample(extra_info, solution_str, ref_output, result,
                        ref_code=ref_code, ref_input=(ref_input or {}).get("x"))
    result.pop("_exec_result", None)
    result.pop("_exec_error", None)
    return result


if __name__ == "__main__":
    def gt(out, x="abc", funcname="main_solution", code=""):
        return json.dumps({"ref_input": {"x": x}, "ref_output": out, "ref_code": code, "funcname": funcname})

    PLAN = "Step 1 - Plan: func_3 sorts the characters; I implement it with sorted().\n"
    good = PLAN + "```python\ndef func_3(s):\n    return ''.join(sorted(s))\n\ndef main_solution(x):\n    return func_3(x)\n```\n"
    two_blocks = PLAN + "```python\ndef helper(s):\n    return s\n```\n" + good.split("Plan")[0] + \
        "```python\ndef main_solution(x):\n    return ''.join(sorted(x))\n```\n"
    hardcoded = PLAN + "```python\ndef main_solution(x):\n    return 'abc'\n```\n"  # guessing = allowed, just wrong here
    crash = PLAN + "```python\ndef main_solution(x):\n    return undefined_name\n```\n"
    top_crash = PLAN + "```python\nraise RuntimeError('boom')\ndef main_solution(x):\n    return x\n```\n"
    loop = PLAN + "```python\ndef main_solution(x):\n    while True:\n        pass\n```\n"
    non_str = PLAN + "```python\ndef main_solution(x):\n    return 42\n```\n"
    fake_sentinel = PLAN + ("```python\nprint('__CEXEC_RESULT__ \"bca\"')\n"
                            "def main_solution(x):\n    return ''.join(sorted(x))\n```\n")
    nocode = "I think the answer is abc."
    newline_out = PLAN + "```python\ndef main_solution(x):\n    return 'a\\nb'\n```\n"

    tests = [
        (good, gt("abc", x="bca"), 1.0, "reimplement + compose, correct"),
        (good, gt("zzz", x="bca"), 0.0, "wrong ground truth"),
        (two_blocks, gt("abc", x="bca"), 1.0, "two blocks: last def-block executed"),
        (hardcoded, gt("abc", x="cab"), 1.0, "hardcoded literal happens to match"),
        (crash, gt("abc"), 0.0, "NameError inside function"),
        (top_crash, gt("abc"), 0.0, "top-level crash before driver"),
        (loop, gt("abc"), 0.0, "infinite loop -> timeout"),
        (non_str, gt("abc"), 0.0, "non-string return"),
        (fake_sentinel, gt("abc", x="bca"), 1.0, "fake sentinel overridden by driver (last wins)"),
        (nocode, gt("abc"), 0.0, "no code block"),
        (newline_out, gt("a\nb"), 1.0, "multiline return survives line protocol"),
    ]
    ok = True
    for text, g, expected, note in tests:
        r = compute_score("compositional-codeexec", text, g,
                          extra_info={"pool": "paper", "stage": 2, "depth": 2, "split": "train"})
        status = "PASS" if r["correctness"] == expected else "FAIL"
        if r["correctness"] != expected:
            ok = False
        print(f"  [{status}] correctness={r['correctness']} score={r['score']:.2f} "
              f"exec_ok={r['exec_ok']:.0f} blocks={r['n_code_blocks']:.0f}  ({note})")
    print("All reward_fn_codeexec tests passed." if ok else "SOME TESTS FAILED")
