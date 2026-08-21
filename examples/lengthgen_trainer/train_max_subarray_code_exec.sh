#!/bin/bash
# Train max_subarray / code_exec (code-execution ablation) on 8 Miyabi nodes.
#   qsub examples/lengthgen_trainer/train_max_subarray_code_exec.sh
#
# Same prompt as the "code" condition; the answer is taken from EXECUTING the
# model's function (reward_fn_codeexec.py) instead of its \boxed{} value.

#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=48:00:00
#PBS -W group_list=go39
#PBS -N lg-max-codex
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/lengthgen_trainer/train_pbs_header.sh"

export TASK=max_subarray
export CONDITION=code_exec
export EXPERIMENT_NAME=max_subarray_code_exec_qwen3_4b
export TRAIN_FILE="${PBS_O_WORKDIR}/data/lengthgen/max_subarray_code_exec/train.parquet"
export TEST_FILE="${PBS_O_WORKDIR}/data/lengthgen/max_subarray_code_exec/test.parquet"
_D="${PBS_O_WORKDIR}/data/lengthgen/max_subarray_code_exec"
export VAL_FILES="${_D}/eval_iid.parquet,${_D}/eval_easy_to_hard.parquet,${_D}/eval_hard_to_easy.parquet"

# Code-execution ablation uses its own reward function.
export REWARD_FN="${PBS_O_WORKDIR}/examples/lengthgen_trainer/reward_fn_codeexec.py"

export M_PROMPTS=64
export ROLLOUT_N=8
export PPO_MINI_BATCH_SIZE=64
export TOTAL_TRAINING_STEPS=500
export TOTAL_EPOCHS=1
export TEST_FREQ=10
export SAVE_FREQ=100
export LENGTHGEN_NUM_EXAMINE=3

launch_training
