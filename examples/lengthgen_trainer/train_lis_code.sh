#!/bin/bash
# Train lis / code on 8 Miyabi nodes.
#   qsub examples/lengthgen_trainer/train_lis_code.sh

#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=12:00:00
#PBS -W group_list=go39
#PBS -N lg-lis-code
#PBS -j oe

source "${PBS_O_WORKDIR}/examples/lengthgen_trainer/train_pbs_header.sh"

export TASK=lis
export CONDITION=code
export EXPERIMENT_NAME=lis_code_qwen3_4b
export TRAIN_FILE="${PBS_O_WORKDIR}/data/lengthgen/lis_code/train.parquet"
export TEST_FILE="${PBS_O_WORKDIR}/data/lengthgen/lis_code/test.parquet"
_D="${PBS_O_WORKDIR}/data/lengthgen/lis_code"
export VAL_FILES="${_D}/test.parquet,${_D}/eval_iid.parquet,${_D}/eval_easy_to_hard.parquet,${_D}/eval_hard_to_easy.parquet"

export M_PROMPTS=64
export ROLLOUT_N=8
export PPO_MINI_BATCH_SIZE=64
export TOTAL_TRAINING_STEPS=500
export TOTAL_EPOCHS=15
export TEST_FREQ=50
export SAVE_FREQ=100
export LENGTHGEN_NUM_EXAMINE=3

launch_training
