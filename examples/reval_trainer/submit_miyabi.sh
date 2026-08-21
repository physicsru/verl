#!/bin/bash
# PBS submit script for ReVal on Miyabi-G.
#
#   qsub examples/reval_trainer/submit_miyabi.sh
#
# Overrides (set in the environment before qsub or via -v VAR=...):
#   NNODES                      number of Miyabi GH200 nodes (default 8)
#   WALLTIME                    walltime hh:mm:ss (default 06:00:00)
#   MODEL_PATH                  HF model id or local snapshot path
#   TRAIN_FILE / TEST_FILE      DeepScaleR parquet paths under /work/gj26/b20033
#   EXPERIMENT_NAME             wandb run name

#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=24:00:00
#PBS -W group_list=go39
#PBS -N reval-dpsk-1_5b
#PBS -j oe

set -x

# --- modules + env (must mirror install.sh / install_verl_deps.sh /
# build_fa2_and_test.sh exactly so runtime sees the same CUDA/cuDNN the venv
# was built against). The only post-install addition is the hpcx mpirun bin
# dir (appended AFTER the /cores/nvidia/ strip), so we get mpirun without
# pulling in HPC-SDK CUDA via `module load nvidia/25.9 + nv-hpcx/25.9`. ---
source /home/b20033/.bashrc

# PBS batch jobs on Miyabi auto-load nvidia/25.9 + nv-hpcx/25.9, which sets the
# OMPI MCA env vars that make mpirun use the PBS-aware launcher (pbs_tmrsh) —
# no ssh, so no host-key / publickey issues. `module purge` below wipes those
# env vars, so capture them here and restore after purge. This matches the
# Singularity+MPI pattern in examples/reval_trainer/SKILL.md without re-adding
# HPC-SDK CUDA paths to PATH/LD_LIBRARY_PATH.
SAVED_OMPI_MCA_plm_rsh_agent=${OMPI_MCA_plm_rsh_agent:-}
SAVED_OMPI_MCA_orte_default_hostfile=${OMPI_MCA_orte_default_hostfile:-}
SAVED_OMPI_MCA_rmaps_base_mapping_policy=${OMPI_MCA_rmaps_base_mapping_policy:-}

module purge
module load cuda/12.9

# Restore the PBS-aware OMPI launcher config captured above.
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

# Append ONLY hpcx mpirun's bin so multinode launching works. We don't
# `module load nvidia/25.9 + nv-hpcx/25.9` because that would re-add HPC-SDK
# CUDA / math_libs / compilers paths that the install scripts deliberately
# stripped — diverging the runtime env from install would risk torch/vllm
# (cu129) loading the wrong CUDA libs. mpirun itself has no MPI rpath deps
# (only glibc), so a bare bin-dir append is enough for the launcher.
export HPCX_MPIRUN_BIN=/work/opt/local/aarch64/cores/nvidia/25.9/Linux_aarch64/25.9/comm_libs/hpcx/bin
export PATH=${PATH}:${HPCX_MPIRUN_BIN}

# --- node topology ---
export NUM_NODES=$(wc -l < "$PBS_NODEFILE")
export NUM_GPUS=1
export NUM_PROCESSES=$(( NUM_GPUS * NUM_NODES ))
export MASTER_ADDR=$(head -1 "$PBS_NODEFILE")
export MASTER_PORT=29500
export SERVER_NODE=$(tail -n 1 "$PBS_NODEFILE")

cd "${PBS_O_WORKDIR}"

# --- caches (gj26 share holds pretrained weights / hf hub / triton) ---
export PIP_CACHE_DIR=/work/gj26/b20033/pip_cache
export HF_HOME=/work/gj26/b20033/HF_HOME
export HF_MODULES_CACHE=/work/gj26/b20033/hf_cache
export HF_DATASETS_CACHE=/work/gj26/b20033/hf_cache
export TRANSFORMERS_CACHE=/work/gj26/b20033/model_path
export TRITON_CACHE_DIR=/work/gj26/b20033/triton
export HOME=/work/go39/b20033

# --- wandb (read from login env; do NOT hardcode a key here) ---
export WANDB_API_KEY=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
#${WANDB_API_KEY:-}
export WANDB_ENTITY=ru-wang
export WANDB_PROJECT=verl_reval
#export WANDB_PROJECT=${WANDB_PROJECT:-verl_reval}

# --- runtime knobs (override at qsub-time via env) ---
export INFER_BACKEND=${INFER_BACKEND:-vllm}
export MODEL_PATH=${MODEL_PATH:-deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B}
export TRAIN_FILE=${TRAIN_FILE:-/work/go39/b20033/code/generalization/verl/data/deepscaler/train.parquet}
export TEST_FILE=${TEST_FILE:-/work/go39/b20033/code/generalization/verl/data/deepscaler/test.parquet}
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-dpsk_r1_distill_1_5b_deepscaler}
export PROJECT_NAME=${PROJECT_NAME:-verl_reval}
# Which run script the head rank executes — override to launch an ablation variant
# (e.g. run_dpsk_r1_distill_1_5b_fsdp_reset9.sh). Path is relative to the repo root.
export RUN_SCRIPT=${RUN_SCRIPT:-examples/reval_trainer/run_dpsk_r1_distill_1_5b_fsdp.sh}

# Paper knobs — keep aligned with examples/reval_trainer/run_dpsk_r1_distill_1_5b_fsdp.sh
export M_PROMPTS=${M_PROMPTS:-128}
export ROLLOUT_N=${ROLLOUT_N:-8}
export PPO_MINI_BATCH_SIZE=${PPO_MINI_BATCH_SIZE:-128}
export PPO_MICRO_BATCH_SIZE_PER_GPU=${PPO_MICRO_BATCH_SIZE_PER_GPU:-1}
export LOG_PROB_MICRO_BATCH_SIZE_PER_GPU=${LOG_PROB_MICRO_BATCH_SIZE_PER_GPU:-2}
export MAX_PROMPT_LENGTH=${MAX_PROMPT_LENGTH:-1024}
# Paper: DPSK-R1-Distill-1.5B max sequence length 8K total (= 1024 prompt + 7168 response).
export MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-7168}
export ACTOR_LR=${ACTOR_LR:-1e-6}
export REVAL_BETA=${REVAL_BETA:-0.002}
# K=2 is structural (1 on-policy + 1 off-policy update/step); REVAL_K is no longer read.
export REVAL_REF_RESET_FREQ=${REVAL_REF_RESET_FREQ:-0}
# Set to 1 (short run only) to assert pi_ref == pi_theta right after each reset.
export REVAL_VERIFY_REF_RESET=${REVAL_VERIFY_REF_RESET:-0}
export REVAL_NORMALIZE_REWARD=${REVAL_NORMALIZE_REWARD:-True}
# Paper: FIFO replay buffer of 5120 trajectories (off-policy half of K=2).
export REVAL_BUFFER_SIZE=${REVAL_BUFFER_SIZE:-5120}
# Single-GPU-per-node Miyabi: TP=1 is the only viable rollout TP without cross-node TP.
export ROLLOUT_TP=${ROLLOUT_TP:-1}
export ROLLOUT_GPU_MEM_UTIL=${ROLLOUT_GPU_MEM_UTIL:-0.6}
export ROLLOUT_TEMPERATURE=${ROLLOUT_TEMPERATURE:-1.0}
export TEST_FREQ=${TEST_FREQ:-10}
export SAVE_FREQ=${SAVE_FREQ:-50}
export TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-650}
export TOTAL_EPOCHS=${TOTAL_EPOCHS:-30}

# Activate venv (Python 3.12 + torch 2.10 + vllm 0.19.1 — see memory note).
source /work/go39/b20033/code/generalization_venv/bin/activate
unset OMPI_MCA_mca_base_env_list

export PYTHONUNBUFFERED=1
export HYDRA_FULL_ERROR=1
export NCCL_DEBUG=INFO

# --- launch: one mpirun rank per node; the last rank becomes Ray head + trainer ---
# OMPI_MCA_plm_rsh_agent (restored above) points mpirun at the PBS-aware
# launcher, so no ssh-args / host-key / identity-file hacks are needed —
# matches the canonical pattern in examples/reval_trainer/SKILL.md.
mpirun --np "$NUM_NODES" \
    --hostfile "$PBS_NODEFILE" \
    -bind-to none -map-by node \
    -x MASTER_ADDR -x MASTER_PORT -x SERVER_NODE \
    -x NUM_NODES -x NUM_GPUS -x NUM_PROCESSES \
    -x PATH -x LD_LIBRARY_PATH -x CC -x CXX \
    -x CUDA_HOME \
    -x PIP_CACHE_DIR -x HF_HOME -x HF_MODULES_CACHE -x HF_DATASETS_CACHE \
    -x TRANSFORMERS_CACHE -x TRITON_CACHE_DIR -x HOME \
    -x WANDB_API_KEY -x WANDB_ENTITY -x WANDB_PROJECT \
    -x PYTHONUNBUFFERED -x HYDRA_FULL_ERROR -x NCCL_DEBUG \
    -x INFER_BACKEND -x MODEL_PATH -x TRAIN_FILE -x TEST_FILE \
    -x EXPERIMENT_NAME -x PROJECT_NAME \
    -x M_PROMPTS -x ROLLOUT_N -x PPO_MINI_BATCH_SIZE \
    -x PPO_MICRO_BATCH_SIZE_PER_GPU -x LOG_PROB_MICRO_BATCH_SIZE_PER_GPU \
    -x MAX_PROMPT_LENGTH -x MAX_RESPONSE_LENGTH -x ACTOR_LR \
    -x REVAL_BETA -x REVAL_REF_RESET_FREQ -x REVAL_NORMALIZE_REWARD -x REVAL_BUFFER_SIZE \
    -x REVAL_VERIFY_REF_RESET -x RUN_SCRIPT \
    -x ROLLOUT_TP -x ROLLOUT_GPU_MEM_UTIL -x ROLLOUT_TEMPERATURE \
    -x TEST_FREQ -x SAVE_FREQ -x TOTAL_TRAINING_STEPS -x TOTAL_EPOCHS \
    bash "${PBS_O_WORKDIR}/examples/reval_trainer/reval_per_node.sh"
