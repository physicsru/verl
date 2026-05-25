#!/usr/bin/env bash
# Per-node bootstrap for smoke test. Called by mpirun from smoke_test.sh.
# Matches the working pattern from examples/reval_trainer/reval_per_node.sh.
set -x

HOSTNAME=$(hostname -s)
echo "[${HOSTNAME}] OMPI_COMM_WORLD_RANK=${OMPI_COMM_WORLD_RANK} OMPI_COMM_WORLD_SIZE=${OMPI_COMM_WORLD_SIZE}"
echo "[${HOSTNAME}] SERVER_NODE=${SERVER_NODE} NUM_NODES=${NUM_NODES} NUM_GPUS=${NUM_GPUS}"

export MACHINE_RANK=${OMPI_COMM_WORLD_RANK}
export CUDA_VISIBLE_DEVICES=0
export PYTHONUNBUFFERED=1

unset VLLM_ATTENTION_BACKEND
export VLLM_USE_V1=1
export VLLM_ENABLE_CUDA_GRAPH=true
export VLLM_ENFORCE_EAGER=false

# Activate venv inside each rank (mpirun strips shell state)
source /work/go39/b20033/code/generalization_venv/bin/activate

cd "${PBS_O_WORKDIR:-/work/go39/b20033/code/generalization/verl}"

if [[ "${OMPI_COMM_WORLD_RANK}" == "$(( NUM_NODES - 1 ))" ]]; then
    echo "[${HOSTNAME}] starting Ray head on ${SERVER_NODE}:6379"
    ray start --head \
        --node-ip-address "${SERVER_NODE}" \
        --port 6379 \
        --num-cpus 72 \
        --num-gpus "${NUM_GPUS}" \
        --disable-usage-stats
    sleep 60

    echo "[${HOSTNAME}] launching GRPO trainer"
    python3 -m verl.trainer.main_ppo \
        algorithm.adv_estimator=grpo \
        algorithm.use_kl_in_reward=False \
        data.train_files=${TRAIN_FILE} \
        data.val_files=${TEST_FILE} \
        data.train_batch_size=32 \
        data.max_prompt_length=2048 \
        data.max_response_length=4096 \
        data.filter_overlong_prompts=True \
        data.truncation=error \
        data.val_max_samples=32 \
        actor_rollout_ref.model.path=Qwen/Qwen3-4B \
        actor_rollout_ref.model.use_remove_padding=True \
        actor_rollout_ref.model.enable_gradient_checkpointing=True \
        'actor_rollout_ref.model.custom_chat_template=${oc.env:CUSTOM_CHAT_TEMPLATE}' \
        actor_rollout_ref.actor.optim.lr=1e-6 \
        actor_rollout_ref.actor.ppo_mini_batch_size=32 \
        actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu=2 \
        actor_rollout_ref.actor.ppo_epochs=1 \
        actor_rollout_ref.actor.use_kl_loss=True \
        actor_rollout_ref.actor.kl_loss_coef=0.001 \
        actor_rollout_ref.actor.kl_loss_type=low_var_kl \
        actor_rollout_ref.actor.entropy_coeff=0 \
        actor_rollout_ref.actor.fsdp_config.param_offload=False \
        actor_rollout_ref.actor.fsdp_config.optimizer_offload=False \
        actor_rollout_ref.actor.use_dynamic_bsz=True \
        actor_rollout_ref.actor.ppo_max_token_len_per_gpu=16384 \
        actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu=2 \
        actor_rollout_ref.rollout.tensor_model_parallel_size=1 \
        actor_rollout_ref.rollout.name=vllm \
        actor_rollout_ref.rollout.gpu_memory_utilization=0.6 \
        actor_rollout_ref.rollout.temperature=1.0 \
        actor_rollout_ref.rollout.n=4 \
        actor_rollout_ref.rollout.enable_chunked_prefill=False \
        actor_rollout_ref.rollout.free_cache_engine=True \
        actor_rollout_ref.rollout.log_prob_use_dynamic_bsz=True \
        actor_rollout_ref.rollout.log_prob_max_token_len_per_gpu=8192 \
        actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu=2 \
        actor_rollout_ref.ref.fsdp_config.param_offload=True \
        actor_rollout_ref.ref.log_prob_use_dynamic_bsz=True \
        actor_rollout_ref.ref.log_prob_max_token_len_per_gpu=8192 \
        reward.custom_reward_function.path=${REWARD_FN} \
        reward.custom_reward_function.name=compute_score \
        trainer.critic_warmup=0 \
        trainer.logger=[console,wandb] \
        trainer.project_name=verl_lengthgen \
        trainer.experiment_name=max_subarray_code_smoke \
        trainer.n_gpus_per_node=1 \
        trainer.nnodes=${NUM_NODES} \
        trainer.save_freq=50 \
        trainer.test_freq=25 \
        trainer.total_epochs=15 \
        trainer.total_training_steps=50
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
