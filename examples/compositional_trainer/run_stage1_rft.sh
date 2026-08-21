#!/bin/bash
# Stage-1 ITERATIVE RFT (the paper's recipe) on 8 nodes.
#
# Each iteration: data-parallel rollout of the CURRENT model across all nodes ->
# keep correct trajectories -> multi-node FSDP SFT on them -> the new checkpoint
# becomes the model for the next iteration. RL / RFT / SFT stay separate scripts;
# this driver only orchestrates the per-node primitives (_rollout_launch.sh,
# _sft_launch.sh) + build_rft_data.py, each debuggable on its own.
#
#   POOL=paper RFT_ITERS=3 qsub examples/compositional_trainer/run_stage1_rft.sh
#
# Rollout (vLLM, one instance/node) and SFT (FSDP across nodes) are launched as
# separate mpirun phases, so vLLM's GPU memory is freed before FSDP starts.
#
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=48:00:00
#PBS -W group_list=go39
#PBS -N comp-s1-rft
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"
set -e
CT=examples/compositional_trainer

POOL=${POOL:-paper}
RFT_ITERS=${RFT_ITERS:-3}
export N_SAMPLES=${N_SAMPLES:-8}
export ROLLOUT_TEMP=${ROLLOUT_TEMP:-1.0}
export ROLLOUT_TOP_P=${ROLLOUT_TOP_P:-1.0}
export ROLLOUT_MAX_TOKENS=${ROLLOUT_MAX_TOKENS:-1024}
export ROLLOUT_MAX_MODEL_LEN=${ROLLOUT_MAX_MODEL_LEN:-4096}
export MAX_PROBLEMS=${MAX_PROBLEMS:--1}     # -1 = all stage-1 problems (sharded over nodes)
MAX_KEEP=${MAX_KEEP:-4}

# SFT knobs (consumed by _sft_launch.sh)
export TORCH_MASTER_PORT=${TORCH_MASTER_PORT:-29411}
export SFT_EPOCHS=${SFT_EPOCHS:-2}
export SFT_LR=${SFT_LR:-2e-5}
export SFT_MAX_LENGTH=${SFT_MAX_LENGTH:-2048}
export SFT_BATCH=${SFT_BATCH:-128}
export SFT_MICRO_BSZ=${SFT_MICRO_BSZ:-4}

export STAGE1_FILE="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage1_level1/train.parquet"
RFT_ROOT="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage1_rft"
export CUR_MODEL=${MODEL_PATH:-Qwen/Qwen3-4B-Base}   # base for iter 1

resolve_hf_ckpt() { find "$1" -type d -name huggingface 2>/dev/null | sort | tail -1; }

for ((it=1; it<=RFT_ITERS; it++)); do
    echo "==================== RFT iteration ${it}/${RFT_ITERS} (model=${CUR_MODEL}) ===================="
    export RFT_ITER=${it}
    ITDIR="${RFT_ROOT}/iter${it}"
    export ROLLOUT_DIR="${ITDIR}/rollouts"
    SFT_DATA="${ITDIR}/sft_data"
    export EXPERIMENT_NAME="stage1_${POOL}_rft_iter${it}_qwen3_4b"
    export SAVE_DIR="${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}"
    export TRAIN_FILE="${SFT_DATA}/train.parquet"
    export VAL_FILES="${SFT_DATA}/test.parquet"
    export MODEL_PATH="${CUR_MODEL}"

    # 1) data-parallel rollout across all nodes -> ${ROLLOUT_DIR}/rollout_rank*.parquet
    launch_mpi ${CT}/_rollout_launch.sh

    # 2) filter correct trajectories -> SFT data (head node; reads the shard dir)
    python3 ${CT}/build_rft_data.py --rollout_path "${ROLLOUT_DIR}" \
        --out_dir "${SFT_DATA}" --val_size 256 --max_keep_per_problem "${MAX_KEEP}"

    # 3) multi-node FSDP SFT (shared primitive)
    launch_mpi ${CT}/_sft_launch.sh

    NEW_CKPT="$(resolve_hf_ckpt "${SAVE_DIR}")"
    if [ -z "${NEW_CKPT}" ]; then
        echo "[rft][ERROR] no HF checkpoint found under ${SAVE_DIR}; aborting."; exit 1
    fi
    echo "[rft] iteration ${it} done -> ${NEW_CKPT}"
    export CUR_MODEL="${NEW_CKPT}"
done

echo "==================== RFT finished. Final Stage-1 model: ${CUR_MODEL} ===================="
echo "Feed it to Stage 2:  MODEL_PATH=${CUR_MODEL} qsub examples/compositional_trainer/train_stage2.sh"
