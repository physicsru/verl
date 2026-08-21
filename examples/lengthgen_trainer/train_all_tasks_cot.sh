#!/bin/bash
# Train ALL 3 DP tasks (combined) / CoT condition on 8 Miyabi nodes.
#   qsub examples/lengthgen_trainer/train_all_tasks_cot.sh

#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=48:00:00
#PBS -W group_list=go39
#PBS -N lg-all-cot
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/lengthgen_trainer/train_pbs_header.sh"

export TASK=all_tasks
export CONDITION=cot
export EXPERIMENT_NAME=all_tasks_cot_qwen3_4b
export TRAIN_FILE="${PBS_O_WORKDIR}/data/lengthgen/all_tasks_cot/train.parquet"
export TEST_FILE="${PBS_O_WORKDIR}/data/lengthgen/all_tasks_cot/test.parquet"
_D="${PBS_O_WORKDIR}/data/lengthgen/all_tasks_cot"
export VAL_FILES="${_D}/eval_iid.parquet,${_D}/eval_easy_to_hard.parquet,${_D}/eval_hard_to_easy.parquet"

export M_PROMPTS=64
export ROLLOUT_N=8
export PPO_MINI_BATCH_SIZE=64
export TOTAL_TRAINING_STEPS=1500
export TOTAL_EPOCHS=1
export TEST_FREQ=10
export SAVE_FREQ=200
export LENGTHGEN_NUM_EXAMINE=3
export VAL_BATCH_SIZE=1500

launch_training
