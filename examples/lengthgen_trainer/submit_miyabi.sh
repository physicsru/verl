#!/bin/bash
# PBS submit script for length-generalization GRPO on Miyabi-G.
#
#   TASK=max_subarray CONDITION=code qsub examples/lengthgen_trainer/submit_miyabi.sh
#
# Override via env vars: TASK, CONDITION, NNODES, MODEL_PATH, etc.

#PBS -q small-g
#PBS -l select=4:mpiprocs=1
#PBS -l walltime=24:00:00
#PBS -W group_list=go39
#PBS -N lengthgen-grpo
#PBS -j oe

set -x

# --- modules + env ---
source /home/b20033/.bashrc

SAVED_OMPI_MCA_plm_rsh_agent=${OMPI_MCA_plm_rsh_agent:-}
SAVED_OMPI_MCA_orte_default_hostfile=${OMPI_MCA_orte_default_hostfile:-}
SAVED_OMPI_MCA_rmaps_base_mapping_policy=${OMPI_MCA_rmaps_base_mapping_policy:-}

module purge
module load cuda/12.9

[ -n "${SAVED_OMPI_MCA_plm_rsh_agent}" ] && \
    export OMPI_MCA_plm_rsh_agent="${SAVED_OMPI_MCA_plm_rsh_agent}"
[ -n "${SAVED_OMPI_MCA_orte_default_hostfile}" ] && \
    export OMPI_MCA_orte_default_hostfile="${SAVED_OMPI_MCA_orte_default_hostfile}"
[ -n "${SAVED_OMPI_MCA_rmaps_base_mapping_policy}" ] && \
    export OMPI_MCA_rmaps_base_mapping_policy="${SAVED_OMPI_MCA_rmaps_base_mapping_policy}"

export CC=gcc
export CXX=g++
export CUDA_HOME=/work/opt/local/aarch64/cores/cuda/12.9
export CUDNN_HOME=/work/opt/local/aarch64/apps/cuda/12.9/cudnn/9.10.1.4

remove_path_entries() {
  local var_name=$1
  local forbidden=$2
  local old_value=${!var_name:-}
  local new_value=
  local entry
  [ -z "${old_value}" ] && return
  IFS=: read -r -a entries <<< "${old_value}"
  for entry in "${entries[@]}"; do
    [ -z "${entry}" ] && continue
    [[ "${entry}" == *"${forbidden}"* ]] && continue
    if [ -z "${new_value}" ]; then new_value=${entry}
    else new_value=${new_value}:${entry}
    fi
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

# --- node topology ---
export NUM_NODES=$(wc -l < "$PBS_NODEFILE")
export NUM_GPUS=1
export NUM_PROCESSES=$(( NUM_GPUS * NUM_NODES ))
export MASTER_ADDR=$(head -1 "$PBS_NODEFILE")
export MASTER_PORT=29500

cd "${PBS_O_WORKDIR}"

# --- caches ---
export PIP_CACHE_DIR=/work/gj26/b20033/pip_cache
export HF_HOME=/work/gj26/b20033/HF_HOME
export HF_MODULES_CACHE=/work/gj26/b20033/hf_cache
export HF_DATASETS_CACHE=/work/gj26/b20033/hf_cache
export TRANSFORMERS_CACHE=/work/gj26/b20033/model_path
export TRITON_CACHE_DIR=/work/gj26/b20033/triton
export HOME=/work/go39/b20033

# --- wandb ---
export WANDB_API_KEY=${WANDB_API_KEY:-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}
export WANDB_ENTITY=${WANDB_ENTITY:-ru-wang}
export WANDB_PROJECT=${WANDB_PROJECT:-verl_lengthgen}

# --- experiment knobs ---
export TASK=${TASK:-max_subarray}
export CONDITION=${CONDITION:-code}
export MODEL_PATH=${MODEL_PATH:-Qwen/Qwen3-4B}
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-${TASK}_${CONDITION}_qwen3_4b}
export PROJECT_NAME=${PROJECT_NAME:-verl_lengthgen}

export NNODES=${NUM_NODES}
export NGPUS_PER_NODE=${NUM_GPUS}
export M_PROMPTS=${M_PROMPTS:-64}
export ROLLOUT_N=${ROLLOUT_N:-8}
export PPO_MINI_BATCH_SIZE=${PPO_MINI_BATCH_SIZE:-64}
export PPO_MICRO_BATCH_SIZE_PER_GPU=${PPO_MICRO_BATCH_SIZE_PER_GPU:-2}
export LOG_PROB_MICRO_BATCH_SIZE_PER_GPU=${LOG_PROB_MICRO_BATCH_SIZE_PER_GPU:-2}
export MAX_PROMPT_LENGTH=${MAX_PROMPT_LENGTH:-2048}
export MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-4096}
export ACTOR_LR=${ACTOR_LR:-1e-6}
export ROLLOUT_TP=${ROLLOUT_TP:-1}
export ROLLOUT_GPU_MEM_UTIL=${ROLLOUT_GPU_MEM_UTIL:-0.6}
export ROLLOUT_TEMPERATURE=${ROLLOUT_TEMPERATURE:-1.0}
export TEST_FREQ=${TEST_FREQ:-10}
export SAVE_FREQ=${SAVE_FREQ:-50}
export TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-500}
export TOTAL_EPOCHS=${TOTAL_EPOCHS:-15}

# --- activate venv ---
source /work/go39/b20033/code/generalization_venv/bin/activate
unset OMPI_MCA_mca_base_env_list

export PYTHONUNBUFFERED=1
export HYDRA_FULL_ERROR=1
export NCCL_DEBUG=INFO

# --- launch ---
mpirun --np "$NUM_NODES" \
    --hostfile "$PBS_NODEFILE" \
    -bind-to none -map-by node \
    -x MASTER_ADDR -x MASTER_PORT \
    -x NUM_NODES -x NUM_GPUS -x NUM_PROCESSES \
    -x PATH -x LD_LIBRARY_PATH -x CC -x CXX \
    -x CUDA_HOME \
    -x PIP_CACHE_DIR -x HF_HOME -x HF_MODULES_CACHE -x HF_DATASETS_CACHE \
    -x TRANSFORMERS_CACHE -x TRITON_CACHE_DIR -x HOME \
    -x WANDB_API_KEY -x WANDB_ENTITY -x WANDB_PROJECT \
    -x PYTHONUNBUFFERED -x HYDRA_FULL_ERROR -x NCCL_DEBUG \
    -x TASK -x CONDITION -x MODEL_PATH \
    -x EXPERIMENT_NAME -x PROJECT_NAME \
    -x NNODES -x NGPUS_PER_NODE \
    -x M_PROMPTS -x ROLLOUT_N -x PPO_MINI_BATCH_SIZE \
    -x PPO_MICRO_BATCH_SIZE_PER_GPU -x LOG_PROB_MICRO_BATCH_SIZE_PER_GPU \
    -x MAX_PROMPT_LENGTH -x MAX_RESPONSE_LENGTH -x ACTOR_LR \
    -x ROLLOUT_TP -x ROLLOUT_GPU_MEM_UTIL -x ROLLOUT_TEMPERATURE \
    -x TEST_FREQ -x SAVE_FREQ -x TOTAL_TRAINING_STEPS -x TOTAL_EPOCHS \
    bash "${PBS_O_WORKDIR}/examples/lengthgen_trainer/lengthgen_per_node.sh"
