#!/bin/bash
# Smoke test for the compositional Stage-1 pipeline on the SHORT queue.
# Validates model load, custom chat template, vLLM rollout, reward path, and
# checkpoint+HF export end to end with a handful of steps. Writes to a separate
# *_smoke checkpoint dir so it can't be mistaken for the real Stage-1 ckpt.
#
#   qsub examples/compositional_trainer/smoke_stage1.sh                 # paper/grpo
#   qsub -v "POOL=lenpres,RL_METHOD=reval" examples/compositional_trainer/smoke_stage1.sh
#
# 8 nodes (matches the full run's sharding, avoids OOM); short-g, 1h walltime.
#PBS -q short-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=01:00:00
#PBS -W group_list=go39
#PBS -N comp-s1-smoke
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"

POOL=${POOL:-paper}
RL_METHOD=${RL_METHOD:-grpo}
export RL_METHOD
export SAVE_HF_MODEL=1   # exercise the HF-export path used for stage1->stage2
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-stage1_${POOL}_${RL_METHOD}_smoke}
export SAVE_DIR=${SAVE_DIR:-${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}}

_D="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage1_level1"
export TRAIN_FILE="${_D}/train.parquet"
export VAL_FILES="${_D}/test.parquet"

# Tiny: a few steps, validate then save at the end.
export M_PROMPTS=32
export ROLLOUT_N=8
export PPO_MINI_BATCH_SIZE=32
export TOTAL_TRAINING_STEPS=6
export TOTAL_EPOCHS=1
export TEST_FREQ=3
export SAVE_FREQ=6
export VAL_BATCH_SIZE=64
export MAX_PROMPT_LENGTH=2048
export MAX_RESPONSE_LENGTH=2048

launch_training
