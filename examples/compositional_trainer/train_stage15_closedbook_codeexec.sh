#!/bin/bash
# Stage-1.5 CLOSED-BOOK CODE-EXEC SFT — install atomic recall for ALL 25 ops.
#
# Why: the first stage-2 code-exec run showed RL cannot install absent
# memories (GRPO groups where every rollout fails have zero advantage -> zero
# gradient; train ops saturated ~0.5 depth-1 after 500 steps, never-trained
# eval ops decayed from 0.46 to 0.36 via sibling interference). Atomic skill
# is stage-1's job; stage-2 measures compositional skill. This stage SFTs the
# stage-1 RFT-codeexec checkpoint on SYNTHESIZED closed-book targets: prompt =
# exact stage-2 hidden-body code-exec prompt (depth-1, one op), target = short
# recall plan + one ```python block with the verbatim reference body (renamed
# to func_N) + unchanged main_solution. Targets never state the output string,
# are correct by construction, and put func_N -> body in the LOSS.
#
#   # 1. build data (CPU, ~1 min — see build_closedbook_codeexec.py docstring)
#   # 2. submit:
#   qsub examples/compositional_trainer/train_stage15_closedbook_codeexec.sh
#   # 3. recall-probe the ckpt, then Stage 2 from it:
#   MODEL_PATH=<stage15 hf ckpt> qsub -v "..." examples/compositional_trainer/train_stage2_codeexec.sh
#
#PBS -q regular-g
#PBS -l select=4:mpiprocs=1
#PBS -l walltime=06:00:00
#PBS -W group_list=go39
#PBS -N comp-s15-cbcx
#PBS -j oe
#PBS -p 1023

# Init from the bodies-SHOWN RFT ckpt (keeps the one-shot codeexec behaviors
# RL already installed); must be set BEFORE the header applies its default.
export MODEL_PATH=${MODEL_PATH:-${PBS_O_WORKDIR}/checkpoints/compositional/stage1_paper_rftcx_iter1_qwen3_4b/global_step_1984/huggingface}

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"

POOL=${POOL:-paper}
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-stage15_${POOL}_closedbook_cx_qwen3_4b}
export SAVE_DIR=${SAVE_DIR:-${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}}

_D="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage15_closedbook_codeexec"
export TRAIN_FILE=${TRAIN_FILE:-${_D}/train.parquet}
export VAL_FILES=${VAL_FILES:-${_D}/test.parquet}

export TORCH_MASTER_PORT=${TORCH_MASTER_PORT:-29412}
export SFT_EPOCHS=${SFT_EPOCHS:-2}
export SFT_LR=${SFT_LR:-2e-5}
export SFT_MAX_LENGTH=${SFT_MAX_LENGTH:-2048}
export SFT_BATCH=${SFT_BATCH:-128}
export SFT_MICRO_BSZ=${SFT_MICRO_BSZ:-4}

launch_mpi examples/compositional_trainer/_sft_launch.sh
