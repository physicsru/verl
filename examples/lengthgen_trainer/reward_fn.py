"""Custom reward function for length-generalization GRPO training.

Extracts \\boxed{answer} from model response and compares to ground truth.
Returns 1.0 for correct, 0.0 for incorrect or unparseable.
+0.1 bonus for following the abstract→code→apply method (code condition only).

Plug in via:
    reward.custom_reward_function.path=examples/lengthgen_trainer/reward_fn.py
"""

import os
import re
import threading

_BOXED_RE = re.compile(r"\\boxed\{([^}]*)\}")

_print_lock = threading.Lock()
_print_counter: dict[str, int] = {}
_last_print_time: float = 0
NUM_EXAMINE = int(os.environ.get("LENGTHGEN_NUM_EXAMINE", "3"))


def _extract_boxed_answer(text: str) -> str | None:
    matches = _BOXED_RE.findall(text)
    if not matches:
        return None
    raw = matches[-1].strip().replace(",", "").replace(" ", "")
    return raw if raw else None


def _maybe_print_sample(extra_info, solution_str, ground_truth, score_dict):
    """Print first NUM_EXAMINE samples per (task, condition) per batch."""
    if NUM_EXAMINE <= 0:
        return
    import time
    global _last_print_time
    task = extra_info.get("task", "?")
    condition = extra_info.get("condition", "?")
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
              f"has_code={score_dict['has_code']:.0f} follows_method={score_dict['follows_method']:.0f})")
        # Print last 800 chars of response to see the answer portion
        resp_tail = solution_str[-800:] if len(solution_str) > 800 else solution_str
        if len(solution_str) > 800:
            resp_tail = "..." + resp_tail
        print(f"[RESPONSE TAIL]\n{resp_tail}")
        print(f"{'='*70}\n")


FORMAT_BONUS = 0.1


def compute_score(data_source, solution_str, ground_truth, extra_info=None, **kwargs):
    extracted = _extract_boxed_answer(solution_str)
    if extracted is None:
        correctness = 0.0
    else:
        try:
            correctness = 1.0 if int(extracted) == int(ground_truth) else 0.0
        except (ValueError, TypeError):
            correctness = 0.0

    extra_info = extra_info or {}
    condition = extra_info.get("condition", "cot")
    n = extra_info.get("n", -1)
    task = extra_info.get("task", "unknown")

    has_code = 1.0 if "```python" in solution_str and "def " in solution_str else 0.0
    has_boxed = 1.0 if extracted is not None else 0.0
    has_abstract = 1.0 if "abstract" in solution_str.lower() or "general" in solution_str.lower() else 0.0
    has_apply = 1.0 if "apply" in solution_str.lower() or "applying" in solution_str.lower() else 0.0
    follows_method = 1.0 if has_code and has_apply else 0.0

    # For the code condition: small bonus for following the 3-step method
    if condition == "code" and correctness > 0 and follows_method:
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
    }
    _maybe_print_sample(extra_info, solution_str, ground_truth, result)
    return result


if __name__ == "__main__":
    tests = [
        (r"The answer is \boxed{42}", "42", 1.0),
        (r"dp = [3,2,6], max = 6. \boxed{6}", "6", 1.0),
        (r"\boxed{-5}", "-5", 1.0),
        (r"\boxed{10} but actually \boxed{12}", "12", 1.0),
        (r"No boxed answer here", "42", 0.0),
        (r"\boxed{wrong}", "42", 0.0),
        (r"\boxed{}", "42", 0.0),
        (r"\boxed{42}", "43", 0.0),
    ]
    for text, gt, expected in tests:
        result = compute_score("dp_lengthgen", text, gt)
        score = result["score"] if isinstance(result, dict) else result
        status = "PASS" if score == expected else "FAIL"
        print(f"  [{status}] score={score}  (gt={gt}, text={text!r:.50})")
    print("All reward_fn tests done.")
