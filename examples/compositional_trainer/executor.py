"""Safe execution of composed string programs -> ground-truth output.

Used by ``generate_data.py`` to compute the reference output of a (possibly
very deep) composition. The forward reward does NOT use this — it only compares
the model's predicted string to the precomputed ``ref_output``.

Guards:
  * wall-clock ``timeout`` (signal-based; generation runs single-threaded in the
    main thread, so SIGALRM is safe here — do NOT reuse this inside a worker
    thread).
  * output ``max_len`` cap — discard expressions whose output blows up (the
    ``paper`` pool has growth operators; ``lenpres`` never triggers this).
  * a bounded recursion limit so ``recursive_reverse`` / ``recursive_interlace``
    on a long string raise ``RecursionError`` (-> discard) instead of segfaulting.

Expressions use the *real* operator names (``sort_chars`` etc.); the opaque
``func_N`` renaming happens only when rendering the prompt, not for execution.
"""

import signal
import sys

# recursive_reverse recurses to depth len(s). For lenpres, len(s) stays ~10, so
# this is never close. For the paper pool with growth ops we cap and discard on
# RecursionError rather than raising the C-stack limit (which can segfault).
_RECURSION_LIMIT = 20000


class _Timeout(Exception):
    pass


def _on_alarm(signum, frame):  # pragma: no cover - signal handler
    raise _Timeout()


def safe_execute(custom_functions, expr, x, max_len=100000, timeout=5):
    """Evaluate ``lambda x: <expr>`` on input ``x`` and return the string output.

    Returns ``None`` (caller should discard the sample) if the expression
    errors, times out, returns a non-string, or exceeds ``max_len``.

    ``custom_functions`` maps real operator names -> functions.
    """
    prev_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(_RECURSION_LIMIT)
    try:
        func = eval(f"lambda x: {expr}", dict(custom_functions))  # noqa: S307 - controlled grammar
    except Exception:
        sys.setrecursionlimit(prev_limit)
        return None

    prev_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.alarm(timeout)
    try:
        out = func(x)
    except (Exception, _Timeout):
        return None
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)
        sys.setrecursionlimit(prev_limit)

    if not isinstance(out, str):
        return None
    if len(out) > max_len:
        return None
    return out


def execute_chain(ops_with_args, x, max_len=100000):
    """Apply a list of ``(fn, args_tuple)`` left-to-right to ``x``.

    A no-eval fast path for unary length-preserving chains (the deep/lenpres
    track). ``args_tuple`` holds the baked constant(s) for parameterized ops,
    or ``()`` for no-arg ops. Returns ``None`` on error / oversize.
    """
    prev_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(_RECURSION_LIMIT)
    try:
        s = x
        for fn, args in ops_with_args:
            s = fn(s, *args)
            if not isinstance(s, str) or len(s) > max_len:
                return None
        return s
    except Exception:
        return None
    finally:
        sys.setrecursionlimit(prev_limit)


if __name__ == "__main__":
    # Empirical check of the central design assumption: length-preserving
    # compositions stay bounded and fast even at depth 100.
    import random
    import time

    import operators as ops

    rng = random.Random(0)
    lp = ops.LENPRES_ALL
    names = list(lp)

    def random_unary_chain(depth):
        chain = []
        for _ in range(depth):
            name = rng.choice(names)
            fn = lp[name]
            if name in ops.LENPRES_PARAM:
                _, lo, hi = ops.PARAM_SPECS[name]
                chain.append((fn, (rng.randint(lo, hi),)))
            else:
                chain.append((fn, ()))
        return chain

    for depth in (1, 2, 3, 10, 100, 500):
        max_out = 0
        t0 = time.time()
        for _ in range(200):
            x = ''.join(rng.choices('abcdefghijklmnopqrstuvwxyz', k=rng.randint(6, 10)))
            out = execute_chain(random_unary_chain(depth), x)
            assert out is not None, f"lenpres chain failed at depth {depth}"
            assert len(out) == len(x), f"NOT length-preserving at depth {depth}: {len(x)}->{len(out)}"
            max_out = max(max_out, len(out))
        dt = time.time() - t0
        print(f"depth={depth:4d}: 200 chains OK, max|out|={max_out}, {dt*1000:.0f} ms total")
    print("OK: length-preserving ops stay length-preserving and fast to depth 500")
