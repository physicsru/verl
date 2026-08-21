#!/usr/bin/env bash
# ReVal | DeepSeek-R1-Distill-Qwen-1.5B | DeepScaleR | vLLM rollout | FSDP training
#
# Reference: Wang et al., "Off-Policy Value-Based Reinforcement Learning for
# Large Language Models", arXiv:2603.23355. Section 5.1 + 5.3 (DPSK-R1-Distill-1.5B).
#
# Paper hyperparameters reproduced here:
#   - M_prompts = 128, N_rollouts = 8 (effective trajectory batch = 1024)
#   - β = 0.002
#   - K = 2 updates per fresh batch, realised structurally by the fit loop: 1
#     on-policy update + 1 off-policy update sampled from the FIFO buffer (M=5120).
#     actor.ppo_epochs is forced to 1; K does NOT come from ppo_epochs.
#   - Periodic π_ref ← π_θ reset every 200 steps: implemented (in-memory actor→ref
#     weight copy + buffer flush). DISABLED by default (freq=0), which is
#     paper-faithful for the 1.5B run; set REVAL_REF_RESET_FREQ=200 for
#     short-response models (Section 5.5.2, e.g. Qwen2.5-Math-7B).
#   - Temperature 1.0
#   - 650 iterations on DeepScaleR
#   - Group-mean-normalized reward (paper's best variant, Section 5.5.4)

set -xeuo pipefail

# ---- HuggingFace cache paths (Miyabi gj26 convention) ----
# Override these if you want HF downloads to land somewhere else.
export HF_HOME=${HF_HOME:-/work/gj26/b20033/HF_HOME}
export HF_MODULES_CACHE=${HF_MODULES_CACHE:-/work/gj26/b20033/hf_cache}
export HF_DATASETS_CACHE=${HF_DATASETS_CACHE:-/work/gj26/b20033/hf_cache}
export TRANSFORMERS_CACHE=${TRANSFORMERS_CACHE:-/work/gj26/b20033/model_path}

# ---- user-adjustable ----
INFER_BACKEND=${INFER_BACKEND:-vllm}
MODEL_PATH=${MODEL_PATH:-deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B}
TRAIN_FILE=${TRAIN_FILE:-/work/go39/b20033/code/generalization/verl/data/deepscaler/train.parquet}
TEST_FILE=${TEST_FILE:-/work/go39/b20033/code/generalization/verl/data/deepscaler/test.parquet}
NNODES=${NNODES:-1}
NGPUS_PER_NODE=${NGPUS_PER_NODE:-8}

# Trajectory batch = M_prompts × N_rollouts (paper: 128 × 8 = 1024).
M_PROMPTS=${M_PROMPTS:-128}
ROLLOUT_N=${ROLLOUT_N:-8}
PPO_MINI_BATCH_SIZE=${PPO_MINI_BATCH_SIZE:-128}
PPO_MICRO_BATCH_SIZE_PER_GPU=${PPO_MICRO_BATCH_SIZE_PER_GPU:-1}
LOG_PROB_MICRO_BATCH_SIZE_PER_GPU=${LOG_PROB_MICRO_BATCH_SIZE_PER_GPU:-2}
MAX_PROMPT_LENGTH=${MAX_PROMPT_LENGTH:-1024}
# Paper: DPSK-R1-Distill-1.5B trained with max sequence length 8K (= 8192 total).
MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-7168}

# Core ReVal knobs.
REVAL_BETA=${REVAL_BETA:-0.002}
# K=2 is structural (1 on-policy + 1 off-policy update per step), not a knob.
REVAL_REF_RESET_FREQ=${REVAL_REF_RESET_FREQ:-0}     # 0=off (paper 1.5B); 200 for short-response models
REVAL_NORMALIZE_REWARD=${REVAL_NORMALIZE_REWARD:-True}
# Paper: FIFO buffer of 5120 trajectories (~5 fresh batches at M=128, N=8).
REVAL_BUFFER_SIZE=${REVAL_BUFFER_SIZE:-5120}

ACTOR_LR=${ACTOR_LR:-1e-6}
ROLLOUT_TP=${ROLLOUT_TP:-2}
ROLLOUT_GPU_MEM_UTIL=${ROLLOUT_GPU_MEM_UTIL:-0.6}
ROLLOUT_TEMPERATURE=${ROLLOUT_TEMPERATURE:-1.0}

PROJECT_NAME=${PROJECT_NAME:-verl_reval}
EXPERIMENT_NAME=${EXPERIMENT_NAME:-dpsk_r1_distill_1_5b_deepscaler}
SAVE_FREQ=${SAVE_FREQ:-50}
TEST_FREQ=${TEST_FREQ:-10}     # validation every 10 global steps
TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-650}
TOTAL_EPOCHS=${TOTAL_EPOCHS:-30}
# ---- end user-adjustable ----

DATA=(
    algorithm.adv_estimator=reval
    algorithm.reval_beta=${REVAL_BETA}
    algorithm.reval_ref_reset_freq=${REVAL_REF_RESET_FREQ}
    algorithm.reval_normalize_reward=${REVAL_NORMALIZE_REWARD}
    algorithm.reval_buffer_size=${REVAL_BUFFER_SIZE}
    algorithm.use_kl_in_reward=False
    # Paper: compensation term for vLLM/FSDP inconsistency (sequence-level TIS).
    algorithm.rollout_correction.rollout_is=sequence
    algorithm.rollout_correction.rollout_is_threshold=2.0
    data.train_files=${TRAIN_FILE}
    data.val_files=${TEST_FILE}
    data.train_batch_size=${M_PROMPTS}
    data.max_prompt_length=${MAX_PROMPT_LENGTH}
    data.max_response_length=${MAX_RESPONSE_LENGTH}
    data.filter_overlong_prompts=True
    data.truncation='error'
    # Paper: eval set capped at 100 (random sub-sample).
    data.val_max_samples=100
)

MODEL=(
    actor_rollout_ref.model.path=${MODEL_PATH}
    actor_rollout_ref.model.use_remove_padding=True
    actor_rollout_ref.model.enable_gradient_checkpointing=True
)

ACTOR=(
    actor_rollout_ref.actor.optim.lr=${ACTOR_LR}
    actor_rollout_ref.actor.ppo_mini_batch_size=${PPO_MINI_BATCH_SIZE}
    actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=${PPO_MICRO_BATCH_SIZE_PER_GPU}
    # ppo_epochs is forced to 1 by _force_reval_config (K=2 lives in the fit loop).
    actor_rollout_ref.actor.ppo_epochs=1
    actor_rollout_ref.actor.policy_loss.loss_mode=reval
    actor_rollout_ref.actor.policy_loss.reval_beta=${REVAL_BETA}
    # Paper: asymmetric GRPO IS clipping 0.28 (upper) / 0.2 (lower).
    actor_rollout_ref.actor.clip_ratio_low=0.2
    actor_rollout_ref.actor.clip_ratio_high=0.28
    actor_rollout_ref.actor.use_kl_loss=False
    actor_rollout_ref.actor.entropy_coeff=0
    actor_rollout_ref.actor.fsdp_config.param_offload=False
    actor_rollout_ref.actor.fsdp_config.optimizer_offload=False
    actor_rollout_ref.actor.use_dynamic_bsz=True
    actor_rollout_ref.actor.ppo_max_token_len_per_gpu=20480
)

ROLLOUT=(
    actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu=${LOG_PROB_MICRO_BATCH_SIZE_PER_GPU}
    actor_rollout_ref.rollout.tensor_model_parallel_size=${ROLLOUT_TP}
    actor_rollout_ref.rollout.name=${INFER_BACKEND}
    actor_rollout_ref.rollout.gpu_memory_utilization=${ROLLOUT_GPU_MEM_UTIL}
    actor_rollout_ref.rollout.temperature=${ROLLOUT_TEMPERATURE}
    actor_rollout_ref.rollout.n=${ROLLOUT_N}
    actor_rollout_ref.rollout.enable_chunked_prefill=False
    actor_rollout_ref.rollout.free_cache_engine=True
    actor_rollout_ref.rollout.log_prob_use_dynamic_bsz=True
    actor_rollout_ref.rollout.log_prob_max_token_len_per_gpu=12288
    # Paper: 16 responses per prompt per evaluation phase (must sample).
    actor_rollout_ref.rollout.val_kwargs.n=16
    actor_rollout_ref.rollout.val_kwargs.do_sample=True
    actor_rollout_ref.rollout.val_kwargs.temperature=1.0
    actor_rollout_ref.rollout.val_kwargs.top_p=1.0
    actor_rollout_ref.rollout.val_kwargs.top_k=-1
)

REF=(
    actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu=${LOG_PROB_MICRO_BATCH_SIZE_PER_GPU}
    actor_rollout_ref.ref.fsdp_config.param_offload=True
    actor_rollout_ref.ref.log_prob_use_dynamic_bsz=True
    actor_rollout_ref.ref.log_prob_max_token_len_per_gpu=16384
)

TRAINER=(
    trainer.critic_warmup=0
    trainer.logger='["console","wandb"]'
    trainer.project_name=${PROJECT_NAME}
    trainer.experiment_name=${EXPERIMENT_NAME}
    trainer.n_gpus_per_node=${NGPUS_PER_NODE}
    trainer.nnodes=${NNODES}
    trainer.save_freq=${SAVE_FREQ}
    trainer.test_freq=${TEST_FREQ}
    trainer.total_epochs=${TOTAL_EPOCHS}
    trainer.total_training_steps=${TOTAL_TRAINING_STEPS}
)

EXTRA=(
)

########################### launch ###########################
python3 -m verl.trainer.main_reval \
    "${DATA[@]}" \
    "${MODEL[@]}" \
    "${ACTOR[@]}" \
    "${ROLLOUT[@]}" \
    "${REF[@]}" \
    "${TRAINER[@]}" \
    "${EXTRA[@]}" \
    "$@"
