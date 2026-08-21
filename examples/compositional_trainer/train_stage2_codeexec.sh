#!/bin/bash
# Stage 2 — compositional RL under the ONE-SHOT CODE-EXEC condition (operator
# bodies HIDDEN), starting from a code-exec Stage-1 checkpoint. The model plans
# in text, then commits to ONE self-contained Python program re-implementing
# every hidden func_N; the reward executes that program exactly once and takes
# main_solution(x)'s return value as the answer (reward_fn_codeexec.py).
#
# Because execution replaces mental tracing, held-out-op accuracy measures
# "recall the atomic implementation + compose it explicitly" — the RL question
# is whether training on train-op compositions improves that on held-out ops.
#
#   POOL=paper  MODEL_PATH=<stage1_codeexec_ckpt> qsub examples/compositional_trainer/train_stage2_codeexec.sh
#   RL_METHOD=reval POOL=lenpres MODEL_PATH=<...>  qsub examples/compositional_trainer/train_stage2_codeexec.sh
#
# Requires the codeexec data first:
#   python examples/compositional_trainer/build_codeexec_data.py --pool ${POOL}
#
# Data-level replay (anti-forgetting): set TRAIN_FILE to a comma-separated list
# that also includes the Stage-1 codeexec parquet.
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=48:00:00
#PBS -W group_list=gj26
#PBS -N comp-s2-cx
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"
export REWARD_FN="${PBS_O_WORKDIR}/examples/compositional_trainer/reward_fn_codeexec.py"

POOL=${POOL:-paper}
RL_METHOD=${RL_METHOD:-grpo}
export RL_METHOD
export SAVE_HF_MODEL=${SAVE_HF_MODEL:-1}
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-stage2_${POOL}_${RL_METHOD}_cx_qwen3_4b}
export SAVE_DIR=${SAVE_DIR:-${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}}

# MODEL_PATH should point at the code-exec Stage-1 checkpoint (defaults to base if unset).
export MODEL_PATH=${MODEL_PATH:-Qwen/Qwen3-4B-Base}

_BASE="${PBS_O_WORKDIR}/data/compositional/${POOL}"
export TRAIN_FILE="${TRAIN_FILE:-${_BASE}/stage2_level1to2_codeexec/train.parquet}"

if [[ "${POOL}" == "lenpres" ]]; then
    # Depth-tiered held-out eval: IID (train ops) + easy/medium/hard (held-out ops).
    export VAL_FILES="${_BASE}/eval_iid_codeexec/test.parquet,${_BASE}/eval_easy_codeexec/test.parquet,${_BASE}/eval_medium_codeexec/test.parquet,${_BASE}/eval_hard_codeexec/test.parquet"
    export MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-4096}
else
    # Paper baseline: held-out compositional eval, levels 1-8.
    export VAL_FILES="${_BASE}/stage2_level1to8_codeexec/test.parquet"
    export MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-4096}
fi

export M_PROMPTS=64
export ROLLOUT_N=8
export PPO_MINI_BATCH_SIZE=64
# verl stops at total_training_steps OR total_epochs, whichever first (see
# train_stage2.sh for the arithmetic).
export TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-5000}
export TOTAL_EPOCHS=${TOTAL_EPOCHS:-1}
export TEST_FREQ=${TEST_FREQ:-10}
export SAVE_FREQ=${SAVE_FREQ:-1000}
export MAX_PROMPT_LENGTH=2048

launch_training
