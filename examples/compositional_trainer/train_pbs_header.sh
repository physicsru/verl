#!/bin/bash
# Shared PBS header for compositional-generalization training on Miyabi-G.
# Source this from individual job scripts, then call launch_training.
set -x

source /home/b20033/.bashrc

SAVED_OMPI_MCA_plm_rsh_agent=${OMPI_MCA_plm_rsh_agent:-}
SAVED_OMPI_MCA_orte_default_hostfile=${OMPI_MCA_orte_default_hostfile:-}
SAVED_OMPI_MCA_rmaps_base_mapping_policy=${OMPI_MCA_rmaps_base_mapping_policy:-}

module purge
module load cuda/12.9

[ -n "${SAVED_OMPI_MCA_plm_rsh_agent}" ] && export OMPI_MCA_plm_rsh_agent="${SAVED_OMPI_MCA_plm_rsh_agent}"
[ -n "${SAVED_OMPI_MCA_orte_default_hostfile}" ] && export OMPI_MCA_orte_default_hostfile="${SAVED_OMPI_MCA_orte_default_hostfile}"
[ -n "${SAVED_OMPI_MCA_rmaps_base_mapping_policy}" ] && export OMPI_MCA_rmaps_base_mapping_policy="${SAVED_OMPI_MCA_rmaps_base_mapping_policy}"

export CC=gcc CXX=g++
export CUDA_HOME=/work/opt/local/aarch64/cores/cuda/12.9
export CUDNN_HOME=/work/opt/local/aarch64/apps/cuda/12.9/cudnn/9.10.1.4

remove_path_entries() {
  local var_name=$1 forbidden=$2 old_value=${!var_name:-} new_value= entry
  [ -z "${old_value}" ] && return
  IFS=: read -r -a entries <<< "${old_value}"
  for entry in "${entries[@]}"; do
    [ -z "${entry}" ] && continue
    [[ "${entry}" == *"${forbidden}"* ]] && continue
    new_value=${new_value:+${new_value}:}${entry}
  done
  export "${var_name}=${new_value}"
}
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH CUDA_PATH CUDA_INC_PATH
remove_path_entries PATH /cores/nvidia/
remove_path_entries LD_LIBRARY_PATH /cores/nvidia/
remove_path_entries LIBRARY_PATH /cores/nvidia/
export PATH=${CUDA_HOME}/bin:${PATH}
export LD_LIBRARY_PATH=${CUDA_HOME}/lib64:${CUDNN_HOME}/lib:${CUDNN_HOME}/lib64:${LD_LIBRARY_PATH:-}
export HPCX_MPIRUN_BIN=/work/opt/local/aarch64/cores/nvidia/25.9/Linux_aarch64/25.9/comm_libs/hpcx/bin
export PATH=${PATH}:${HPCX_MPIRUN_BIN}

export NUM_NODES=$(wc -l < "$PBS_NODEFILE")
export NUM_GPUS=1
export MASTER_ADDR=$(head -1 "$PBS_NODEFILE")
export MASTER_PORT=29500
export SERVER_NODE=$(tail -n 1 "$PBS_NODEFILE")

cd "${PBS_O_WORKDIR}"

export PIP_CACHE_DIR=/work/gj26/b20033/pip_cache
export HF_HOME=/work/gj26/b20033/HF_HOME
export HF_MODULES_CACHE=/work/gj26/b20033/hf_cache
export HF_DATASETS_CACHE=/work/gj26/b20033/hf_cache
export TRANSFORMERS_CACHE=/work/gj26/b20033/model_path
export TRITON_CACHE_DIR=/work/gj26/b20033/triton
export HOME=/work/go39/b20033

# wandb key: prefer the env; else read it from the user's existing ~/.netrc at
# runtime (HOME is overridden to /work/go39/... for the venv, so wandb can't find
# /home/b20033/.netrc on its own). No secret is hardcoded in this committed file.
export WANDB_API_KEY=${WANDB_API_KEY:-}
if [ -z "${WANDB_API_KEY}" ] && [ -f /home/b20033/.netrc ]; then
    export WANDB_API_KEY=$(awk '/machine api\.wandb\.ai/{f=1} f{for(i=1;i<=NF;i++) if($i=="password"){print $(i+1); exit}}' /home/b20033/.netrc)
fi
if [ -z "${WANDB_API_KEY}" ]; then
    echo "[warn] no WANDB_API_KEY found -> WANDB_MODE=offline (logs locally; run 'wandb sync' later)"
    export WANDB_MODE=offline
fi
export WANDB_ENTITY=${WANDB_ENTITY:-ru-wang}
export WANDB_PROJECT=${WANDB_PROJECT:-verl_compositional}

source /work/go39/b20033/code/generalization_venv/bin/activate
unset OMPI_MCA_mca_base_env_list

export PYTHONUNBUFFERED=1
export HYDRA_FULL_ERROR=1
export NCCL_DEBUG=WARN

# Base model: concatenate message contents (no chat-role markup), but END each
# assistant turn with EOS. Without it (v1/v2 template), packed no-padding SFT
# taught "after one answer, more text follows": the model cap-filled every
# 4096-token budget with a repeated mantra and RL could never fix stopping
# (EOS never sampled => zero gradient on it). Prompts contain only user
# messages, so rollout/RL prompt token streams are byte-identical to before.
export CUSTOM_CHAT_TEMPLATE="{% for message in messages %}{{ message['content'] }}{% if message['role'] == 'assistant' %}{{ eos_token }}{% endif %}{% endfor %}"

PROJECT_DIR="${PBS_O_WORKDIR}"
# Default = CoT forward reward; job scripts may pre-set/override REWARD_FN
# (e.g. train_stage2_codeexec.sh -> reward_fn_codeexec.py).
export REWARD_FN="${REWARD_FN:-${PROJECT_DIR}/examples/compositional_trainer/reward_fn.py}"
export MODEL_PATH=${MODEL_PATH:-Qwen/Qwen3-4B-Base}

launch_training() {
    mpirun --np "$NUM_NODES" \
        --hostfile "$PBS_NODEFILE" \
        -bind-to none -map-by node \
        -x MASTER_ADDR -x MASTER_PORT -x SERVER_NODE -x NUM_NODES -x NUM_GPUS \
        -x PATH -x LD_LIBRARY_PATH -x CC -x CXX -x CUDA_HOME \
        -x PIP_CACHE_DIR -x HF_HOME -x HF_MODULES_CACHE -x HF_DATASETS_CACHE \
        -x TRANSFORMERS_CACHE -x TRITON_CACHE_DIR -x HOME \
        -x WANDB_API_KEY -x WANDB_ENTITY -x WANDB_PROJECT -x WANDB_MODE \
        -x PYTHONUNBUFFERED -x HYDRA_FULL_ERROR -x NCCL_DEBUG \
        -x CUSTOM_CHAT_TEMPLATE -x REWARD_FN -x MODEL_PATH \
        -x RL_METHOD -x EXPERIMENT_NAME -x SAVE_DIR \
        -x TRAIN_FILE -x VAL_FILES \
        -x M_PROMPTS -x ROLLOUT_N -x PPO_MINI_BATCH_SIZE \
        -x MAX_PROMPT_LENGTH -x MAX_RESPONSE_LENGTH \
        -x TOTAL_TRAINING_STEPS -x TOTAL_EPOCHS \
        -x TEST_FREQ -x SAVE_FREQ -x VAL_BATCH_SIZE \
        -x COMPOSITIONAL_NUM_EXAMINE -x SAVE_HF_MODEL \
        -x LOG_VAL_GENERATIONS -x ROLLOUT_DATA_DIR \
        -x REVAL_BETA -x REVAL_K -x REVAL_REF_RESET_FREQ \
        -x REVAL_NORMALIZE_REWARD -x REVAL_BUFFER_SIZE \
        -x KL_COEF -x CKPT_KEEP -x RA_EPISODE_BONUS \
        bash "${PBS_O_WORKDIR}/examples/compositional_trainer/train_per_node.sh"
}

# Generic multi-node launcher for the RFT/SFT per-node scripts (rollout, sft).
# Each rank gets OMPI_COMM_WORLD_RANK/SIZE; per-iteration vars must be exported
# before calling so mpirun -x forwards their current values.
#   launch_mpi examples/compositional_trainer/_rollout_launch.sh
launch_mpi() {
    local per_node_script="$1"
    mpirun --np "$NUM_NODES" \
        --hostfile "$PBS_NODEFILE" \
        -bind-to none -map-by node \
        -x MASTER_ADDR -x MASTER_PORT -x SERVER_NODE -x NUM_NODES -x NUM_GPUS \
        -x PATH -x LD_LIBRARY_PATH -x CC -x CXX -x CUDA_HOME \
        -x PIP_CACHE_DIR -x HF_HOME -x HF_MODULES_CACHE -x HF_DATASETS_CACHE \
        -x TRANSFORMERS_CACHE -x TRITON_CACHE_DIR -x HOME \
        -x WANDB_API_KEY -x WANDB_ENTITY -x WANDB_PROJECT -x WANDB_MODE \
        -x PYTHONUNBUFFERED -x HYDRA_FULL_ERROR -x NCCL_DEBUG \
        -x CUSTOM_CHAT_TEMPLATE -x REWARD_FN -x MODEL_PATH \
        -x EXPERIMENT_NAME -x SAVE_DIR -x TRAIN_FILE -x VAL_FILES \
        -x TORCH_MASTER_PORT \
        -x SFT_EPOCHS -x SFT_LR -x SFT_MAX_LENGTH -x SFT_BATCH -x SFT_MICRO_BSZ -x SFT_SEED \
        -x CUR_MODEL -x STAGE1_FILE -x ROLLOUT_DIR -x N_SAMPLES \
        -x ROLLOUT_TEMP -x ROLLOUT_TOP_P -x ROLLOUT_MAX_TOKENS \
        -x ROLLOUT_MAX_MODEL_LEN -x MAX_PROBLEMS -x RFT_ITER \
        bash "${PBS_O_WORKDIR}/${per_node_script}"
}
