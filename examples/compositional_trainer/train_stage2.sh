#!/bin/bash
# Stage 2 — compositional skill learning (operator bodies HIDDEN), starting
# from a Stage-1 checkpoint. Trains on train-op compositions; validates on the
# disjoint held-out-op eval splits (the generalization measurement).
#
#   POOL=paper  MODEL_PATH=<stage1_ckpt> qsub examples/compositional_trainer/train_stage2.sh
#   RL_METHOD=reval POOL=lenpres MODEL_PATH=<stage1_ckpt> qsub examples/compositional_trainer/train_stage2.sh
#
# Data-level replay (anti-forgetting): set TRAIN_FILE to a comma-separated list
# that also includes the Stage-1 / S parquet, e.g.
#   TRAIN_FILE="${D2}/train.parquet,${D1}/train.parquet"
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=48:00:00
#PBS -W group_list=go39
#PBS -N comp-s2
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"

POOL=${POOL:-paper}
RL_METHOD=${RL_METHOD:-grpo}
export RL_METHOD
export SAVE_HF_MODEL=${SAVE_HF_MODEL:-1}
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-stage2_${POOL}_${RL_METHOD}_qwen3_4b}
export SAVE_DIR=${SAVE_DIR:-${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}}

# MODEL_PATH should point at the Stage-1 checkpoint (defaults to base if unset).
export MODEL_PATH=${MODEL_PATH:-Qwen/Qwen3-4B-Base}

_BASE="${PBS_O_WORKDIR}/data/compositional/${POOL}"
export TRAIN_FILE="${TRAIN_FILE:-${_BASE}/stage2_level1to2/train.parquet}"

if [[ "${POOL}" == "lenpres" ]]; then
    # Depth-tiered held-out eval: IID (train ops) + easy/medium/hard (held-out ops).
    export VAL_FILES="${_BASE}/eval_iid/test.parquet,${_BASE}/eval_easy/test.parquet,${_BASE}/eval_medium/test.parquet,${_BASE}/eval_hard/test.parquet"
    export MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-4096}
else
    # Paper baseline: held-out compositional eval, levels 1-8.
    export VAL_FILES="${_BASE}/stage2_level1to8/test.parquet"
    export MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-4096}
fi

export M_PROMPTS=64
export ROLLOUT_N=8
export PPO_MINI_BATCH_SIZE=64
# Note: verl stops at whichever comes first — total_training_steps OR
# total_epochs exhausted. Stage-2 data is 50k rows / bsz 64 = 781 steps/epoch,
# so a long step budget needs TOTAL_EPOCHS raised (e.g. 5000 steps -> >=7).
export TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-500}
export TOTAL_EPOCHS=${TOTAL_EPOCHS:-1}
export TEST_FREQ=${TEST_FREQ:-10}
export SAVE_FREQ=${SAVE_FREQ:-100}
export MAX_PROMPT_LENGTH=2048

launch_training
