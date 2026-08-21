# Compositional Generalization — Walkthrough & Results Log

A running record of what we've built, what we ran, what we found, and what's
next. Companion to `README.md` (how-to) and `../../compositional.md` (summary).
Reproduces / extends *"From f(x) and g(x) to f(g(x)): LLMs Learn New Skills in RL
by Composing Old Ones"* (arXiv:2509.25123, the "RL-Compositionality" paper).

Last updated: 2026-08-05.

---

## 1. The question

Can a model that has learned **atomic string operators** (`func_0…func_24`)
**compose** them, and how far does that composition **generalize** — to deeper
nesting and to **held-out operators**? Two stages:

- **Stage 1** — operator bodies **shown**; learn the atomic skills.
- **Stage 2** — bodies **hidden**; must *recall* + *compose*. Train on one
  operator set, evaluate on a **disjoint held-out** set.
- **Forward task**: predict `main_solution(x)`'s output as `{"output": ...}`,
  scored by exact string match (pure Python, no sandbox).

**Two operator pools** (`operators.py`):

| pool | ops | role | depth reach |
|---|---|---|---|
| `paper` | all 25, paper train(13)/eval(12) split | faithful baseline | shallow (branching/growth ops) |
| `lenpres` | 8 length-preserving unary (subset) | deep track | depth 100 (output stays = input length) |

`depth`/level = compositional nesting. **The two pools' depth axes differ**:
`lenpres` depth-N = exactly N nested unary ops (`f₁(f₂(…fₙ(x)))`); `paper`
depth-N = the expression-generator recursion level, which *branches*, so the
operator count grows faster and non-monotonically (depth 1→1 func, 2→3, 3→5,
8→8). A `paper` depth-2 is already a 3-operator tree — not comparable to a
`lenpres` depth-2.

---

## 2. What we built (Phase 1 — static baseline)

| file | role |
|---|---|
| `operators.py` | 25 operators + pools/splits, stable global `func_N` naming |
| `executor.py` | safe GT execution (length cap, timeout, recursion guard) |
| `generate_data.py` | parquet generator (stage 1/2, any pool/depth) |
| `reward_fn.py` | forward-task reward + **validation sample logging** (§6) |
| `selection.py` | pluggable curriculum top-K (random default; frontier stub) |
| **RL** | `train_per_node.sh` (`RL_METHOD=grpo|reval`), `train_stage1.sh`, `train_stage2.sh` |
| **SFT** | `build_sft_data.py` (synthetic data) → `train_stage1_sft.sh` → `_sft_launch.sh` (primitive) |
| **RFT** | `rollout_stage1.py` → `build_rft_data.py` → `run_stage1_rft.sh` (iterative driver) |

RL / RFT / SFT are deliberately **separate scripts** (easier to debug). RFT
*composes* the SFT primitive (`_sft_launch.sh`); it does not duplicate it.

Infra: Miyabi GH200, 1 GPU/node, PBS, `-p 1023`. RL = 8-node mpirun+Ray; SFT/RFT
= single node (4B fits one GH200). wandb key read from `~/.netrc` at runtime.
Zero verl-core edits (reward via `reward.custom_reward_function.path`).

---

## 3. What we ran

| run | method | pool | result |
|---|---|---|---|
| Stage 1 (2112431/2) | **GRPO**, 400 steps | paper, lenpres | atomic-skill (bodies shown) correctness 0.99 both |
| Stage 2 (2119179/80) | **GRPO**, 500 steps | paper, lenpres | see §4 — both `trainer exited 0` |

Stage-2 init = the Stage-1 GRPO checkpoint (`global_step_400/actor/huggingface`).
Both Stage-2 runs train on a 50/50 mix of **depth-1 (`f(x)`) + depth-2 (`f(g(x))`)**
(`stage2_level1to2`); depth ≥3 is **held-out eval only**.

---

## 4. Results (held-out eval, correctness)

| level | **paper (2509.25123)** | our **lenpres** | our **paper-pool** |
|---|---|---|---|
| 1 | ~0.90 | **1.00** | **0.25** |
| 2 | ~0.64 | 0.54 | 0.06 |
| 3 | ~0.30 | 0.03 | 0.02 |
| 4 | ~0.15 | – | 0.00 |
| 10 / 100 | – | 0.00 / 0.00 | – |

- **`lenpres` reproduces the paper's curve** (L1 1.0≈0.90, L2 0.54≈0.64; deeper
  weaker, likely scale/steps). At depth-100, `has_answer` collapses 0.91→0.33 =
  the **truncation wall** (Mode-1 final-answer can't reach deep depth; Modes 2/3
  needed). The deep track behaves as designed.
- **`paper-pool` does NOT** — it collapses at **Level-1 atomic recall**, and
  Stage-2 RL actively *erodes* it (L1 peaked 0.46 @ step 40, decayed to 0.25 =
  catastrophic forgetting, no replay).

---

## 5. Key finding & root cause

**The paper-pool failure is recall, not composition — and it's a Stage-1
problem.** Sample evidence (paper-pool L1, body hidden):
`REF 'qqbbssyyzzggee'` (double-each-char) → `PRED 'qbsyzge'` (applied ~identity =
**recalled the wrong operator**); `REF 'jpmfhtkxme'` → `PRED 'Unknown'` (gave up).

Why: our **Stage-1 used GRPO**; the paper's **Stage-1 is iterative RFT/NTP**
("atomic skills acquired through NTP training"). With the body shown, GRPO can
earn reward by *reading* the function without memorising `func_N → behaviour`, so
held-out recall never forms: our Stage-1 model's held-out L1 ≈ **0.33–0.46** vs
the paper's **~0.90**. The paper states *"compositional RL does not improve
atomic skills, only composition"* — so a weak-recall Stage-1 caps everything
downstream; Stage-2 RL cannot create the missing atoms. `lenpres` dodges this
because its 4 held-out ops are few/simple/similar-to-train, so even weak GRPO
recall transfers.

Data protocol itself is **faithful** (verified against
`RL-Compositionality/examples/data_preprocess/string_data.py`): Stage-1 shows all
25 bodies, Stage-2 hides them and evaluates the held-out set; `func_N` is a
stable global mapping. The divergence is purely the **Stage-1 training method**.

---

## 6. The fix being implemented — faithful iterative RFT Stage-1

The paper's Stage 1 = **Rejection Fine-Tuning, iterative**: roll out the *current*
model → keep only **correct** trajectories → SFT on them → repeat with the new
model (lr 2e-5, batch 128). Pipeline (**8 nodes**, 48 h: rollout is data-parallel
across nodes, SFT is FSDP across the 8 GPUs):

```
run_stage1_rft.sh  (one 8-node PBS job, loops RFT_ITERS times):
  for it in 1..K:
    launch_mpi _rollout_launch.sh   # each node: vLLM on a disjoint problem shard (N samples)
    build_rft_data.py               # merge shards, keep correct -> messages SFT parquet
    launch_mpi _sft_launch.sh       # FSDP SFT across all nodes (shared primitive) -> new ckpt
  final checkpoint -> Stage 2
```

Launch: `POOL=paper RFT_ITERS=3 qsub examples/compositional_trainer/run_stage1_rft.sh`,
then `MODEL_PATH=<final ckpt> qsub train_stage2.sh`.

Expected: held-out L1 recall ≈0.9 → paper-pool reproduces L1~90 / L2~64 / L3~30.

**Status:** CPU data path validated (`build_sft_data.py`, `build_rft_data.py`
correctness filter). **GPU steps need a smoke run** to verify (a) the SFT
chat-template hook — `+data.apply_chat_template_kwargs.chat_template='${oc.env:CUSTOM_CHAT_TEMPLATE}'`
must match Stage-2's concatenate format, and (b) the SFT HF-checkpoint path
resolution in `run_stage1_rft.sh`. `build_sft_data.py` (synthetic deterministic
traces) is a cheap **cold-start / fallback** if iter-1 rollouts yield too few
correct trajectories — it is *not* the paper's method.

---

## 7. Other notes

- **Validation sample logging** (`reward_fn.py`): validation-only by default
  (`COMPOSITIONAL_PRINT_VAL_ONLY=1`); prints `[VAL SAMPLE]` + PROGRAM + INPUT +
  REF + PREDICTED + RESPONSE TAIL, up to `COMPOSITIONAL_NUM_EXAMINE` (3) per
  depth per round; one `print()` per sample (avoids Ray cross-worker log dedup).
- **reval** (`RL_METHOD=reval`): the FIFO replay buffer **works** (verified on a
  650-step deepscaler run: off-policy active 499/500 steps, eviction past
  capacity 5120 clean). Only unwired piece: `reval_ref_reset_freq>0` → π_ref
  reset is a no-op (default 0 = fixed reference). Never run on the compositional
  pool yet (both Stage-2 runs were GRPO).

---

## 8. Next steps

1. **Smoke** `run_stage1_rft.sh` (1 iter, small `MAX_PROBLEMS`) — verify SFT
   launch + checkpoint path, then full 3-iter RFT for `paper`.
2. Re-run **paper-pool Stage-2** from the RFT Stage-1 ckpt (+ Stage-1 replay) →
   compare to the paper's curve.
3. **Phase 1.5**: standalone `eval/` (Modes 1–3, depth sweep, D\*).
4. **Phase 2**: curriculum outer-loop (grow `C`, train to saturation with `S`
   replay, prune via `selection.py`).

*(§§1–8 above are the CoT-condition Phase-1 log, kept as history. The code-exec
track that followed is §§9–13 below.)*

---

## 9. The code-exec track (chronology)

After §6, the pipeline moved to the **one-shot code-exec condition**
(`reward_fn_codeexec.py`): bodies hidden, the model writes ONE self-contained
program re-implementing every `func_N` in the given skeleton; it is executed
once at reward time. Composition *structure* is handed to the model in the
prompt — what is tested is recalling and faithfully emitting k operator
implementations in a single program.

| step | run / ckpt | what happened |
|---|---|---|
| Stage-1 RFT-cx | `stage1_paper_rftcx_iter1/step_1984` | bodies-shown atomic training, all 25 ops |
| Stage-2 v1 (o2372789) | init = RFT-cx ckpt | held-out d1 only ~0.35-0.46: **atomic recall never formed** (autopsy: `analysis/S2CX_EXPERIMENT_SUMMARY.md`) |
| **Stage 1.5** (`stage15`) | SFT, 20k depth-1 closed-book recall targets, all 25 ops | installs atomic recall |
| Stage-2 v2 (o2387955) | init = `stage15/step_312`, train d1-2 | genuine learning (train 0.66→1.05 over ~50 steps) then saturation; held-out d2 ≈ 0.90 at init, OOD (d5-8) only ever declined |
| **Stage 1.5b** (`stage15b`) | + 12k depth-2..4 **train-op** composition rows, EOS template | multi-helper robustness for train ops |
| Stage-2 v3 (o2465997) | init = `stage15b/step_500`, train d1-4 | saturated from step 1 — see §10 |
| Stage-2 v3d12 (o2471454) | init = `stage15b/step_500`, train **d1-2** | controlled comparison — see §10 |

---

## 10. Stage-2 RL is dead on arrival, and training depth was never the variable

An apparent "d1-2 training beats d1-4" comparison (v2 vs v3) dissolved on
inspection: the two runs started from **different Stage-1.5 checkpoints**, and
`stage15b/500` is far weaker on held-out composition *before any RL* (d2 0.67
vs 0.90, d3 0.20 vs 0.61, d5 0.01 vs 0.19). Extra Stage-1.5 training on
train-op compositions bought train-op ceiling at the cost of held-out ability —
**over-training Stage 1.5 is anti-generalization**.

The controlled re-run (v3d12: identical init/config to v3, only
`TRAIN_FILE=stage2_level1to2_codeexec`) settles it. Both runs, 781 steps
(1 epoch of 50k):

- **Train reward = 1.05 (max) from step 1** in both; only 68/781 steps (8.7%)
  had any nonzero advantage. GRPO: zero within-group reward variance → zero
  advantage → zero pg-gradient. The only thing propagating for ~91% of steps
  is KL-loss noise — which slowly *erodes* the policy.
- **Held-out scores only decay**, at every depth, in both runs. Final step 780,
  d1-4 vs d1-2 runs: d2 0.320/0.289, d3 0.098/0.062, d4 0.004/0.000; even
  atomic d1 fell to 0.977/0.840. For the d1-2 run the best-ever score at every
  held-out depth is **step 0**.
- **d1-2 is equal-or-worse than d1-4 everywhere.** The narrower data is *more*
  saturated (rollouts ~165 vs ~260 tokens) and gives shorter programs to
  practice on. The original observation was purely the checkpoint confound.
- OOD (d5-8 mean) is at the noise floor (≤0.004, i.e. 1-4 of 1024 correct) at
  init and forever after, for both.

**Conclusion:** RL on a task the init already solves at ceiling cannot teach
anything and slowly damages what exists. Any next Stage-2 attempt needs
(a) reward variance restored — deeper **train-op** data where the model is
below ceiling, plus DAPO-style `filter_groups` to drop zero-variance groups —
and (b) a less-baked init.

---

## 11. Failure anatomy: the model can't *emit the program*, not can't compose

`val-aux/.../exec_ok` (logged per depth over the full 2048-row held-out set)
splits score into *did the program run* × *was it right given it ran*
(`stage15b/500` init, before RL):

| depth | k = distinct ops | exec_ok | score | acc \| ran |
|---|---|---|---|---|
| 1 | 0.9 | 0.99 | 0.99 | 1.00 |
| 2 | 1.9 | 0.75 | 0.67 | 0.90 |
| 3 | 2.8 | 0.33 | 0.20 | 0.62 |
| 4 | 4.0 | 0.10 | 0.03 | 0.31 |
| 6 | 6.1 | 0.012 | 0.004 | 0.33 |
| 8 | 7.8 | **0.00** | 0.00 | — |

- The bottleneck is **exec_ok**: at depth 7-8 not one program in 256 runs.
  Logged crash mix: TypeError 39% (a `func_N` defined with the wrong arity,
  though every call site is printed in the prompt), NameError 31% (a `func_N`
  in the skeleton never defined at all). Format is never the issue
  (`has_plan` = `one_block` = 1.0 at every depth).
- Worse than independent compounding: implied per-op reliability
  p = exec_ok^(1/k) falls 0.99 → 0.86 → 0.67 → 0.56 → 0.48 as programs grow.
  Recall-under-load degrades per item — an interference/capacity effect, not
  just k chances to slip.
- Because GRPO can only amplify behaviors with nonzero base rate, depth ≥ 6
  (success probability ~0) can never be learned by outcome-reward RL from this
  init: the correct program is never sampled, so no gradient toward it exists.

---

## 12. Compositionality Index (CI)

`compositionality_index.py` formalizes "how much atomic skill survives
composition". With per-op depth-1 recall x_i, perfect compositional mastery
predicts a program over ops S succeeds with prob `bound = Π x_i` (distinct
ops; a def's correctness is input-independent in the code-exec condition, so
the bound is not confounded by depth-growing intermediate strings).
**CI(n) = observed(n) / bound(n)**; also reported: implied per-op p(n).

```
# exact per-op mode (rollout sweep parquets):
python examples/compositional_trainer/compositionality_index.py \
    --sweep stage15b=checkpoints/compositional/probe_stage15b/depth_sweep_stage15b \
    --out analysis/ci_stage15b.md
# approximate mode (verl job log + test parquet for k(n)):
python examples/compositional_trainer/compositionality_index.py \
    --log comp-s2cx-v3.o2465997 \
    --test-parquet data/compositional/paper/stage2_level1to8_codeexec/test.parquet
```

Headline (`stage15b/500`, greedy, `analysis/ci_stage15b.md`): **every held-out
op has x_i = 1.000 at depth 1** — so bound = 1.0 at every depth and CI equals
raw accuracy: 1.00, 0.67, 0.21, 0.03, 0.012, 0.004, 0.000, 0.000 for depths
1-8. The strongest possible form of the result: atomic recall is *perfect*,
and 100% of the loss is composition-induced interference. The model retains
~40-60% of per-op skill per additional op composed, vs the ~100% mastery
predicts.

**Interpretation caveat:** since the skeleton is given, CI here measures
*k-way simultaneous recall under interference*, not structural composition.
Current verdict on the research question: the model memorizes atoms and
sharpens shortcuts; nothing we have tried instills a robust op-general
compose-and-emit procedure, and RL demonstrably cannot (it only redistributes
mass over behaviors that already occur).

---

## 13. Next steps (code-exec track)

1. **Open-book depth sweep** — same held-out d1-8 eval with bodies *shown*.
   Separates recall-interference from any true composition/program-length
   limit: if open-book d8 is high, the entire failure is recall capacity.
2. **Per-func partial credit** — the reward already executes the program;
   additionally unit-test each defined `func_N` against the hidden reference
   on probe inputs and pay `(#correct)/k`. Converts depth-8 from
   probability-~0 outcome reward (dead gradient) into dense signal on exactly
   the failing channel. If dense reward *still* can't climb, that is strong
   evidence of a hard capacity limit rather than an exploration failure.
3. **Deeper train-op data (d5-8) + `filter_groups`** — restore reward variance
   (headroom exists only at depth ≥ 5) and stop the 91% dead steps.
4. **Stage-1.5 checkpoint sweep** — OOD vs SFT step count, to locate where
   train-op specialization starts costing held-out ability
   (`stage15/312` ≫ `stage15b/500` on OOD).

---

## 14. The RA intervention — recall-then-assemble (2026-08-04/05)

§§11-12 said the failure is k-way recall interference, not composition. The
treatment: teach an op-agnostic FORMAT that reduces a k-op composition to k
sequential *isolated* recall episodes plus a mechanical copy step —

```
Recall func_N: <one-sentence semantics>
```python
<that def alone, from memory>          <- one episode per distinct op,
```                                       shaped exactly like the depth-1
... (k episodes) ...                      atomic task (which is x_i = 1.0)
Assemble:
```python
<all defs re-copied + main_solution verbatim>   <- LAST block = the program
```
```

Pipeline (`build_ra_elicit_data.py`, `build_ra_rft_data.py`,
`build_ra_sft_data.py`, `run_ra_rft.sh`): bootstrap SFT on STITCHED targets →
one prompted-RFT round (hard gate: full-program exec AND per-episode unit
tests vs the hidden reference) → greedy held-out sweep + CI.

**Elicitation alone fails** (smokes 2487679/2487685/2488107/2488215):
stage15/312 predates the EOS fix (88% cap-fill, unusable); stage15b resists
instructions + per-problem template + prefix seeding — 6.4% structural
compliance, 0.4% verified. Content was usually CORRECT; only the
"prose + one block" habit failed. Hence stitched bootstrap: response content =
exactly the stage-1.5 target phrasing (docstring gloss + verbatim renamed
body), recomposed into RA structure; 16k train-op comps (d2-4) + 10k depth-1
atomics over ALL 25 ops (held-out ops practice the episode SHAPE atomically —
never inside a composition, so benchmark purity is preserved). All 25,979
stitched rows pass the RFT gate. After bootstrap, RFT elicitation jumps to
~59-87% verified — the format is native, later rounds are on-policy.

**Gotcha (job 2488926):** `train_pbs_header.sh` exports
`MODEL_PATH=Qwen/Qwen3-4B-Base` at source time, so `${MODEL_PATH:-...}`
fallbacks in job scripts silently pick base. Use a dedicated env var
(`RA_INIT`). The buggy run (whole pipeline from BASE) was kept as an ablation
(`*_frombase`, `analysis/ci_ra_rft_frombase.md`).

### Results (held-out ops, greedy, CI = accuracy since all x_i = 1.0)

| depth | stage15b baseline | RA from BASE (ablation) | **RA from stage15b (2490799)** |
|---|---|---|---|
| 1 | 0.996 | 0.996 | 0.992 |
| 2 | 0.672 | 0.652 | **0.902** |
| 3 | 0.207 | 0.320 | **0.766** |
| 4 | 0.027 | 0.086 | **0.594** (×22) |
| 5 | 0.012 | 0.035 | **0.453** (×38) |
| 6 | 0.004 | 0.012 | **0.301** (×77) |
| 7 | 0.000 | 0.008 | **0.156** (0→) |
| 8 | 0.000 | 0.004 | **0.121** (0→) |

Implied per-op reliability p = acc^(1/k): baseline 0.81/0.57/0.40/0.41/0.40/0/0
→ RA **0.95/0.91/0.88/0.85/0.82/0.77/0.76**. Binomial MLE fits (constant-p
model, exact tail checks): baseline and the from-base ablation both behave as
independent compounding for k≥4 (p ≈ 0.398 and 0.514 resp.); the corrected run
still shows a slow drift (0.95→0.76) — interference strongly suppressed, not
zero. Note depth 5-8 had NO training compositions at any stage: those numbers
are simultaneous op- and depth-extrapolation, the first real depth
generalization on this benchmark.

### Why the jump is this large

1. **Retrieval context is restored to the atomic shape.** Autoregressively,
   the old format generates def #3 conditioned on a window full of other defs
   (sibling bodies prime wrong continuations — the measured NameError/
   TypeError/chimera modes). In RA each def is generated right after its own
   `Recall func_N: <gloss>` cue, a context nearly identical to the depth-1
   task where recall is perfect. The gloss line also factorizes retrieval:
   name → stated semantics (cheap) → code for the semantics just stated.
2. **Recall and assembly are unbundled.** The final program is now produced by
   verbatim COPYING from the model's own context (transformers are near-perfect
   at this), not by recalling under load. The hard step is done k times in
   isolation; the entangled step is made mechanical.
3. **Held-out episode shape is in-distribution.** The all-25-op atomic RA rows
   mean "a held-out op's episode inside a long RA answer" is exactly what
   training looked like; previously held-out defs in multi-def contexts were
   doubly out-of-distribution.
4. **Per-episode data hygiene.** The RFT gate unit-tests every episode, so no
   wrong-def trace enters training (the old data only checked the final
   output, letting lucky-cancellation errors through).
5. **The format is length-invariant.** Emitting k episodes is k repetitions of
   one learned unit + copy; nothing in the unit depends on k, so performance
   extrapolates multiplicatively (~p^k) instead of collapsing — which is what
   the depth-5-8 numbers show.
6. **Memory × format are complementary (ablation).** Format without
   pre-installed memory (from-base run): deep p ≈ 0.51. Memory without format
   (baseline): deep p ≈ 0.40. Both: 0.76-0.95.

### Status / next

Targets were CI(2) ≥ 0.95, CI(3) ≥ 0.85 → the RFT-augmented run got 0.90/0.77,
but §15 then showed the RFT round was NET HARMFUL — the bootstrap-only
checkpoint achieves **0.984 / 0.910** and beats it at every depth. See §15.

---

## 15. Composition-depth ablation — and the RFT round is harmful (2026-08-05)

Four bootstrap-only variants (same stage15b/500 init, same SFT hyperparams, NO
RFT), single variable = depth range of the stitched comp data (all-25-op d1
atomics always included). Jobs 2492864-66; `analysis/ci_ra_depth_ablation.md`.

| depth | d1 (no comps) | d12 (+d2 only) | d13 (+d2-3) | d14 (+d2-4) | old baseline |
|---|---|---|---|---|---|
| 1 | 1.000 | 0.895 | 0.961 | 1.000 | 0.996 |
| 2 | **0.203** | **0.965** | 0.852 | 0.984 | 0.672 |
| 3 | 0.035 | **0.910** | 0.723 | 0.910 | 0.207 |
| 4 | 0.000 | **0.727** | 0.461 | 0.750 | 0.027 |
| 5 | 0.000 | 0.496 | 0.352 | 0.586 | 0.012 |
| 6 | 0.000 | 0.355 | 0.230 | 0.398 | 0.004 |
| 7 | 0.000 | 0.188 | 0.121 | 0.223 | 0.000 |
| 8 | 0.000 | 0.117 | 0.035 | 0.152 | 0.000 |

Implied per-op p (d2→d8): d12 0.98→0.76, d13 0.92→0.65, d14 0.99→0.79.

1. **Multi-episode emission is itself a skill** — format seen only at k=1
   (d1) does NOT extrapolate: depth-2 drops to 0.203 (far below even the
   no-RA baseline), 0 from depth 4. The episode "loop" needs a demonstration.
2. **One depth of demonstration suffices**: d12 (k=2 comps only) ≈ d14
   everywhere, incl. depth 8 (0.117 vs 0.152) — extrapolation from k=2 to
   k≈7.8. Once the "emit another episode" unit is installed, depth is ~free.
   This is the direct evidence of the format's length-invariance.
3. **The RFT round on train-op comps is NET HARMFUL to held-out**: the d14
   bootstrap-only checkpoint beats the post-RFT model of §14 at every depth
   (0.984/0.910/0.750/0.586/…/0.152 vs 0.902/0.766/0.594/0.453/…/0.121).
   Same mechanism as stage15b's damage: ANY continued training on the fixed
   13-train-op composition set specializes content and squeezes held-out ops.
   Best checkpoint overall =
   `ra_sft_bootstrap_paper_qwen3_4b/global_step_400` (bootstrap SFT only).
   CI(2)=0.984, CI(3)=0.910 — both targets exceeded.
4. **d13 anomaly RESOLVED = training-seed noise** (replication `d13b`,
   seed 123, job 2493626): d13b lands right in the d12/d14 band and is
   best-in-class at d2-3 (1.000/0.992/0.945/0.672/0.465/0.281/0.129/0.086) —
   the seed-42 d13 run was simply an unlucky draw. Implication: single-seed
   SFT runs carry variance up to ~±0.2 absolute at mid depths, so the
   d12-vs-d13-vs-d14 ordering is NOT resolvable at n=1; the robust statements
   are (a) d1-only collapses, (b) any ≥1 depth of comp practice lands in the
   same high band and extrapolates to k≈8. (The paired RFT-harm comparison in
   pt. 3 is same-checkpoint before/after, not two seeds, so it survives this
   caveat — though it too is n=1.) Also noteworthy: failure modes differ —
   d14's deep failures are mostly silent wrong answers (d8 exec_ok 0.352 vs
   acc 0.152) while d12's are mostly crashes (0.129 vs 0.117).

Revised recipe: stage-1.5 atomic memory + one stitched-SFT with d1 atomics
(all ops) + depth-2 comps (train ops) is the whole intervention; deeper comp
data adds little and further train-op-comp training (RFT or otherwise)
subtracts.

---

## 16. TRAIN-op depth sweep — depth was never the bottleneck (2026-08-08)

New eval set `stage2_level1to8_trainops_codeexec/test.parquet` (2048 rows,
same generator/seed/format as the held-out set but over the 13 TRAIN ops) —
atoms fully practiced incl. inside compositions, so op-generalization is
removed and what remains is pure depth extrapolation (depth 5-8 unseen by
every model; job 2507855, `analysis/ci_trainops_sweep.md`).

| depth | baseline held/**train** | d14 held/**train** | d13b held/**train** | d12 held/**train** | d1 train |
|---|---|---|---|---|---|
| 1 | 0.996 / **0.977** | 1.000 / **1.000** | 1.000 / **1.000** | 0.895 / **0.871** | 1.000 |
| 2 | 0.672 / **1.000** | 0.984 / **1.000** | 0.992 / **1.000** | 0.965 / **0.996** | 0.164 |
| 3 | 0.207 / **1.000** | 0.910 / **1.000** | 0.945 / **1.000** | 0.910 / **0.992** | 0.023 |
| 4 | 0.027 / **1.000** | 0.750 / **1.000** | 0.672 / **0.992** | 0.727 / **0.844** | 0.000 |
| 5 | 0.012 / **1.000** | 0.586 / **0.996** | 0.465 / **0.883** | 0.496 / **0.719** | 0.000 |
| 6 | 0.004 / **1.000** | 0.398 / **0.953** | 0.281 / **0.691** | 0.355 / **0.555** | 0.012 |
| 7 | 0.000 / **0.992** | 0.223 / **0.867** | 0.129 / **0.496** | 0.188 / **0.414** | 0.008 |
| 8 | 0.000 / **0.969** | 0.152 / **0.695** | 0.086 / **0.371** | 0.117 / **0.219** | 0.008 |

1. **The baseline has NO depth wall.** stage15b composes train ops at depth
   5-8 (never trained) at 0.97-1.00, implied p = 1.00 throughout — in its
   native prose+one-block format. The held-out collapse (§11) was therefore
   ~100% op-specific, ~0% depth/capacity. "k-way recall interference" must be
   restated: multi-def emission is only unreliable for ops NOT practiced in
   multi-def contexts; familiar ops compose arbitrarily deep for free.
2. **Op-generalization cost, precisely priced** (same variant, same depth,
   held-out vs train): baseline pays everything (0 vs 0.97 at d8); RA-d14
   shrinks it to ~4.6× (0.152 vs 0.695; per-op p 0.79 vs 0.96). RA's gain is
   real but a per-op familiarity gap remains.
3. **RA costs some train-op deep ability**: every RA variant is below
   baseline on train ops at d7-8 (d14 0.695 vs 0.969) — the format rewrite
   trades a little in-distribution composition for a lot of held-out.
4. **Comp-depth range matters ONLY in-distribution**: on train ops the
   ordering is clean d14 > d13b > d12 (0.695/0.371/0.219 at d8), while on
   held-out the same three are within seed noise. Deeper comp data buys
   familiar-content depth robustness, not op transfer.
5. **d1 actively destroyed existing ability**: its atomic-RA-only SFT took
   train-op d2 composition from 1.000 (init) to 0.164 — format overwrite
   without a multi-episode demonstration damages what the init had.
6. Caveat: train-op rows at depth ≤4 may textually overlap training programs
   (same generator; in-distribution anchor is intended); depth 5-8 cannot
   overlap and is the clean reading.

**Failure classification of the RA deep-depth drop** (train-op sweeps, greedy,
depth ≥ 4, classified by re-executing every failing program): TWO distinct
mechanisms, split by variant —

- **d14 = token-budget truncation, not capability.** At d8, 50 of its 78
  failures are mid-generation cutoffs (median response 4304 chars, p90 5431
  vs the ~5.6k-char ceiling of ROLLOUT_MAX_TOKENS=1536), plus 17
  top_level_error that are mostly near-cap malformed programs; only 9 are
  missing-episode NameErrors. The RA format writes every def TWICE (episodes
  + Assemble), doubling length: k≈8.6 defs ≈ the whole budget. So d14's
  "drop beyond d6" on train ops is largely an eval-budget artifact — pending
  verification re-sweep with ROLLOUT_MAX_TOKENS=3072.
- **d12 (and partly d13b) = episode omission.** Dominant failure is NameError
  with missing recall episodes (d12@d8: 153/200 failures): trained on k≈2
  episodes, the model under-emits at k≈8 — a learned episode-count prior —
  and Assemble then calls undefined funcs. This is the genuine
  format-extrapolation limit (it also explains why d12<d14 on train ops but
  not held-out: held-out scores are low enough that the omission tail is
  masked).
- Fix directions: raise the eval budget (immediate); an **RA-inline** format
  variant — episodes as comment + def inside the single final block, no
  duplication, halves length; or an explicit episode-count cue in the plan
  line ("k helpers to recall").

**Uniform theoretical reference added** (`p̄₁^k`, p̄₁ = overall depth-1
accuracy; extra columns in `compositionality_index.py` reports): baseline
observed 0.207 vs reference 0.989 at depth 3 (the original indictment); d14
p̄₁=1.0 so reference = 1.0 and CI is the gap. Caveat discovered via d12/d13:
their depth-1 accuracy (0.895/0.961) is dragged by the ~10% FUNCLESS
skeletons (literal/`.upper()`-only programs — absent from the stitched data),
NOT by op unreliability (per-op x_i = 1.000 for all ops in every variant).
Hence d12 *exceeds* its naive "bound" at depths 2-4 (acc/p̄₁^k up to 1.25):
the mean approximation is not a true upper bound when depth-1 has a
format-specific failure mode; the per-op `Π x_i` column is the honest one.
Note the funcless failures are themselves seed-dependent (d1/d13b/d14 keep
them at 1.000; d12 and seed-42 d13 partially lose them) — preservation of the
pre-SFT behavior on these OOD rows is not systematic. (Fixable data gap: add
funcless-skeleton rows to the stitcher.)
