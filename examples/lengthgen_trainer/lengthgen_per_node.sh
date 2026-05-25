#!/usr/bin/env bash
# Per-node bootstrap for length-generalization GRPO on Miyabi.
# Launched by mpirun from submit_miyabi.sh (one rank per node).
set -x

OMPI_RANK=${OMPI_COMM_WORLD_RANK:-0}
OMPI_SIZE=${OMPI_COMM_WORLD_SIZE:-1}
IS_HEAD=$(( OMPI_RANK == OMPI_SIZE - 1 ? 1 : 0 ))

if [ "$IS_HEAD" -eq 1 ]; then
    ray start --head --disable-usage-stats \
        --port=6379 \
        --dashboard-host=0.0.0.0 \
        --dashboard-port=8265 \
        --num-gpus=${NUM_GPUS}
    sleep 5
    bash "${PBS_O_WORKDIR}/examples/lengthgen_trainer/run_lengthgen_fsdp.sh"
else
    ray start --address="${MASTER_ADDR}:6379" \
        --num-gpus=${NUM_GPUS}
    sleep infinity
fi
