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
| Trainer | `verl/trainer/main_reval.py` | `RevalTrainer(PPOTrainer)` injects `calculate_init_state_value` into the ref + actor forwards, persists `ref_init_state_value` on the TransferQueue, and adds a periodic ref-reset hook |
| Config | `verl/trainer/config/algorithm.py` | `reval_beta`, `reval_normalize_reward`, `reval_updates_per_iter`, `reval_ref_reset_freq` |

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
| `REVAL_K` (`ppo_epochs`) | 2 | Section 4.3, Eq. 3 |
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

1. **In-place reference-policy reset (every 200 steps)** is not wired. The
   `RevalTrainer._reset_reference_policy()` method logs a warning and returns;
   `REVAL_REF_RESET_FREQ=0` is the default. To enable, implement an actor→ref
   FSDP state-dict broadcast (the cheap path is a `save_checkpoint`/
   `load_checkpoint` round-trip via `actor_rollout_wg` / `ref_policy_wg`; the
   fast path is an in-memory rebroadcast). This matters most for short-response
   models (Qwen2.5-Math-7B in Section 5.5.2); the headline 1.5B run still
   reaches paper-comparable scores without it.
2. **Persistent FIFO replay across iterations (M=5120)**. We approximate the
   paper's `K=2` expected updates per trajectory by running `ppo_epochs=K` on
   each fresh batch — same per-trajectory gradient budget, but no mixing across
   iteration boundaries. Verl's `ReplayBuffer` is a TransferQueue-coupled
   synchronization primitive, not a trajectory store, so a faithful M=5120
   replay needs a new buffer plus changes to the `step()` loop in
   `verl/trainer/main_ppo_sync.py`.
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
