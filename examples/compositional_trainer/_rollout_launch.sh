#!/bin/bash
# RFT ROLLOUT — PER-NODE (data-parallel). Launched once per node by mpirun (via
# launch_mpi). Each node runs an independent vLLM instance over a disjoint shard
# of the Stage-1 problems (shard = OMPI rank), so rollout throughput scales with
# node count. Shards are written to $ROLLOUT_DIR and merged by build_rft_data.py.
#
# Required env (forwarded by mpirun -x): CUR_MODEL STAGE1_FILE ROLLOUT_DIR N_SAMPLES
# Optional: ROLLOUT_TEMP ROLLOUT_TOP_P ROLLOUT_MAX_TOKENS ROLLOUT_MAX_MODEL_LEN
#           MAX_PROBLEMS RFT_ITER
set -x
set -e

HOSTNAME=$(hostname -s)
RANK=${OMPI_COMM_WORLD_RANK:-0}
WSIZE=${OMPI_COMM_WORLD_SIZE:-1}
echo "[${HOSTNAME}] rollout shard=${RANK}/${WSIZE} model=${CUR_MODEL}"

export CUDA_VISIBLE_DEVICES=0
export PYTHONUNBUFFERED=1
export VLLM_USE_V1=1
source /work/go39/b20033/code/generalization_venv/bin/activate
cd "${PBS_O_WORKDIR:-/work/go39/b20033/code/generalization/verl}"

: "${CUR_MODEL:?}"; : "${STAGE1_FILE:?}"; : "${ROLLOUT_DIR:?}"
mkdir -p "${ROLLOUT_DIR}"

# Same --seed on every shard so all pick the SAME global subset, then take a
# disjoint stride. Seed varies by iteration (RFT_ITER) for fresh coverage.
python3 examples/compositional_trainer/rollout_stage1.py \
    --model "${CUR_MODEL}" \
    --in_path "${STAGE1_FILE}" \
    --out_path "${ROLLOUT_DIR}/rollout_rank${RANK}.parquet" \
    --shard_id "${RANK}" --num_shards "${WSIZE}" \
    --n_samples "${N_SAMPLES:-8}" \
    --temperature "${ROLLOUT_TEMP:-1.0}" \
    --top_p "${ROLLOUT_TOP_P:-1.0}" \
    --max_tokens "${ROLLOUT_MAX_TOKENS:-1024}" \
    --max_model_len "${ROLLOUT_MAX_MODEL_LEN:-4096}" \
    --max_problems "${MAX_PROBLEMS:--1}" \
    --seed "${RFT_ITER:-1}"
