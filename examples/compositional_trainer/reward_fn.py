"""Forward-task reward for the compositional-generalization pipeline.

Scores "predict the output of ``main_solution(x)``". Pure-Python: it extracts
the model's predicted output (a JSON ``{"output": ...}`` object, or a
``\\boxed{...}`` fallback) and compares it to the precomputed ``ref_output``.
No code execution / sandbox needed (the forward task is just string equality).

Plug in via:
    reward.custom_reward_function.path=examples/compositional_trainer/reward_fn.py
    reward.custom_reward_function.name=compute_score

Self-contained on purpose (no import of operators/executor) so it loads cleanly
inside verl reward workers regardless of sys.path.
"""

import json
import math
import os
import re
import threading

# ---------------------------------------------------------------------------
# Extraction (adapted from RL-Compositionality verl/utils/reward_score/codeio.py)
# ---------------------------------------------------------------------------


def _sub_extract_last_complete_json(s):
    if '```json' not in s:
        stack = []
        last_json_start = None
        last_json_str = None
        for i, char in enumerate(s):
            if char == '{':
                stack.append(i)
                if last_json_start is None:
                    last_json_start = i
            elif char == '}':
                if stack:
                    start = stack.pop()
                    if not stack:
                        last_json_str = s[last_json_start:i + 1]
                        last_json_start = None
    else:
        last_json_start = s.rfind('```json')
        last_json_end = s.find('```', last_json_start + len('```json'))
        last_json_str = s[last_json_start + 7:last_json_end].strip()

    if last_json_str:
        try:
            return json.loads(last_json_str.replace("\n", ""))
        except json.JSONDecodeError:
            last_json_str = last_json_str.replace("False", "false").replace("True", "true").replace("None", "null")
            try:
                return json.loads(last_json_str.replace("\n", ""))
            except json.JSONDecodeError:
                pass
    return None


def _extract_last_complete_json(s):
    res = _sub_extract_last_complete_json(s)
    if res is None:
        s2 = s.replace("\\{", "{").replace("\\}", "}").replace('(', '[').replace(')', ']')
        res = _sub_extract_last_complete_json(s2)
    if res is None and "\\boxed{" in s:
        boxstart = s.rfind("\\boxed{") + len("\\boxed{")
        boxend = s.rfind("}", boxstart)
        boxcontent = s[boxstart:boxend]
        processed = (boxcontent.replace("\\\\", "\\").replace("\\{", "{").replace("\\}", "}").replace(
            '\\left', '').replace('\\right', ''))
        res = _sub_extract_last_complete_json(processed)
    return res


_BOXED_RE = re.compile(r"\\boxed\{(.*?)\}", re.DOTALL)


def _extract_predicted_output(solution_str):
    """Return the model's predicted output string, or None if unparseable."""
    extracted = _extract_last_complete_json(solution_str)
    if isinstance(extracted, dict) and "output" in extracted:
        return extracted["output"]
    # Fallback: a bare \boxed{...} holding the raw string answer.
    matches = _BOXED_RE.findall(solution_str)
    if matches:
        return matches[-1].strip()
    return None


def _is_close(pred, target, tol=0.001):
    if isinstance(pred, dict) and isinstance(target, dict):
        if pred.keys() != target.keys():
            return False
        return all(_is_close(pred[k], target[k], tol) for k in pred)
    if isinstance(pred, list) and isinstance(target, list):
        if len(pred) != len(target):
            return False
        return all(_is_close(p, t, tol) for p, t in zip(pred, target))
    if isinstance(pred, (int, float)) and isinstance(target, (int, float)) and not isinstance(pred, bool):
        try:
            if isinstance(pred, float) or isinstance(target, float):
                if math.isnan(pred) or math.isnan(target) or math.isinf(pred) or math.isinf(target):
                    return False
                return (abs(pred - target) <= tol * abs(target)) and (int(pred) == int(target))
            return pred == target
        except Exception:
            return False
    return pred == target


# ---------------------------------------------------------------------------
# Sample logging (mirrors lengthgen reward_fn behaviour)
# ---------------------------------------------------------------------------

_print_lock = threading.Lock()
_print_counter: dict = {}
_last_print_time = [0.0]
NUM_EXAMINE = int(os.environ.get("COMPOSITIONAL_NUM_EXAMINE", "3"))
# By default only print VALIDATION samples (split != "train"); set
# COMPOSITIONAL_PRINT_VAL_ONLY=0 to also examine training rollouts.
PRINT_VAL_ONLY = os.environ.get("COMPOSITIONAL_PRINT_VAL_ONLY", "1") not in ("0", "false", "False")


def _maybe_print_sample(extra_info, solution_str, ref_output, predicted, score, ref_code=None, ref_input=None):
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
    # Key per (split, depth) so each eval depth gets its own NUM_EXAMINE quota.
    key = f"{pool}_s{stage}_{split}_d{depth}"
    with _print_lock:
        now = time.time()
        # Validation rounds are far apart (>> 30s); a gap resets the per-round quota.
        if now - _last_print_time[0] > 30:
            _print_counter.clear()
        _last_print_time[0] = now
        count = _print_counter.get(key, 0)
        if count >= NUM_EXAMINE:
            return
        _print_counter[key] = count + 1
        tag = "VAL" if is_val else "TRAIN"
        tail = solution_str[-600:]
        if len(solution_str) > 600:
            tail = "..." + tail
        # Build the whole block as ONE string and emit it in a single print() call.
        # Ray aggregates logs per-record and de-duplicates identical lines across
        # workers; separate print() calls get mangled ("[repeated Nx across
        # cluster]") and mispair REF/PREDICTED. One record per sample avoids that.
        lines = [
            "", "=" * 70,
            f"[{tag} SAMPLE {count + 1}/{NUM_EXAMINE}] pool={pool} stage={stage} "
            f"split={split} depth={depth} score={score:.2f}",
        ]
        if ref_code is not None:
            lines.append(f"[PROGRAM]    {' '.join(str(ref_code).split())}")
        if ref_input is not None:
            lines.append(f"[INPUT]      {ref_input!r}")
        lines += [
            f"[REF OUTPUT] {ref_output!r}",
            f"[PREDICTED]  {predicted!r}",
            f"[RESPONSE TAIL]\n{tail}",
            "=" * 70, "",
        ]
        print("\n".join(lines), flush=True)


# ---------------------------------------------------------------------------
# verl entry point
# ---------------------------------------------------------------------------


def compute_score(data_source, solution_str, ground_truth, extra_info=None, **kwargs):
    """Forward-task score.

    ground_truth: JSON string with at least ``ref_output`` (also ref_input,
    ref_code, funcname) — as emitted by generate_data.py.
    Returns a dict with ``score`` plus diagnostic metrics.
    """
    extra_info = extra_info or {}
    ref_code = ref_input = None
    try:
        gt = json.loads(ground_truth) if isinstance(ground_truth, str) else ground_truth
        ref_output = gt["ref_output"]
        ref_code = gt.get("ref_code")
        ref_input = gt.get("ref_input")
    except Exception:
        ref_output = ground_truth  # last resort: compare against the raw string

    predicted = _extract_predicted_output(solution_str)
    has_answer = 1.0 if predicted is not None else 0.0
    correctness = 1.0 if (predicted is not None and _is_close(predicted, ref_output)) else 0.0

    result = {
        "score": correctness,
        "correctness": correctness,
        "has_answer": has_answer,
        "depth": extra_info.get("depth", -1),
    }
    _maybe_print_sample(extra_info, solution_str, ref_output, predicted, correctness,
                        ref_code=ref_code, ref_input=ref_input)
    return result


if __name__ == "__main__":
    def gt(out):
        return json.dumps({"ref_input": {"x": "abc"}, "ref_output": out, "ref_code": "", "funcname": "main_solution"})

    tests = [
        ('The answer is {"output": "cba"}', gt("cba"), 1.0),
        ('```json\n{"output": "xyz"}\n```', gt("xyz"), 1.0),
        ('blah \\boxed{cba}', gt("cba"), 1.0),
        ('{"output": "cba"}', gt("xyz"), 0.0),
        ('no answer here', gt("cba"), 0.0),
        ('{"output": "abc"} then {"output": "cba"}', gt("cba"), 1.0),  # last JSON wins
        ('{"output": 42}', gt(42), 1.0),
    ]
    ok = True
    for text, g, expected in tests:
        r = compute_score("compositional-forward", text, g, extra_info={"pool": "paper", "stage": 2, "depth": 2})
        status = "PASS" if r["score"] == expected else "FAIL"
        if r["score"] != expected:
            ok = False
        print(f"  [{status}] score={r['score']} expected={expected}  text={text!r:.45}")
    print("All reward_fn tests passed." if ok else "SOME TESTS FAILED")
