#!/usr/bin/env bash
# Length-Generalization GRPO | Qwen3-4B-Base | FSDP | vLLM rollout
#
# Two conditions:
#   CONDITION=cot   — plain CoT reasoning baseline
#   CONDITION=code  — code-first reasoning (method)
#
# Three tasks: max_subarray, lis, knapsack_01

set -xeuo pipefail

# ---- HuggingFace cache paths (Miyabi convention) ----
export HF_HOME=${HF_HOME:-/work/gj26/b20033/HF_HOME}
export HF_MODULES_CACHE=${HF_MODULES_CACHE:-/work/gj26/b20033/hf_cache}
export HF_DATASETS_CACHE=${HF_DATASETS_CACHE:-/work/gj26/b20033/hf_cache}
export TRANSFORMERS_CACHE=${TRANSFORMERS_CACHE:-/work/gj26/b20033/model_path}

# ---- user-adjustable ----
INFER_BACKEND=${INFER_BACKEND:-vllm}
MODEL_PATH=${MODEL_PATH:-Qwen/Qwen3-4B}
TASK=${TASK:-max_subarray}
CONDITION=${CONDITION:-code}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

TRAIN_FILE=${TRAIN_FILE:-${PROJECT_DIR}/data/lengthgen/${TASK}_${CONDITION}/train.parquet}
TEST_FILE=${TEST_FILE:-${PROJECT_DIR}/data/lengthgen/${TASK}_${CONDITION}/test.parquet}
REWARD_FN_PATH=${REWARD_FN_PATH:-${SCRIPT_DIR}/reward_fn.py}

NNODES=${NNODES:-1}
NGPUS_PER_NODE=${NGPUS_PER_NODE:-1}

# Trajectory batch = M_prompts x rollout_n
M_PROMPTS=${M_PROMPTS:-64}
ROLLOUT_N=${ROLLOUT_N:-8}
PPO_MINI_BATCH_SIZE=${PPO_MINI_BATCH_SIZE:-64}
PPO_MICRO_BATCH_SIZE_PER_GPU=${PPO_MICRO_BATCH_SIZE_PER_GPU:-2}
LOG_PROB_MICRO_BATCH_SIZE_PER_GPU=${LOG_PROB_MICRO_BATCH_SIZE_PER_GPU:-2}

# Few-shot prefix + problem can be long
MAX_PROMPT_LENGTH=${MAX_PROMPT_LENGTH:-2048}
# CoT / code reasoning can be long, especially for Knapsack
MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-4096}

ACTOR_LR=${ACTOR_LR:-1e-6}
KL_LOSS_COEF=${KL_LOSS_COEF:-0.001}
ENTROPY_COEFF=${ENTROPY_COEFF:-0}
PPO_EPOCHS=${PPO_EPOCHS:-1}

ROLLOUT_TP=${ROLLOUT_TP:-1}
ROLLOUT_GPU_MEM_UTIL=${ROLLOUT_GPU_MEM_UTIL:-0.6}
ROLLOUT_TEMPERATURE=${ROLLOUT_TEMPERATURE:-1.0}

PROJECT_NAME=${PROJECT_NAME:-verl_lengthgen}
EXPERIMENT_NAME=${EXPERIMENT_NAME:-${TASK}_${CONDITION}_qwen3_4b}
SAVE_FREQ=${SAVE_FREQ:-50}
TEST_FREQ=${TEST_FREQ:-10}
TOTAL_EPOCHS=${TOTAL_EPOCHS:-15}
TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-500}
# ---- end user-adjustable ----

DATA=(
    algorithm.adv_estimator=grpo
    algorithm.use_kl_in_reward=False
    data.train_files=${TRAIN_FILE}
    data.val_files=${TEST_FILE}
    data.train_batch_size=${M_PROMPTS}
    data.max_prompt_length=${MAX_PROMPT_LENGTH}
    data.max_response_length=${MAX_RESPONSE_LENGTH}
    data.filter_overlong_prompts=True
    data.truncation='error'
)

# Base model chat template: just concatenate message content, no chat tokens.
# Passed via env var + oc.env resolver because Jinja2 {% %} conflicts with Hydra CLI.
export CUSTOM_CHAT_TEMPLATE=${CUSTOM_CHAT_TEMPLATE:-"{% for message in messages %}{{ message['content'] }}{% endfor %}"}

MODEL=(
    actor_rollout_ref.model.path=${MODEL_PATH}
    actor_rollout_ref.model.use_remove_padding=True
    actor_rollout_ref.model.enable_gradient_checkpointing=True
    'actor_rollout_ref.model.custom_chat_template=${oc.env:CUSTOM_CHAT_TEMPLATE}'
)

ACTOR=(
    actor_rollout_ref.actor.optim.lr=${ACTOR_LR}
    actor_rollout_ref.actor.ppo_mini_batch_size=${PPO_MINI_BATCH_SIZE}
    actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=${PPO_MICRO_BATCH_SIZE_PER_GPU}
    actor_rollout_ref.actor.ppo_epochs=${PPO_EPOCHS}
    actor_rollout_ref.actor.use_kl_loss=True
    actor_rollout_ref.actor.kl_loss_coef=${KL_LOSS_COEF}
    actor_rollout_ref.actor.kl_loss_type=low_var_kl
    actor_rollout_ref.actor.entropy_coeff=${ENTROPY_COEFF}
    actor_rollout_ref.actor.fsdp_config.param_offload=False
    actor_rollout_ref.actor.fsdp_config.optimizer_offload=False
    actor_rollout_ref.actor.use_dynamic_bsz=True
    actor_rollout_ref.actor.ppo_max_token_len_per_gpu=16384
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
    actor_rollout_ref.rollout.log_prob_max_token_len_per_gpu=8192
)

REF=(
    actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu=${LOG_PROB_MICRO_BATCH_SIZE_PER_GPU}
    actor_rollout_ref.ref.fsdp_config.param_offload=True
    actor_rollout_ref.ref.log_prob_use_dynamic_bsz=True
    actor_rollout_ref.ref.log_prob_max_token_len_per_gpu=8192
)

REWARD=(
    reward.custom_reward_function.path=${REWARD_FN_PATH}
    reward.custom_reward_function.name=compute_score
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

python3 -m verl.trainer.main_ppo \
    "${DATA[@]}" \
    "${MODEL[@]}" \
    "${ACTOR[@]}" \
    "${ROLLOUT[@]}" \
    "${REF[@]}" \
    "${REWARD[@]}" \
    "${TRAINER[@]}" \
    "$@"
