#!/bin/bash
# Per-node launcher for ReVal on Miyabi-G.
# Invoked by mpirun (one rank per node). The last rank starts the Ray head and
# runs `verl.trainer.main_reval`; the other ranks join as Ray workers.
#
# Expects the parent (submit_miyabi.sh) to forward NUM_NODES, NUM_GPUS,
# SERVER_NODE, all HF cache paths, all REVAL_* knobs, and HOME via `mpirun -x`.

set -x

HOSTNAME=$(hostname -s)
echo "[${HOSTNAME}] OMPI_COMM_WORLD_SIZE=${OMPI_COMM_WORLD_SIZE}"
echo "[${HOSTNAME}] OMPI_COMM_WORLD_RANK=${OMPI_COMM_WORLD_RANK}"
echo "[${HOSTNAME}] SERVER_NODE=${SERVER_NODE} NUM_NODES=${NUM_NODES} NUM_GPUS=${NUM_GPUS}"

export MACHINE_RANK=${OMPI_COMM_WORLD_RANK}
export CUDA_VISIBLE_DEVICES=0
export PYTHONUNBUFFERED=1

# vLLM defaults that match the rest of the verl ecosystem on this cluster.
unset VLLM_ATTENTION_BACKEND
export VLLM_USE_V1=1
export VLLM_ENABLE_CUDA_GRAPH=true
export VLLM_ENFORCE_EAGER=false

# Activate venv inside each rank's shell (mpirun strips most shell state).
source /work/go39/b20033/code/generalization_venv/bin/activate

# Run from the verl repo root so `python -m verl.trainer.main_reval` resolves.
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

    echo "[${HOSTNAME}] launching ReVal trainer"
    # Defer all Hydra overrides to the existing run script for a single source of truth.
    # NNODES / NGPUS_PER_NODE come from the PBS allocation, not the run script's defaults.
    NNODES="${NUM_NODES}" \
    NGPUS_PER_NODE="${NUM_GPUS}" \
    bash "${PBS_O_WORKDIR}/examples/reval_trainer/run_dpsk_r1_distill_1_5b_fsdp.sh"
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
