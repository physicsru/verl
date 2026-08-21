#!/bin/bash
# Stage-1 ITERATIVE RFT for the ONE-SHOT CODE-EXEC condition, on 8 nodes.
#
# Same driver structure as run_stage1_rft.sh (rollout -> keep-correct -> FSDP
# SFT, iterated), but on the *_codeexec prompts and scored by executing the
# model's single program once (reward_fn_codeexec.py). Stage-1 bodies are SHOWN,
# so correct trajectories are ones that reproduce each func_N as working code
# (+ needed imports) — RFT bakes the atomic implementations into the model in
# CODE space, which Stage 2 (bodies hidden) then has to recall and compose.
#
#   POOL=paper RFT_ITERS=3 qsub examples/compositional_trainer/run_stage1_rft_codeexec.sh
#
# Requires the codeexec data first:
#   python examples/compositional_trainer/build_codeexec_data.py --pool ${POOL}
#
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=48:00:00
#PBS -W group_list=go39
#PBS -N comp-s1-rcx
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"
set -e
CT=examples/compositional_trainer
export REWARD_FN="${PBS_O_WORKDIR}/${CT}/reward_fn_codeexec.py"

POOL=${POOL:-paper}
RFT_ITERS=${RFT_ITERS:-3}
export N_SAMPLES=${N_SAMPLES:-8}
export ROLLOUT_TEMP=${ROLLOUT_TEMP:-1.0}
export ROLLOUT_TOP_P=${ROLLOUT_TOP_P:-1.0}
# Code answers (plan + full program incl. copied bodies) run longer than CoT.
export ROLLOUT_MAX_TOKENS=${ROLLOUT_MAX_TOKENS:-2048}
export ROLLOUT_MAX_MODEL_LEN=${ROLLOUT_MAX_MODEL_LEN:-6144}
export MAX_PROBLEMS=${MAX_PROBLEMS:--1}     # -1 = all stage-1 problems (sharded over nodes)
MAX_KEEP=${MAX_KEEP:-4}
MAX_CHARS=${MAX_CHARS:-8000}

# SFT knobs (consumed by _sft_launch.sh)
export TORCH_MASTER_PORT=${TORCH_MASTER_PORT:-29411}
export SFT_EPOCHS=${SFT_EPOCHS:-2}
export SFT_LR=${SFT_LR:-2e-5}
export SFT_MAX_LENGTH=${SFT_MAX_LENGTH:-3072}
export SFT_BATCH=${SFT_BATCH:-128}
export SFT_MICRO_BSZ=${SFT_MICRO_BSZ:-4}

export STAGE1_FILE="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage1_level1_codeexec/train.parquet"
RFT_ROOT="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage1_rft_codeexec"
export CUR_MODEL=${MODEL_PATH:-Qwen/Qwen3-4B-Base}   # base for iter 1

resolve_hf_ckpt() { find "$1" -type d -name huggingface 2>/dev/null | sort | tail -1; }

for ((it=1; it<=RFT_ITERS; it++)); do
    echo "==================== RFT-codeexec iteration ${it}/${RFT_ITERS} (model=${CUR_MODEL}) ===================="
    export RFT_ITER=${it}
    ITDIR="${RFT_ROOT}/iter${it}"
    export ROLLOUT_DIR="${ITDIR}/rollouts"
    SFT_DATA="${ITDIR}/sft_data"
    export EXPERIMENT_NAME="stage1_${POOL}_rftcx_iter${it}_qwen3_4b"
    export SAVE_DIR="${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}"
    export TRAIN_FILE="${SFT_DATA}/train.parquet"
    export VAL_FILES="${SFT_DATA}/test.parquet"
    export MODEL_PATH="${CUR_MODEL}"

    # 1) data-parallel rollout across all nodes -> ${ROLLOUT_DIR}/rollout_rank*.parquet
    launch_mpi ${CT}/_rollout_launch.sh

    # 2) keep trajectories whose PROGRAM EXECUTES to the right output -> SFT data
    python3 ${CT}/build_rft_data.py --rollout_path "${ROLLOUT_DIR}" \
        --out_dir "${SFT_DATA}" --val_size 256 --max_keep_per_problem "${MAX_KEEP}" \
        --max_chars "${MAX_CHARS}" --reward_module reward_fn_codeexec

    # 3) multi-node FSDP SFT (shared primitive)
    launch_mpi ${CT}/_sft_launch.sh

    NEW_CKPT="$(resolve_hf_ckpt "${SAVE_DIR}")"
    if [ -z "${NEW_CKPT}" ]; then
        echo "[rft-cx][ERROR] no HF checkpoint found under ${SAVE_DIR}; aborting."; exit 1
    fi
    echo "[rft-cx] iteration ${it} done -> ${NEW_CKPT}"
    export CUR_MODEL="${NEW_CKPT}"
done

echo "==================== RFT-codeexec finished. Final Stage-1 model: ${CUR_MODEL} ===================="
echo "Feed it to Stage 2:  MODEL_PATH=${CUR_MODEL} POOL=${POOL} qsub examples/compositional_trainer/train_stage2_codeexec.sh"
