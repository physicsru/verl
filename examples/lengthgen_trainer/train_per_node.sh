#!/usr/bin/env bash
# Per-node bootstrap for length-gen GRPO training on Miyabi.
# Called by mpirun. Expects env vars: SERVER_NODE, NUM_NODES, NUM_GPUS,
# TRAIN_FILE, TEST_FILE, REWARD_FN, CUSTOM_CHAT_TEMPLATE, TASK, CONDITION,
# EXPERIMENT_NAME, TOTAL_TRAINING_STEPS, M_PROMPTS, ROLLOUT_N, etc.
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

# Defaults (can be overridden by env)
M_PROMPTS=${M_PROMPTS:-64}
ROLLOUT_N=${ROLLOUT_N:-8}
PPO_MINI_BATCH_SIZE=${PPO_MINI_BATCH_SIZE:-64}
MAX_PROMPT_LENGTH=${MAX_PROMPT_LENGTH:-2048}
MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-4096}
TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-500}
TOTAL_EPOCHS=${TOTAL_EPOCHS:-15}
TEST_FREQ=${TEST_FREQ:-50}
SAVE_FREQ=${SAVE_FREQ:-100}
MODEL_PATH=${MODEL_PATH:-Qwen/Qwen3-4B}
LENGTHGEN_NUM_EXAMINE=${LENGTHGEN_NUM_EXAMINE:-3}
export LENGTHGEN_NUM_EXAMINE
LOG_VAL_GENERATIONS=${LOG_VAL_GENERATIONS:-0}
ROLLOUT_DATA_DIR=${ROLLOUT_DATA_DIR:-}
VAL_BATCH_SIZE=${VAL_BATCH_SIZE:-500}

if [[ "${OMPI_COMM_WORLD_RANK}" == "$(( NUM_NODES - 1 ))" ]]; then
    echo "[${HOSTNAME}] starting Ray head on ${SERVER_NODE}:6379"
    ray start --head \
        --node-ip-address "${SERVER_NODE}" \
        --port 6379 \
        --num-cpus 72 \
        --num-gpus "${NUM_GPUS}" \
        --disable-usage-stats
    sleep 60

    echo "[${HOSTNAME}] launching GRPO trainer: task=${TASK} condition=${CONDITION}"
    python3 -m verl.trainer.main_ppo \
        algorithm.adv_estimator=grpo \
        algorithm.use_kl_in_reward=False \
        data.train_files=${TRAIN_FILE} \
        "data.val_files=[${VAL_FILES}]" \
        data.train_batch_size=${M_PROMPTS} \
        data.max_prompt_length=${MAX_PROMPT_LENGTH} \
        data.max_response_length=${MAX_RESPONSE_LENGTH} \
        data.filter_overlong_prompts=True \
        data.truncation=error \
        data.val_max_samples=-1 \
        data.val_batch_size=${VAL_BATCH_SIZE} \
        actor_rollout_ref.model.path=${MODEL_PATH} \
        actor_rollout_ref.model.use_remove_padding=True \
        actor_rollout_ref.model.enable_gradient_checkpointing=True \
        'actor_rollout_ref.model.custom_chat_template=${oc.env:CUSTOM_CHAT_TEMPLATE}' \
        actor_rollout_ref.actor.optim.lr=1e-6 \
        actor_rollout_ref.actor.ppo_mini_batch_size=${PPO_MINI_BATCH_SIZE} \
        actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=16 \
        actor_rollout_ref.actor.ppo_epochs=1 \
        actor_rollout_ref.actor.use_kl_loss=True \
        actor_rollout_ref.actor.kl_loss_coef=0.001 \
        actor_rollout_ref.actor.kl_loss_type=low_var_kl \
        actor_rollout_ref.actor.entropy_coeff=0 \
        actor_rollout_ref.actor.fsdp_config.param_offload=False \
        actor_rollout_ref.actor.fsdp_config.optimizer_offload=False \
        actor_rollout_ref.actor.use_dynamic_bsz=True \
        actor_rollout_ref.actor.ppo_max_token_len_per_gpu=16384 \
        actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu=16 \
        actor_rollout_ref.rollout.tensor_model_parallel_size=1 \
        actor_rollout_ref.rollout.name=vllm \
        actor_rollout_ref.rollout.gpu_memory_utilization=0.85 \
        actor_rollout_ref.rollout.temperature=1.0 \
        actor_rollout_ref.rollout.n=${ROLLOUT_N} \
        actor_rollout_ref.rollout.enable_chunked_prefill=False \
        actor_rollout_ref.rollout.free_cache_engine=True \
        actor_rollout_ref.rollout.log_prob_use_dynamic_bsz=True \
        actor_rollout_ref.rollout.log_prob_max_token_len_per_gpu=8192 \
        actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu=16 \
        actor_rollout_ref.ref.fsdp_config.param_offload=True \
        actor_rollout_ref.ref.log_prob_use_dynamic_bsz=True \
        actor_rollout_ref.ref.log_prob_max_token_len_per_gpu=8192 \
        reward.custom_reward_function.path=${REWARD_FN} \
        reward.custom_reward_function.name=compute_score \
        trainer.critic_warmup=0 \
        trainer.logger=[console,wandb] \
        trainer.project_name=verl_lengthgen \
        trainer.experiment_name=${EXPERIMENT_NAME} \
        trainer.n_gpus_per_node=1 \
        trainer.nnodes=${NUM_NODES} \
        trainer.save_freq=${SAVE_FREQ} \
        trainer.test_freq=${TEST_FREQ} \
        trainer.total_epochs=${TOTAL_EPOCHS} \
        trainer.total_training_steps=${TOTAL_TRAINING_STEPS} \
        trainer.log_val_generations=${LOG_VAL_GENERATIONS} \
        ${ROLLOUT_DATA_DIR:+trainer.rollout_data_dir=${ROLLOUT_DATA_DIR}}
    HEAD_EXIT=$?
    echo "[${HOSTNAME}] trainer exited with ${HEAD_EXIT}"
    exit ${HEAD_EXIT}
else
    sleep 30
    echo "[${HOSTNAME}] joining Ray head at ${SERVER_NODE}:6379"
    ray start --address "${SERVER_NODE}:6379" \
        --num-cpus 72 \
        --num-gpus "${NUM_GPUS}" \
        --block
fi
