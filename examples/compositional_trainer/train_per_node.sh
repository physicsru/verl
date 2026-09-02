#!/usr/bin/env bash
# Per-node bootstrap for compositional-generalization training on Miyabi.
# Called by mpirun from train_pbs_header.sh. The last rank becomes the Ray head
# and launches the trainer; other ranks join the Ray cluster.
#
# RL_METHOD selects the algorithm:
#   grpo  -> verl.trainer.main_ppo   (adv_estimator=grpo, policy-gradient baseline)
#   reval -> verl.trainer.main_reval (adv_estimator=reval, value-based off-policy)
set -x

HOSTNAME=$(hostname -s)
echo "[${HOSTNAME}] rank=${OMPI_COMM_WORLD_RANK}/${OMPI_COMM_WORLD_SIZE} SERVER=${SERVER_NODE}"

export MACHINE_RANK=${OMPI_COMM_WORLD_RANK}
export CUDA_VISIBLE_DEVICES=0
export PYTHONUNBUFFERED=1
unset VLLM_ATTENTION_BACKEND
export VLLM_USE_V1=1
export VLLM_ENABLE_CUDA_GRAPH=true
export VLLM_ENFORCE_EAGER=false

source /work/go39/b20033/code/generalization_venv/bin/activate
cd "${PBS_O_WORKDIR:-/work/go39/b20033/code/generalization/verl}"

# ---- defaults (override via env) ----
RL_METHOD=${RL_METHOD:-grpo}
M_PROMPTS=${M_PROMPTS:-64}
ROLLOUT_N=${ROLLOUT_N:-8}
PPO_MINI_BATCH_SIZE=${PPO_MINI_BATCH_SIZE:-64}
MAX_PROMPT_LENGTH=${MAX_PROMPT_LENGTH:-2048}
MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-4096}
TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-500}
TOTAL_EPOCHS=${TOTAL_EPOCHS:-1}
TEST_FREQ=${TEST_FREQ:-10}
SAVE_FREQ=${SAVE_FREQ:-100}
MODEL_PATH=${MODEL_PATH:-Qwen/Qwen3-4B-Base}
VAL_BATCH_SIZE=${VAL_BATCH_SIZE:-500}
LOG_VAL_GENERATIONS=${LOG_VAL_GENERATIONS:-0}
ROLLOUT_DATA_DIR=${ROLLOUT_DATA_DIR:-}
COMPOSITIONAL_NUM_EXAMINE=${COMPOSITIONAL_NUM_EXAMINE:-3}
export COMPOSITIONAL_NUM_EXAMINE
# SAVE_HF_MODEL=1 -> also write full HF weights under <ckpt>/actor/huggingface so
# the next stage can load it directly as model.path (used for stage1->stage2 chaining).
SAVE_HF_MODEL=${SAVE_HF_MODEL:-0}
# GRPO KL-to-reference coefficient (use_kl_loss); RA-RL uses 0.01 (run_rl_ra.sh).
KL_COEF=${KL_COEF:-0.001}

# ReVal knobs (only used when RL_METHOD=reval).
REVAL_BETA=${REVAL_BETA:-0.002}
REVAL_K=${REVAL_K:-2}
REVAL_REF_RESET_FREQ=${REVAL_REF_RESET_FREQ:-0}
REVAL_NORMALIZE_REWARD=${REVAL_NORMALIZE_REWARD:-True}
REVAL_BUFFER_SIZE=${REVAL_BUFFER_SIZE:-5120}

# TRAIN_FILE may be a comma-separated list -> data-level replay (e.g. add the
# Stage-1 / S parquet alongside the current layer to avoid forgetting).
COMMON_DATA=(
    data.train_files="[${TRAIN_FILE}]"
    "data.val_files=[${VAL_FILES}]"
    data.train_batch_size=${M_PROMPTS}
    data.max_prompt_length=${MAX_PROMPT_LENGTH}
    data.max_response_length=${MAX_RESPONSE_LENGTH}
    data.filter_overlong_prompts=True
    data.truncation=error
    data.val_max_samples=-1
    data.val_batch_size=${VAL_BATCH_SIZE}
)

COMMON_MODEL_ACTOR=(
    actor_rollout_ref.model.path=${MODEL_PATH}
    actor_rollout_ref.model.use_remove_padding=True
    actor_rollout_ref.model.enable_gradient_checkpointing=True
    'actor_rollout_ref.model.custom_chat_template=${oc.env:CUSTOM_CHAT_TEMPLATE}'
    actor_rollout_ref.actor.optim.lr=1e-6
    actor_rollout_ref.actor.ppo_mini_batch_size=${PPO_MINI_BATCH_SIZE}
    actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=16
    actor_rollout_ref.actor.entropy_coeff=0
    actor_rollout_ref.actor.fsdp_config.param_offload=False
    actor_rollout_ref.actor.fsdp_config.optimizer_offload=False
    actor_rollout_ref.actor.use_dynamic_bsz=True
    actor_rollout_ref.actor.ppo_max_token_len_per_gpu=16384
)

COMMON_ROLLOUT_REF=(
    actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu=16
    actor_rollout_ref.rollout.tensor_model_parallel_size=1
    actor_rollout_ref.rollout.name=vllm
    actor_rollout_ref.rollout.gpu_memory_utilization=0.85
    actor_rollout_ref.rollout.temperature=1.0
    actor_rollout_ref.rollout.n=${ROLLOUT_N}
    actor_rollout_ref.rollout.enable_chunked_prefill=False
    actor_rollout_ref.rollout.free_cache_engine=True
    actor_rollout_ref.rollout.log_prob_use_dynamic_bsz=True
    actor_rollout_ref.rollout.log_prob_max_token_len_per_gpu=8192
    actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu=16
    actor_rollout_ref.ref.fsdp_config.param_offload=True
    actor_rollout_ref.ref.log_prob_use_dynamic_bsz=True
    actor_rollout_ref.ref.log_prob_max_token_len_per_gpu=8192
)

COMMON_TRAINER=(
    reward.custom_reward_function.path=${REWARD_FN}
    reward.custom_reward_function.name=compute_score
    trainer.critic_warmup=0
    trainer.logger=[console,wandb]
    trainer.project_name=${WANDB_PROJECT}
    trainer.experiment_name=${EXPERIMENT_NAME}
    trainer.n_gpus_per_node=1
    trainer.nnodes=${NUM_NODES}
    trainer.save_freq=${SAVE_FREQ}
    trainer.test_freq=${TEST_FREQ}
    trainer.total_epochs=${TOTAL_EPOCHS}
    trainer.total_training_steps=${TOTAL_TRAINING_STEPS}
    trainer.log_val_generations=${LOG_VAL_GENERATIONS}
    ${SAVE_DIR:+trainer.default_local_dir=${SAVE_DIR}}
    ${ROLLOUT_DATA_DIR:+trainer.rollout_data_dir=${ROLLOUT_DATA_DIR}}
)

if [[ "${SAVE_HF_MODEL}" == "1" ]]; then
    COMMON_TRAINER+=("actor_rollout_ref.actor.checkpoint.save_contents=[model,optimizer,extra,hf_model]")
fi

# Bound checkpoint disk on long runs (keep only the last N actor ckpts).
if [[ -n "${CKPT_KEEP}" ]]; then
    COMMON_TRAINER+=("trainer.max_actor_ckpt_to_keep=${CKPT_KEEP}")
fi

if [[ "${RL_METHOD}" == "reval" ]]; then
    ENTRYPOINT="verl.trainer.main_reval"
    METHOD_ARGS=(
        algorithm.adv_estimator=reval
        algorithm.reval_beta=${REVAL_BETA}
        algorithm.reval_updates_per_iter=${REVAL_K}
        algorithm.reval_ref_reset_freq=${REVAL_REF_RESET_FREQ}
        algorithm.reval_normalize_reward=${REVAL_NORMALIZE_REWARD}
        algorithm.reval_buffer_size=${REVAL_BUFFER_SIZE}
        algorithm.use_kl_in_reward=False
        algorithm.rollout_correction.rollout_is=sequence
        algorithm.rollout_correction.rollout_is_threshold=2.0
        actor_rollout_ref.actor.ppo_epochs=${REVAL_K}
        actor_rollout_ref.actor.policy_loss.loss_mode=reval
        actor_rollout_ref.actor.policy_loss.reval_beta=${REVAL_BETA}
        actor_rollout_ref.actor.clip_ratio_low=0.2
        actor_rollout_ref.actor.clip_ratio_high=0.28
        actor_rollout_ref.actor.use_kl_loss=False
    )
else
    ENTRYPOINT="verl.trainer.main_ppo"
    METHOD_ARGS=(
        algorithm.adv_estimator=grpo
        algorithm.use_kl_in_reward=False
        actor_rollout_ref.actor.ppo_epochs=1
        actor_rollout_ref.actor.use_kl_loss=True
        actor_rollout_ref.actor.kl_loss_coef=${KL_COEF:-0.001}
        actor_rollout_ref.actor.kl_loss_type=low_var_kl
    )
fi

if [[ "${OMPI_COMM_WORLD_RANK}" == "$(( NUM_NODES - 1 ))" ]]; then
    echo "[${HOSTNAME}] starting Ray head on ${SERVER_NODE}:6379"
    ray start --head --node-ip-address "${SERVER_NODE}" --port 6379 \
        --num-cpus 72 --num-gpus "${NUM_GPUS}" --disable-usage-stats
    sleep 60
    echo "[${HOSTNAME}] launching ${RL_METHOD} trainer (${ENTRYPOINT}): exp=${EXPERIMENT_NAME}"
    python3 -m "${ENTRYPOINT}" \
        "${METHOD_ARGS[@]}" \
        "${COMMON_DATA[@]}" \
        "${COMMON_MODEL_ACTOR[@]}" \
        "${COMMON_ROLLOUT_REF[@]}" \
        "${COMMON_TRAINER[@]}"
    HEAD_EXIT=$?
    echo "[${HOSTNAME}] trainer exited with ${HEAD_EXIT}"
    exit ${HEAD_EXIT}
else
    sleep 30
    echo "[${HOSTNAME}] joining Ray head at ${SERVER_NODE}:6379"
    ray start --address "${SERVER_NODE}:6379" --num-cpus 72 --num-gpus "${NUM_GPUS}" --block
fi
