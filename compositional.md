# Compositional Generalization

Research pipeline for **learning atomic skills, then composing them**, and
measuring how far composition generalizes — to **deeper nesting** and to
**held-out operators never trained on**. Lives in
[`examples/compositional_trainer/`](examples/compositional_trainer/) (see its
`README.md` for full usage); ported from the RL-Compositionality string task and
built on verl with zero core edits (custom reward via
`reward.custom_reward_function.path`, like `lengthgen_trainer` / `reval_trainer`).

## Task

- ~25 atomic string operators (`func_0…func_24`), composed into nested programs.
  **Level = composition depth.** Forward task: predict `main_solution(x)`'s
  output as `{"output": ...}` — scored by pure-Python string match, no sandbox.
- **Stage 1** (operator bodies **shown**): learn what each `func_N` does.
- **Stage 2** (bodies **hidden**): recall + compose them. Trains on **train
  ops**, evaluated on the **disjoint held-out ops** — the generalization test.

Two **conditions** on the same instances: **CoT** (predict the output mentally,
above) and **one-shot code-exec** — plan in text, then commit to ONE
self-contained Python program re-implementing every hidden `func_N`; it is
executed exactly once at reward time (output never shown to the model), so
execution capacity is factored out and held-out-op accuracy isolates
skill-recall + explicit composition. See
`examples/compositional_trainer/README_codeexec.md`.

## Two operator pools

| pool | ops | role | depth reach |
|---|---|---|---|
| `paper` | all 25 (paper train13/eval12 split) | faithful **baseline** | shallow (growth ops) |
| `lenpres` | 8 length-preserving unary (subset) | **deep track** | depth 100+ (output len = input len) |

`lenpres` keeps the paper's train/eval assignment, giving a free
"same-operation, new-name" probe (`while_rotate` train ≡ `rotate_str` held-out).
Length preservation is what makes depth-100 eval tractable — verified bounded &
fast (`python examples/compositional_trainer/executor.py`).

## Self-play curriculum (the goal; Phase 2/3)

Two question sets: **S** = fixed atomic-skill questions (replay anchor),
**C** = evolving compositional beam (width N). Each layer: expand `C` by adding
one skill (ground truth free via the executor), train the solver (GRPO or ReVal)
on the candidates **+ replay from S** until val acc ≥ 0.95 on a held-out
depth-*d* set (saturation gate, with a max-step safety cap), then prune
candidates → next `C` via a pluggable top-K (`selection.py`, default random,
frontier/learning-progress later). The questioner and solver are one
role-conditioned policy. Stage-2 RL uses **ReVal** (value-based off-policy,
`V=logsumexp(logits)`, FIFO replay) as the "mixed value/policy" method; GRPO is
the baseline.

## Evaluation

Depth-resolved accuracy (always logging `has_answer` to separate truncation from
reasoning failure); headline = **effective compositional depth** D\* (largest
depth with acc ≥ 0.5). Tiers: IID, OOD easy (2–3), medium (10), hard (100).
**Mode 1** (final-answer) ships via verl validation; **Mode 2** (checkpoint
probe) and **Mode 3** (chunked multi-turn) are planned.

## Status

Live progress log (run ledger, scoreboard, next steps):
[`analysis/PROGRESS.md`](analysis/PROGRESS.md).

- **Phase 1 (done):** static two-stage GRPO/ReVal baseline — operators, safe
  executor, data generator (both pools), forward reward, PBS/Ray launch with a
  `grpo|reval` switch, `run_baseline.sh` one-shot launcher, Mode-1 eval. All
  offline self-tests pass; no training runs launched yet.
- **Phase 1.5:** standalone eval suite (Modes 1–3, depth sweep, D\*).
- **Phase 2:** curriculum outer-loop driver (S/C, saturation gate, selection).
- **Phase 3:** learned questioner, faithful off-policy ReVal buffer, OPD Stage-1
  (32B teacher).

## Run

```bash
# build data + chain stage1 -> stage2 (PBS dependency)
POOL=paper bash examples/compositional_trainer/run_baseline.sh
DRY_RUN=1 POOL=lenpres RL_METHOD=reval bash examples/compositional_trainer/run_baseline.sh
```

Env: venv `/work/go39/b20033/code/generalization_venv`; data at
`data/compositional/<pool>/`; Qwen3-4B-Base on Miyabi (8 nodes).
AI-assisted — per `CLAUDE.md` §1 a human must review before any upstream PR.
