# Self-Play Curriculum — Design

Design record for the **self-play curriculum** that sits on top of the static
two-stage baseline (`README.md`) — the **Phase 2/3** roadmap. Companion to
`WALKTHROUGH.md` (results log) and `compositional.md` (repo-root summary).

> **Prerequisite.** Self-play assumes a model that already has the **atomic
> skills** (Stage-1 closed-book recall, held-out Level-1 ≈ 0.9) and can do
> shallow composition (Stage-2). Self-play does *not* create atoms — it grows
> *composition depth*. Build it only once the closed-book Stage-1 fix lands
> (`train_stage1_closedbook.sh`); a weak-recall base caps everything downstream
> (see WALKTHROUGH §5).

Status: **design only — not implemented.** Today's Stage-2 is static GRPO/reval
on a frozen `stage2_level1to2/train.parquet`. `selection.py` is a standalone stub
(never called). Nothing below exists yet except the seams noted as *(exists)*.

---

## 1. Why self-play

The static pipeline measures *how far a fixed model generalizes*. Self-play
*pushes the frontier*: it keeps inventing compositions just past what the solver
can currently do, trains until the solver masters them, then goes deeper. The
question distribution **co-evolves** with the solver — a curriculum nobody hand-
authors. The headline output is the **effective trainable depth** D\* (the depth
at which the curriculum stops being able to saturate).

Three escalating versions (ship in order):

| version | questioner | what it adds |
|---|---|---|
| **v1** | programmatic (`generate_data.py`) | the outer loop + saturation gate + replay; random pruning |
| **v2** | programmatic + **frontier pruning** | `selection.py` "frontier" policy targets ~50%-acc candidates |
| **v3** | **learned** questioner (a 2nd policy) | questioner trained on a learning-progress reward |

v1 is the workhorse; v2/v3 are pluggable upgrades that don't change the loop.

---

## 2. Core objects

- **Operator menu `ops`** — the 25 `func_N` (paper pool) or 8 (lenpres). The
  *skill library*. Train ops vs held-out ops keep the paper split. *(exists:
  `operators.py`.)*
- **`S` — atomic anchor set.** Fixed depth-1 questions, one family per operator,
  many inputs each. Two jobs: (a) **replay** — mixed into every solver update so
  composition RL can't erode recall (the forgetting we saw at WALKTHROUGH §4);
  (b) **the expansion alphabet** — the skills the questioner composes with. `S`
  is *not* a third dataset; it is the depth-1 slice of the op menu. *(exists:
  `stage1_closedbook` / `stage2_level1` data.)*
- **`C` — compositional beam.** The evolving working set, **constant width `N`**.
  Each `q ∈ C` is a composition expression `f_{i1}(f_{i2}(… (x)))` of some depth
  `d`. Starts as the depth-1 (or depth-2) seeds; deepens one layer at a time.
- **Ground truth** — never labeled by hand: `execute(expr, input)` returns the
  gold output, with the length cap / timeout / recursion guard. *(exists:
  `executor.py`.)*

---

## 3. The outer loop (v1)

```
seed C  <- width-N sample of depth-1 (or depth-2) compositions over train ops
for layer d = 2, 3, 4, …, D_max:
    # (a) EXPAND: questioner deepens each q in C by composing ONE more skill
    cand = []
    for q in C:
        for _ in range(n_questioner):           # branching factor
            op   = pick_skill(ops_train)        # one more operator from the menu
            child = compose(op, q)              # f_op( q )   -> depth d
            child.parent_id = q.id
            cand.append(child)                  # GT is free via execute()

    # (b) TRAIN: solver RL on the candidates, with S replayed for anti-forgetting
    train_file = parquet(cand)  +  replay_sample(S, frac=REPLAY_FRAC)
    val_file   = held_out_eval(depth=d)         # disjoint held-out ops, depth d
    run_verl_rl(model, train_file, val_file,    # GRPO or reval, UNMODIFIED verl
                until = saturated(val_acc >= SAT_THRESH) or steps >= MAX_STEPS)

    # (c) GATE: did the solver master this depth?
    if not saturated:
        D_star = d - 1                          # first non-saturating layer
        break

    # (d) PRUNE: collapse the expanded pool back to width N for the next layer
    C = selection.select_candidates(cand, size=N, policy=SEL_POLICY, seed=…)

report D_star  # = effective trainable depth
```

**One PBS job per layer** (a verl RL run), orchestrated by a thin Python driver
that loops, builds each layer's parquet, qsubs the RL job, reads back the val
metric, and decides expand/prune/stop. **Zero verl-core edits** — the driver
only generates data and launches `train_per_node.sh`, exactly like the static
scripts.

---

## 4. Saturation gate & stopping

- **Saturation** = `val_acc(held-out ops, depth d) ≥ SAT_THRESH` (default
  **0.95**), measured on the *disjoint held-out* operator set so it's
  generalization, not memorization. Always log `has_answer` to distinguish a
  genuine reasoning ceiling from response **truncation** (the depth-100 wall in
  WALKTHROUGH §4 — a truncation collapse, not a reasoning one).
- **Step cap** `MAX_STEPS` per layer so a non-saturating layer terminates.
- **Stop** at the first layer that fails to saturate within the cap; that depth
  minus one is **D\*** (the effective trainable depth) — the curriculum's
  headline number. Optionally also stop at a target `D_max`.

---

## 5. Questioner — the three versions

**v1 — programmatic.** `pick_skill` is uniform-random over train ops; `compose`
wraps the parent expression in one more operator. This is just `generate_data.py`
used online (it already builds depth-`d` compositions with free GT). No learning;
the *curriculum* comes purely from the saturate-then-deepen loop. Ship first.

**v2 — frontier pruning.** Same programmatic expansion, but `select_candidates`
uses the **`frontier`** policy: keep candidates whose estimated solver accuracy is
nearest a target (~0.5 = max learning-progress), still guaranteeing ≥1 per parent
to preserve lineage diversity. Needs a cheap `solver_acc` estimate per candidate
(e.g. solver pass-rate over the layer's rollouts). *(exists as a stub:
`selection.py` `@register_policy("frontier")` + `solver_acc` field.)*

**v3 — learned questioner.** A second policy `π_q` that *generates* expressions
(or selects op + insertion point), trained by RL on a **learning-progress**
reward: a question is valuable when the solver is ~50/50 on it (not trivially
solved, not impossible). Concretely reward `q` by `1 − |solver_passrate(q) − 0.5|`
or Δ-competence (improvement the question induces). Co-training `π_q` and the
solver is the full self-play game; `selection.py` is the seam where `π_q`'s
proposals get scored/pruned. Highest risk, last.

---

## 6. Solver training

- **Algorithm:** `RL_METHOD=grpo` (baseline) or `reval` (value-based off-policy,
  `V_θ = logsumexp(logits)`, FIFO trajectory buffer). *(exists:
  `train_per_node.sh` switch.)* reval's buffer gives cross-layer off-policy
  replay "for free"; GRPO relies on the data-level `S` replay below.
- **Anti-forgetting replay:** every layer's `train_file` = `candidates` +
  `REPLAY_FRAC` sample of `S` (comma-separated `TRAIN_FILE` already supported).
  Without it, composition RL erodes atomic recall (WALKTHROUGH §4). Default
  `REPLAY_FRAC ≈ 0.2`.
- **Init:** layer `d` resumes from layer `d−1`'s checkpoint (curriculum =
  continued training), not from scratch. Each layer is its own `EXPERIMENT_NAME`
  / fresh `SAVE_DIR` so `resume_mode=auto` loads `model.path` and doesn't
  cross-contaminate (the footgun from this session — always pass vars with
  `qsub -v`).

---

## 7. Pruning — `selection.py` (exists)

`select_candidates(candidates, size=N, policy, parent_key, seed, **kw)`:

- **`random`** (v1 default): one random expansion per parent → constant width,
  every lineage survives. Tops up if `#parents < N`, samples parents if `> N`.
- **`frontier`** (v2): per-parent closest-to-`target_acc`, then global frontier
  fill. Needs `solver_acc` on candidates.
- New policies register via `@register_policy(name)` without touching the driver.

A candidate is a dict/obj with `parent_id` (lineage) and optional `solver_acc`.

---

## 8. Evaluation (shared with the static pipeline)

- **Mode 1** — end-to-end: predict the final output; metric = **D\*** (largest
  depth with acc ≥ 0.5); always log `has_answer` (truncation vs reasoning).
- **Mode 2** — intermediate-checkpoint probe: ask for the value after `k` of the
  `d` nested ops, to localize *where* a deep chain breaks.
- **Mode 3** — chunked multi-turn: let the solver emit one operator step per
  turn, sidestepping the single-response truncation wall for very deep chains.
- Tiers (lenpres): `iid` (train ops, shallow), `easy` (held-out 2–3), `medium`
  (10), `hard` (100). Mode 1 ships with the static pipeline; Modes 2/3 are
  Phase-1.5 standalone scripts and feed self-play's gate for deep layers.

---

## 9. Implementation plan

New (none touch verl core):

| file | role |
|---|---|
| `curriculum_driver.py` | the outer loop §3 — owns `C`, builds per-layer parquet (calls `generate_data.py`/`executor.py`), qsubs the RL job, reads back the val metric, gates, prunes via `selection.py`, advances/stops |
| `train_selfplay_layer.sh` | one PBS RL job for one layer (≈ `train_stage2.sh` parameterized by layer `d`, `TRAIN_FILE`=cand+`S`-replay, `VAL_FILES`=held-out depth-`d`, resume from prev ckpt) |
| `selfplay_state.json` | persisted beam `C`, current depth, per-layer val history (so a requeued driver resumes) |

Reuse *(exists)*: `operators.py`, `executor.py`, `generate_data.py`,
`reward_fn.py`, `selection.py`, `train_per_node.sh`, the `S` replay knob.

Sequencing: **v1** (driver + random pruning + saturation gate + `S` replay) →
**v2** (wire `solver_acc` → `frontier`) → **v3** (learned `π_q`). Land v1 against
the closed-book Stage-1 checkpoint and confirm it reaches at least the static
pipeline's depth before adding adaptivity.

---

## 10. Open design questions

1. **Saturation threshold / cap** — 0.95 may be too strict for deep held-out
   ops; consider a per-depth schedule or a patience window.
2. **Beam width `N` vs branching `n_questioner`** — N too small loses operator
   diversity; too large makes each layer a full RL run. Start N≈64,
   `n_questioner`≈4.
3. **`solver_acc` estimate cost (v2)** — reuse the layer's own training rollouts
   vs a separate eval pass; the former is free but noisier.
4. **Replay fraction** — fixed 0.2 vs anneal as depth grows (more forgetting
   pressure deeper).
5. **Held-out-op generalization at depth** — does saturating on *train*-op
   compositions transfer to *held-out*-op compositions at the same depth, or do
   we need held-out ops inside `C`? (The whole point — measure, don't assume.)
6. **v3 reward hacking** — a learned questioner can collude (emit only
   ~50%-acc-looking but degenerate questions); needs a validity/diversity
   constraint via `execute()` + dedup.

---

*Drafted with AI assistance. Per `CLAUDE.md` §1, a human must review and defend
any implementation before upstreaming.*
