# ReVal — Off-Policy Value-Based RL for LLMs

Prototype implementation of **ReVal** from Wang et al., 2026
([arXiv:2603.23355](https://arxiv.org/abs/2603.23355)) layered on top of
verl's synchronous PPO trainer.

> **AI-assistance disclosure.** This pipeline was drafted with AI assistance.
> Per `CLAUDE.md` §1, a human submitter must review every changed line and run
> the relevant tests before any upstream contribution.

## What ReVal does

ReVal is a single-model, value-based, off-policy RL algorithm. The pretrained
LLM's logits are reinterpreted as a soft Q-function (`Q_θ(s, a) := logit_θ(s, a)`),
giving `V_θ(s) = logsumexp_a Q_θ(s, a)` for free — no separate critic. Training
minimizes the trajectory-level Bellman residual (Eq. 2 of the paper):

```
L(θ) = E_{τ∈D_replay} [ ( V_θ(s_1) − V_ref(s_1)
                          + Σ_h log π_θ(a_h|s_h)
                          − r(τ)/β
                          − Σ_h log π_ref(a_h|s_h) )^2 ]
```

The objective satisfies *Calibrated Initialization* (Proposition 2): when
`r = 0` and `π_θ = π_ref`, the loss is exactly zero, so a freshly-loaded model
does not drift before any reward signal arrives.

## How it slots into verl

| Layer | File | Change |
| --- | --- | --- |
| Advantage estimator | `verl/trainer/ppo/core_algos.py` | New `@register_adv_est("reval")` carrying r(τ) (optionally group-mean-normalized) |
| Policy loss | `verl/trainer/ppo/core_algos.py` | New `@register_policy_loss("reval")` computing the squared Bellman residual |
| Engine forward | `verl/workers/engine/fsdp/transformer_impl.py` | New `calculate_init_state_value` flag → emits `init_state_value` (logsumexp of logits per token) |
| Loss dispatcher | `verl/workers/utils/losses.py` | Routes `V_θ`, `V_ref`, `ref_log_prob`, and β to the ReVal loss; suppresses the entropy/KL add-ons (absorbed in the Bellman residual) |
| Trainer | `verl/trainer/main_reval.py` | `RevalTrainer(PPOTrainer)` injects `calculate_init_state_value` into the ref + actor forwards, persists `ref_init_state_value` on the TransferQueue, runs the FIFO replay buffer (1 on-policy + 1 off-policy update/step), and performs the periodic π_ref ← π_θ reset |
| Weight sync | `verl/workers/engine_workers.py`, `verl/workers/engine/fsdp/transformer_impl.py` | `sync_ref_with_actor` worker RPC + `FSDPEngine.load_per_tensor_param` (inverse of `get_per_tensor_param`) do the in-memory actor→ref copy for the reset |
| Config | `verl/trainer/config/algorithm.py` | `reval_beta`, `reval_normalize_reward`, `reval_ref_reset_freq` (note: `reval_updates_per_iter` is unused — K=2 is structural) |

The dataset and rollout plumbing (TransferQueue, vLLM, AgentLoop) are unchanged.

## Paper-faithful run (DeepSeek-R1-Distill-Qwen-1.5B / DeepScaleR)

```bash
bash examples/reval_trainer/run_dpsk_r1_distill_1_5b_fsdp.sh
```

Defaults reproduce Section 5.1/5.3 of the paper:

| Knob | Value | Source |
| --- | --- | --- |
| Base model | `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B` | Table 1 |
| Dataset | DeepScaleR | Section 5.1 |
| `M_PROMPTS × ROLLOUT_N` | 128 × 8 = 1024 | Section 5.1 |
| `REVAL_BETA` | 0.002 | Section 5.5.3 (≈5K-token responses) |
| K (updates/step) | 2 = 1 on-policy + 1 off-policy (FIFO buffer) | Section 4.3, Eq. 3 |
| `REVAL_REF_RESET_FREQ` | 0 (off; 200 for short-response models) | Section 5.5.2 |
| Temperature | 1.0 | Section 5.1 |
| `TOTAL_TRAINING_STEPS` | 650 | Section 5.1 |
| Reward design | Group-mean-normalized | Section 5.5.4 (best variant) |

Override anything from the CLI:

```bash
REVAL_BETA=0.02 EXPERIMENT_NAME=qwen2_5_math_7b_check \
MODEL_PATH=Qwen/Qwen2.5-Math-7B MAX_RESPONSE_LENGTH=1024 \
bash examples/reval_trainer/run_dpsk_r1_distill_1_5b_fsdp.sh
```

## Known gaps from the paper

1. **In-place reference-policy reset (every 200 steps)** is wired.
   `RevalTrainer._reset_reference_policy()` copies the actor weights into the
   reference engine in memory via the `sync_ref_with_actor` worker RPC (both
   engines are colocated, so the copy is local to each rank — no disk
   round-trip), then flushes the FIFO buffer (cached `ref_log_prob` /
   `ref_init_state_value` were computed against the *old* reference). It is
   **disabled by default** (`REVAL_REF_RESET_FREQ=0`), which is paper-faithful
   for the headline 1.5B run; set `REVAL_REF_RESET_FREQ=200` for short-response
   models (Qwen2.5-Math-7B in Section 5.5.2). Set `REVAL_VERIFY_REF_RESET=1` to
   assert π_ref ≡ π_θ right after each reset (Calibrated Initialization,
   Proposition 2) — recommended once on a short run. The buffer is flushed
   rather than ref-value-refreshed: correct, but it costs a few steps of pure
   on-policy updates while the FIFO refills (refresh is a possible follow-up).
2. **Persistent FIFO replay across iterations (M=5120)** is implemented:
   `RevalReplayBuffer` is a real cross-iteration FIFO over TransferQueue keys.
   Each step runs `K=2` updates structurally — 1 on-policy on the fresh batch +
   1 off-policy sampled uniformly from the buffer — and `actor.ppo_epochs` is
   forced to 1 (K does **not** come from `ppo_epochs`). The `fit()` loop keeps
   buffered keys alive across iterations by shadowing `tq.kv_clear`.
3. **Fused-kernel forward** is rejected when `calculate_init_state_value=True`
   because fused kernels don't materialize logits. Disable fused kernels (the
   verl default for FSDP is already non-fused).
4. **Megatron backend** is not patched — the V-extraction lives only in
   `verl/workers/engine/fsdp/transformer_impl.py`. Megatron support requires
   the analogous edit to its `prepare_model_outputs`.

## Quick sanity checks before launching a real run

```bash
# Imports + registration
python -c "from verl.trainer.ppo.core_algos import ADV_ESTIMATOR_REGISTRY, POLICY_LOSS_REGISTRY; \
           assert 'reval' in ADV_ESTIMATOR_REGISTRY and 'reval' in POLICY_LOSS_REGISTRY; print('ok')"

# Trainer entry point
python -c "from verl.trainer import main_reval; print(main_reval.RevalTrainer)"
```

## Verification recommended by `CLAUDE.md`

- [ ] `gh issue view <issue> --repo verl-project/verl --comments` and
      `gh pr list --repo verl-project/verl --search "reval"` — confirm no
      duplicate work upstream.
- [ ] Run the smoke test (the two `python -c` lines above).
- [ ] Run a short end-to-end with `TOTAL_TRAINING_STEPS=5` against a small
      math dataset before launching the full 650-step run.
- [ ] If you upstream a PR, the description must include the duplicate-work
      check, your test commands and their results, and a clear statement that
      AI assistance was used.
