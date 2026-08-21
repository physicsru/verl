#!/bin/bash
# Stage-1.5b CLOSED-BOOK CODE-EXEC SFT — atomic recall (all 25 ops, depth 1)
# PLUS multi-helper robustness (depth-2..4 TRAIN-op compositions), with the
# EOS-terminated chat template (train_pbs_header.sh).
#
# Why (v2 autopsy): atoms were perfect in isolation after stage-1.5, but
# per-mention recall corrupted to ~0.85-0.9 with several helpers in one
# program (61% of failures = wrong signature / lost helper / hallucinated
# method / chimera body), compounding multiplicatively with depth. And the
# no-EOS SFT template left a degenerate never-stop tail RL could not fix.
# This run replaces stage-1.5: same init (stage-1 RFT ckpt), superset data
# (20k depth-1 rows + 12k depth-2..4 multi-helper rows), EOS in every target.
# Eval-op COMPOSITIONS stay held out — eval ops appear only alone at depth 1.
#
#   # 1. build data (CPU): bash examples/compositional_trainer/build_v3_data.sh
#   # 2. submit:          qsub examples/compositional_trainer/train_stage15b_closedbook_codeexec.sh
#   # 3. gate:            qsub examples/compositional_trainer/probe_stage15b.sh
#   # 4. stage-2 v3 from the probed ckpt (see PROGRESS.md).
#
#PBS -q regular-g
#PBS -l select=4:mpiprocs=1
#PBS -l walltime=06:00:00
#PBS -W group_list=go39
#PBS -N comp-s15b-cbcx
#PBS -j oe
#PBS -p 1023

# Init from the bodies-SHOWN RFT ckpt (keeps the one-shot codeexec behaviors
# RL already installed); must be set BEFORE the header applies its default.
export MODEL_PATH=${MODEL_PATH:-${PBS_O_WORKDIR}/checkpoints/compositional/stage1_paper_rftcx_iter1_qwen3_4b/global_step_1984/huggingface}

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"

POOL=${POOL:-paper}
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-stage15b_${POOL}_closedbook_cx_qwen3_4b}
export SAVE_DIR=${SAVE_DIR:-${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}}

_D="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage15b_closedbook_codeexec"
export TRAIN_FILE=${TRAIN_FILE:-${_D}/train.parquet}
export VAL_FILES=${VAL_FILES:-${_D}/test.parquet}

export TORCH_MASTER_PORT=${TORCH_MASTER_PORT:-29413}
export SFT_EPOCHS=${SFT_EPOCHS:-2}
export SFT_LR=${SFT_LR:-2e-5}
# Depth-4 rows can hold many helper bodies (binary ops branch): 2048 truncates
# the tail of long targets — and the EOS with it — so give more headroom.
export SFT_MAX_LENGTH=${SFT_MAX_LENGTH:-3072}
export SFT_BATCH=${SFT_BATCH:-128}
export SFT_MICRO_BSZ=${SFT_MICRO_BSZ:-4}

launch_mpi examples/compositional_trainer/_sft_launch.sh
