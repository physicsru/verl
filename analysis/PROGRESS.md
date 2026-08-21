# Compositional Generalization — Progress Log

Living document tracking the compositional-generalization pipeline
(`examples/compositional_trainer/`). **Update this file whenever a run
finishes, a finding lands, or the plan changes**: add a ledger row, update the
scoreboard + "State" section, and move items between *Next steps* and *Done*.
Deep-dive analyses go in separate `analysis/*.md` files and are linked here.

- Overview / design: [`compositional.md`](../compositional.md), usage in
  [`examples/compositional_trainer/README.md`](../examples/compositional_trainer/README.md),
  code-exec condition in
  [`README_codeexec.md`](../examples/compositional_trainer/README_codeexec.md).
- Main analysis: [`S2CX_EXPERIMENT_SUMMARY.md`](S2CX_EXPERIMENT_SUMMARY.md)
  (v1 + v2 + failure autopsies), probe table in
  [`probe_recall_stage15.md`](probe_recall_stage15.md).

## Research question

Does RL on *train-op* compositions generalize to compositions of *held-out*
ops under the one-shot code-exec condition (helper bodies hidden, model
re-implements every `func_N` from memory, program executed exactly once)?
Model: Qwen3-4B-Base. Pool: `paper` (25 ops, 13 train / 12 eval).

## State — 2026-07-30

**v3 RL running (job 2465888).** Pre-RL gate PASSED 07-30: recall 1.000 on
all 25 ops, EOS bug confirmed fixed (no cap-fill), pre-RL depth baseline
logged (`v3 s0` column). Stage-2 v3 GRPO submitted; headline to watch is
whether held-out-op d5–8 lifts off ~0. Direction settled with the user on 07-29: stay in the
code-exec condition (CoT was tried earlier and is worse — it entangles
composition with mental execution; code-exec separates them), fix the two v2
root causes, and make **depth extrapolation** the headline: SFT/RL only ever
see load ≤ depth 4, val goes to depth 8 — if held-out-op d5–8 improves
alongside d2–4 the model has learned assembly-under-load as a transferable
skill; if it cliffs at the trained depth, it memorizes load levels (a clean
negative). Built and launched: EOS chat-template fix, stage-1.5b multi-helper
closed-book SFT, pre-RL probe gate, depths-1–4 RL data. See *v3 checklist*.

v2 recap: with atoms installed by closed-book SFT (probe 1.000 on all 25
ops), held-out depth-1 holds at 1.000 through 500 RL steps and composition
transfers far beyond v1 (d4: 0.328 vs 0.008). Remaining failures were ~95%
mechanical program-construction crashes with two root causes: (1) per-mention
recall corrupts to ~0.85–0.9 under multi-helper load; (2) a degenerate no-EOS
generative state inherited from the SFT chat template (no EOS ⇒ the model
never learned to stop, fills every 4096-token budget with a mantra; RL cannot
fix it because EOS is never sampled ⇒ zero gradient on stopping).

**Best v2 checkpoint**: `stage2_paper_grpo_cx_v2_qwen3_4b/global_step_200`.

## Experiment ledger

| date (2026) | job | what | key result | artifacts |
|---|---|---|---|---|
| ~07-10 | — | Stage-1 RFT-codeexec (bodies shown, 3 iters) | per-sample acc 0.449, pass@8 0.991; incidental recall only 0.181 | `checkpoints/compositional/stage1_paper_rftcx_iter1_qwen3_4b/global_step_1984` |
| 07-14 | 2372789 | Stage-2 v1: GRPO 500 steps from stage-1 ckpt | d1 peak 0.457, d4 0.008; held-out recall eroded by sibling interference | `stage2_paper_grpo_cx_qwen3_4b`; trajectories `analysis/s2cx_val_trajectories/` |
| 07-15 | 2387365 | Stage-1.5: closed-book SFT (20k depth-1 rows, all 25 ops, 2 ep, lr 2e-5, ~14 min) | installed what 500 RL steps could not | `stage15_paper_closedbook_cx_qwen3_4b/global_step_312` |
| 07-15 | 2387747 | Recall probe (25 ops × 64 unseen depth-1, greedy@1) | **1.000 every op** (stage-1 init: 0.181, 11 ops at 0.000) | `analysis/probe_recall_stage15.md`, `checkpoints/compositional/probe_recall_d1/` |
| 07-16 | 2387955 | Stage-2 v2: identical to v1 but init = stage-1.5 ckpt | scoreboard below; best ckpt step 200 | `stage2_paper_grpo_cx_v2_qwen3_4b/global_step_{100..500}`; log `comp-s2-cx.o2387955` |
| 07-18 | — | v2 failure autopsy (1,733 captured val trajectories) | 61% = one recall-corruption mechanism; no-EOS degenerate state diagnosed | `S2CX_EXPERIMENT_SUMMARY.md` §autopsy |
| 07-27 | — | Traced mantra/34-block artifact to SFT chat template lacking EOS | reframes lever 1 as a bug fix | this doc |
| 07-29 | — | Decision: reject CoT pivot (tried before, worse); go v3 code-exec with depth extrapolation (d5–8 vs d2–4) as headline | see *v3 checklist* | this doc |
| 07-30 | — | v3 build: EOS template fix, stage-1.5b multi-helper SFT data (d2–4 train-op comps), probe+depth-sweep gate, d1–4 RL data | builder smoke-tested; SFT submitted | `build_v3_data.sh`, `train_stage15b_closedbook_codeexec.sh`, `probe_stage15b.sh`, `score_depth_sweep.py` |
| 07-30 | 2465179 | Stage-1.5b multi-helper closed-book SFT (32k rows: 20.8k d1 + 11.2k d2–4 train-op comps; init = stage-1 RFT, 2 ep, lr 2e-5, max_len 3072) | probe gate passed (see below) | `stage15b_paper_closedbook_cx_qwen3_4b/global_step_500` |
| 07-30 | 2465182 | v3 pre-RL gate: 25×64 recall probe + greedy d1–8 depth sweep | **recall 1.000 all 25 ops** (atoms survived multi-helper SFT); **EOS fix confirmed** (len 520→2029 tok, no 4096 cap-fill); pre-RL sweep d2 0.672 / d3 0.207 / d4 0.027 / d5–8 ~0 | `analysis/{probe_recall_stage15b,depth_sweep_stage15b}.md` |
| 07-30 | 2465888 | **Stage-2 v3 RL launched** (GRPO, init = stage-15b ckpt, TRAIN d1–4, val held-out d1–8, 8 nodes/48h, small-g) | queued | `stage2_paper_grpo_cx_v3_qwen3_4b` (pending); log `comp-s2cx-v3.o2465888` |

## Scoreboard — held-out-op composition accuracy (greedy mean@1, 256/depth)

`v3 s0` = stage-15b pre-RL baseline (multi-helper SFT, before any RL). d5–8
never trained by SFT or RL ⇒ the extrapolation test; the v3 RL run (2465888)
must move these for the headline claim.

| depth | v1 peak | v2 s0 | v2 s200 | v2 s500 | v2 peak | v3 s0 |
|---|---|---|---|---|---|---|
| 1 | 0.457 | 0.977 | 1.000 | 1.000 | 1.000 | 0.996 |
| 2 | 0.137 | 0.324 | 0.887 | 0.820 | 0.910@20 | 0.672 |
| 3 | 0.051 | 0.137 | 0.664 | 0.574 | 0.668@180 | 0.207 |
| 4 | 0.008 | 0.105 | 0.324 | 0.270 | 0.328 | 0.027 |
| 5 | 0.000 | 0.031 | 0.156 | 0.125 | 0.188 | 0.012 |
| 6 | 0.000 | 0.023 | 0.066 | 0.074 | 0.074 | 0.004 |
| 7 | — | — | — | — | — | 0.000 |
| 8 | — | — | — | — | — | 0.000 |

## What we know (condensed; details in S2CX_EXPERIMENT_SUMMARY.md)

1. **RL transfers behaviors, not memories** (v1): format discipline transferred
   to held-out ops; op semantics did not, and were eroded by train-sibling
   interference. GRPO cannot install absent memories (all-wrong groups ⇒ zero
   advantage).
2. **One cheap SFT beats 500 RL steps for memory** (stage-1.5): 14 minutes of
   closed-book SFT took per-op recall 0.181 → 1.000, and those memories
   *resist* the interference that degraded v1.
3. **Composition is bottlenecked by recall-under-load, not reasoning** (v2
   autopsy): atoms are perfect in isolation but per-mention integrity drops to
   ~0.85–0.9 with many helpers in one program (wrong signatures → TypeError
   23.9%, lost helpers → NameError 20.2%, hallucinated methods →
   AttributeError 11.5%, chimera bodies → wrong output 5.5%). Multiplicative
   compounding over 8–10 helper mentions explains the depth curve.
4. **The generation tail is degenerate and RL-unfixable**: no-EOS SFT template
   ⇒ every response cap-fills with a mantra; entropy 0.013 from step 10,
   pg_loss ~5e-8, clip_ratio ≥ 0.97 all run. Stopping must be taught
   supervised.
5. Pipeline plumbing (prompting, extraction, sandboxed exec, grading) is
   validated end-to-end.

## v3 checklist (built 2026-07-30)

Decision (07-29): stay code-exec; CoT rejected (tried before, worse — it
entangles composition with mental execution). Headline metric: held-out-op
**d5–8 accuracy vs d2–4** — extrapolation beyond the trained load.

1. ✅ **EOS bug fix** — `CUSTOM_CHAT_TEMPLATE` in `train_pbs_header.sh` now
   appends `eos_token` to assistant turns only (verified: prompt token
   stream byte-identical, assistant turn ends in id 151643). Applies to SFT
   loss (per-message masks) and is inherited by rollout stopping.
2. ✅ **Stage-1.5b multi-helper closed-book SFT data** —
   `build_closedbook_codeexec.py --comp_src ...` adds depth-2–4 TRAIN-op
   composition rows (4k+64 per depth) on top of the 25×800 depth-1 rows;
   eval ops only ever appear alone at depth 1. Builder smoke-tested +
   exec-validated. Data driver: `build_v3_data.sh`.
3. 🚀 **SFT run** — `train_stage15b_closedbook_codeexec.sh` (init = stage-1
   RFT ckpt, 2 ep, lr 2e-5, max_len 3072; measured max row = 1,151 tok, no
   truncation). **Job 2465179**, submitted 07-30.
4. ✅ **Probe gate before RL** — `probe_stage15b.sh`, **job 2465182**:
   (a) 25×64 depth-1 recall probe → **1.000 all 25 ops** (gate: 0 ops below
   0.9); (b) greedy d1–8 sweep → baseline in scoreboard (`v3 s0`).
   **EOS confirmed**: per-depth len 520→2029 tok, no 4096 cap-fill. PASSED.
5. 🚀 **Stage-2 v3 RL** — `train_stage2_codeexec.sh`,
   `TRAIN_FILE=stage2_level1to4_codeexec/train.parquet` (depths 1–4),
   `MODEL_PATH=stage15b_.../global_step_500/huggingface`,
   `EXPERIMENT_NAME=stage2_paper_grpo_cx_v3_qwen3_4b`. **Job 2465888**
   submitted 07-30 (8 nodes/48h, small-g). Watch: does d5–8 lift off ~0
   (extrapolation) or cliff at the trained d4 (memorized load)?
6. **Sampling signal (contingent)** — if the stage-15b ckpt still shows
   entropy ~0.01 in early RL, raise rollout temperature (~1.1–1.2) or add an
   entropy floor.

## Backlog

- `build_rft_data.py` fence-truncation fix (stage-1 ramble poisoning) —
  subsumed for future stage-1 reruns by the EOS fix, still unpatched.
- Optional: re-probe saved v2 ckpts per-op
  (`qsub -v "PROBE_MODEL=<hf dir>" probe_recall.sh`) to trace when/which
  bindings corrupt during RL.
- Phase 1.5+ from `compositional.md`: standalone eval suite (D\*), self-play
  curriculum outer loop, ReVal solver, `lenpres` deep track — all untouched
  since the code-exec detour.

## Key paths

- venv: `/work/go39/b20033/code/generalization_venv`
- checkpoints: `checkpoints/compositional/` (repo root)
- data: `data/compositional/paper/{stage2_level1to2_codeexec, stage2_level1to4_codeexec, stage2_level1to8_codeexec, stage15_closedbook_codeexec, stage15b_closedbook_codeexec}`
- job logs: repo root `comp-s2-cx.o<jobid>`, `comp-s15-cbcx.o<jobid>`, `comp-s15b-cbcx.o<jobid>`, `comp-probe-15b.o<jobid>`
- SFT template gotcha: `CUSTOM_CHAT_TEMPLATE` in
  `examples/compositional_trainer/train_pbs_header.sh` (must stay consistent
  between SFT and stage-2 rollout). Since 07-30 it ends assistant turns with
  `eos_token` — v1/v2 checkpoints were trained WITHOUT it (the mantra bug);
  don't mix pre/post-fix checkpoints and templates.

*AI-assisted analysis and doc; per `CLAUDE.md` §1 a human must review before
any of this feeds an upstream PR.*
