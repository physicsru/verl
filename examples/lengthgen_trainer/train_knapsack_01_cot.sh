#!/bin/bash
# Train knapsack_01 / cot on 8 Miyabi nodes.
#   qsub examples/lengthgen_trainer/train_knapsack_01_cot.sh

#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=48:00:00
#PBS -W group_list=go39
#PBS -N lg-kna-cot
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/lengthgen_trainer/train_pbs_header.sh"

export TASK=knapsack_01
export CONDITION=cot
export EXPERIMENT_NAME=knapsack_01_cot_qwen3_4b
export TRAIN_FILE="${PBS_O_WORKDIR}/data/lengthgen/knapsack_01_cot/train.parquet"
export TEST_FILE="${PBS_O_WORKDIR}/data/lengthgen/knapsack_01_cot/test.parquet"
_D="${PBS_O_WORKDIR}/data/lengthgen/knapsack_01_cot"
export VAL_FILES="${_D}/eval_iid.parquet,${_D}/eval_easy_to_hard.parquet,${_D}/eval_hard_to_easy.parquet"

export M_PROMPTS=64
export ROLLOUT_N=8
export PPO_MINI_BATCH_SIZE=64
export TOTAL_TRAINING_STEPS=500
export TOTAL_EPOCHS=1
export TEST_FREQ=10
export SAVE_FREQ=100
export LENGTHGEN_NUM_EXAMINE=3

launch_training
