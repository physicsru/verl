"""Pluggable top-K selection for the self-play curriculum (Phase 2/3 interface).

Each layer the questioner expands every question ``q in C`` into ``n_questioner``
deeper candidates. ``select_candidates`` prunes the expanded pool back to a
constant beam width N for the next layer.

The baseline ships only the ``random`` policy (the user's v1: one random
expansion per parent, so the beam stays width-N and every lineage survives).
Smarter policies — frontier-targeting / learning-progress / diversity — register
here later without touching callers.

A candidate is any object carrying a ``parent_id`` (which q it came from) and,
optionally for adaptive policies, a ``solver_acc`` estimate.
"""

import random
from collections import defaultdict

_POLICIES = {}


def register_policy(name):
    def deco(fn):
        _POLICIES[name] = fn
        return fn
    return deco


def _group_by_parent(candidates, parent_key):
    groups = defaultdict(list)
    for c in candidates:
        groups[parent_key(c)].append(c)
    return groups


@register_policy("random")
def _select_random(candidates, size, parent_key, rng, **kwargs):
    """One random expansion per parent (lineage-preserving, constant width).

    If #parents < size, top up with extra random picks; if #parents > size,
    sample ``size`` parents and take one each.
    """
    groups = _group_by_parent(candidates, parent_key)
    parents = list(groups)
    rng.shuffle(parents)
    chosen = [rng.choice(groups[p]) for p in parents[:size]]
    if len(chosen) < size:  # fewer parents than target -> top up
        pool = [c for c in candidates if c not in chosen]
        rng.shuffle(pool)
        chosen += pool[: size - len(chosen)]
    return chosen[:size]


@register_policy("frontier")
def _select_frontier(candidates, size, parent_key, rng, target_acc=0.5, **kwargs):
    """Placeholder for an adaptive curriculum: prefer candidates whose estimated
    solver accuracy is nearest ``target_acc`` (max learning-progress), while
    still guaranteeing >=1 per parent. Requires ``solver_acc`` on candidates.

    Not the baseline default — wired as the seam for Phase 3.
    """
    groups = _group_by_parent(candidates, parent_key)
    chosen = []
    # Guarantee one (closest-to-frontier) per parent first.
    for p, group in groups.items():
        group_sorted = sorted(group, key=lambda c: abs(_acc(c) - target_acc))
        chosen.append(group_sorted[0])
    # Fill/trim toward width N by global frontier proximity.
    rest = [c for c in candidates if c not in chosen]
    rest.sort(key=lambda c: abs(_acc(c) - target_acc))
    chosen = (chosen + rest)[:size] if len(chosen) < size else \
        sorted(chosen, key=lambda c: abs(_acc(c) - target_acc))[:size]
    return chosen


def _acc(c):
    if isinstance(c, dict):
        return c.get("solver_acc", 1.0)
    return getattr(c, "solver_acc", 1.0)


def select_candidates(candidates, size, policy="random", parent_key=None, seed=0, **kwargs):
    """Select ``size`` candidates for the next curriculum layer.

    candidates : iterable of candidate items (dicts or objects)
    size       : target beam width N
    policy     : registered policy name (default "random")
    parent_key : fn(candidate)->parent id; defaults to candidate["parent_id"]
    """
    if policy not in _POLICIES:
        raise ValueError(f"unknown selection policy {policy!r}; choices: {list(_POLICIES)}")
    if parent_key is None:
        def parent_key(c):
            return c["parent_id"] if isinstance(c, dict) else c.parent_id
    rng = random.Random(seed)
    return _POLICIES[policy](list(candidates), size, parent_key, rng, **kwargs)


if __name__ == "__main__":
    # 3 parents x 4 expansions each; width-3 random selection keeps one per parent.
    cands = [{"parent_id": p, "id": f"{p}.{i}", "solver_acc": (i / 4)} for p in range(3) for i in range(4)]
    sel = select_candidates(cands, size=3, policy="random", seed=1)
    parents = sorted(c["parent_id"] for c in sel)
    print("random:", [c["id"] for c in sel], "parents:", parents)
    assert len(sel) == 3 and parents == [0, 1, 2], "random must keep one per parent"
    sel2 = select_candidates(cands, size=3, policy="frontier", seed=1, target_acc=0.5)
    print("frontier:", [(c["id"], c["solver_acc"]) for c in sel2])
    print("OK: selection interface works (random default + frontier stub)")
