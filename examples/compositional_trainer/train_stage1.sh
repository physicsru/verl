#!/bin/bash
# Stage 1 — atomic skill acquisition (operator bodies SHOWN), from base model.
#   POOL=paper  qsub examples/compositional_trainer/train_stage1.sh
#   RL_METHOD=reval POOL=lenpres qsub examples/compositional_trainer/train_stage1.sh
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=48:00:00
#PBS -W group_list=go39
#PBS -N comp-s1
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"

POOL=${POOL:-paper}
RL_METHOD=${RL_METHOD:-grpo}
export RL_METHOD
# Save HF weights so the Stage-1 checkpoint is directly loadable as Stage-2 model.path.
export SAVE_HF_MODEL=${SAVE_HF_MODEL:-1}
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-stage1_${POOL}_${RL_METHOD}_qwen3_4b}
export SAVE_DIR=${SAVE_DIR:-${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}}

_D="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage1_level1"
export TRAIN_FILE="${_D}/train.parquet"
export VAL_FILES="${_D}/test.parquet"

export M_PROMPTS=64
export ROLLOUT_N=8
export PPO_MINI_BATCH_SIZE=64
export TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-400}
export TOTAL_EPOCHS=1
export TEST_FREQ=10
export SAVE_FREQ=100
export MAX_PROMPT_LENGTH=2048
export MAX_RESPONSE_LENGTH=2048

launch_training
