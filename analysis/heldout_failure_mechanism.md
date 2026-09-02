# Why probe ops compose and held-out ops don't — Phase 0 analysis (2026-08-30)

Data: RA-v1 held-out sweeps @3072, 3 SFT seeds pooled (d14, v1_s7, v1_s123),
every `Recall func_N:` episode unit-tested against the hidden reference;
depth 3-6 unless stated. Scripts inline in the session (classify_ra_failures.py
machinery).

## 1. Where per-episode failures sit

| factor | ok | TypeError | wrong body |
|---|---|---|---|
| call site flat, arity 1 (n=1714) | 0.769 | 0.104 | 0.126 |
| call site flat, arity 2 (n=1549) | 0.933 | 0.015 | 0.052 |
| call site nested, arity 1 (n=4769) | 0.782 | 0.131 | 0.087 |
| call site nested, arity 2 (n=5665) | 0.845 | 0.112 | 0.043 |
| episode position 0 (first def written) | 0.903 | 0.086 | 0.010 |
| position 1 / 2 / 3 / 4+ | 0.82 / 0.83 / 0.80 / 0.76 | 0.11-0.13 | 0.07 / 0.06 / 0.10 / 0.12 |
| depth-2, 2 held-out funcs, nested `f(g(x))` (n=498) | acc 0.922 | | |
| depth-2, 2 held-out funcs, side-by-side `f(x)+g('lit')` (n=51) | acc 0.843 | | |

- Nested call sites matter only for arity-2 ops (TypeError 1.5% → 11%): the
  "parsed signature" mechanism exists but is secondary.
- Position matters for everything, and wrong-body errors grow 10× from the
  first def to the 5th: context load, not data flow. Side-by-side co-occurrence
  is no easier than nesting — **having other defs in the answer is the load**.

## 2. What is written instead — collapse onto a COMPOSED neighbor

TypeError episodes by (reference arity → params written): 1→2: 802, 2→1: 561,
2→3: 39. Wrong-body episodes: 326 are an EXACT copy of another op's reference
body, 624 novel; of 1,175 chimera copies, **1,102 come from a TRAIN op** (the
13 composed ops), 73 from another held-out op.

| held-out op | ref sig | written instead | body copied from |
|---|---|---|---|
| func_10 alternate_case | (s) | (s, shift) ×483 | func_11 shift_chars (train) ×483 |
| func_14 duplicate_every_char | (s) | — | func_4 reverse_words (train) ×219 |
| func_0 deterministic_shuffle | (s) | (s, pre) ×148 | func_5 add_prefix (train) ×148 |
| func_6 add_suffix | (s, suf) | (s) ×150 | func_5 add_prefix (train) ×27 |
| func_18 loop_concat | (s, n) | (s) ×178, (s1, s2) ×51 | func_4 ×56, func_19 while_rotate ×43 |
| func_24 backchain_palindrome | (s, depth) | (s) ×223 | — |
| func_21 loop_filter_nonalpha | (s) | (s, depth) ×51 | func_23 backchain_add_digit (train) ×27 |
| func_7 / func_8 / func_12 / func_16 | | (0.95-0.99 ok) | — |

Per-op ok rate (d3-6): func_10 0.49, func_0 0.52, func_6 0.76, func_14 0.76,
func_18 0.78, func_24 0.84, func_2 0.85, func_21 0.92, func_16 0.95,
func_7 0.97, func_12 0.97, func_8 0.99.

## 3. Reading

Under multi-def load, a held-out op's name→definition binding loses to a
STRONGER binding of a composed (train) op — frequently a name-token neighbor
(func_10→func_11, func_6→func_5, func_18→func_19, func_14→func_4) — and the
model writes that op's signature and body under the held-out op's name. The
held-out ops that are fine are those whose nearest composed neighbor is
harmless (rotate_str≡while_rotate, interlace_str≡recursive_interlace: same
signature and semantics) or absent.

This explains the whole record:
- composition exposure (train ops; probe ops at depth 2 only) installs a
  binding strong enough to survive load → the "phase transition" is per-op
  binding strength, not a procedure;
- RA-v2's call-site cue cannot help: the collapse happens at retrieval by
  name, before the call site is consulted;
- RL on train-op compositions strengthens exactly the attractors the held-out
  ops fall into → held-out declines while probe ops (own binding installed by
  SFT) rise;
- operator diversity (more composed train ops) is a double-edged route: more
  attractors unless the added ops also make bindings less confusable.

## 4. Predictions to test (B ladder, cheap)
- E-co: multi-atomic co-occurrence (defs of several ops in one answer, NO data
  flow) for a 6-op exposure subset of the held-out ops → should fix those 6
  (binding under load) without composition.
- E-self: complex call sites via self/literal composition only → should fix
  only the arity-2 nested-call-site share (small).
- Name ablation (bigger): retrain stage-1.5 + RA with non-numeric opaque names
  → held-out CI should rise if name-token collision drives the collapse.
