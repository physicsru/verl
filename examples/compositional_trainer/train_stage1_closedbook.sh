#!/bin/bash
# Stage-1 CLOSED-BOOK SFT — the fix for the held-out atomic-recall hole.
#
# Our RFT/SFT only computes loss on the assistant turn, so with the operator
# bodies sitting in the (masked) prompt the model got ZERO gradient on the
# `def func_N` definitions and never memorised func_N -> behaviour (held-out
# Level-1 recall stuck ~0.34 vs the paper's ~0.9). build_sft_data.py
# --hide_body_frac 1.0 moves the definition into the assistant turn: the prompt
# is body-HIDDEN (Stage-2 format) and the target RECALLS the def, then computes.
# That puts func_N -> body in the LOSS, closed-book, so recall forms in weights.
#
# This is plain SFT (reuses the _sft_launch.sh primitive); kept as its own script
# so RL / RFT / SFT / closed-book stay separately debuggable.
#
#   # 1. build closed-book data (CPU, ~seconds):
#   python examples/compositional_trainer/build_sft_data.py --pool paper \
#       --in_dir  data/compositional/paper/stage1_level1 \
#       --out_dir data/compositional/paper/stage1_closedbook --hide_body_frac 1.0
#   # 2. submit:
#   qsub -v "POOL=paper" examples/compositional_trainer/train_stage1_closedbook.sh
#   # 3. then Stage 2 from the resulting ckpt:
#   MODEL_PATH=<closedbook hf ckpt> qsub -v "..." examples/compositional_trainer/train_stage2.sh
#
#PBS -q regular-g
#PBS -l select=4:mpiprocs=1
#PBS -l walltime=12:00:00
#PBS -W group_list=go39
#PBS -N comp-s1-cb
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"

POOL=${POOL:-paper}
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-stage1_${POOL}_closedbook_qwen3_4b}
export SAVE_DIR=${SAVE_DIR:-${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}}

_D="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage1_closedbook"
export TRAIN_FILE=${TRAIN_FILE:-${_D}/train.parquet}
export VAL_FILES=${VAL_FILES:-${_D}/test.parquet}

# MODEL_PATH defaults to the base model (set in train_pbs_header.sh) — a clean
# closed-book Stage-1, so any held-out recall is attributable to this stage.
export TORCH_MASTER_PORT=${TORCH_MASTER_PORT:-29411}
export SFT_EPOCHS=${SFT_EPOCHS:-2}
export SFT_LR=${SFT_LR:-2e-5}
export SFT_MAX_LENGTH=${SFT_MAX_LENGTH:-2048}
export SFT_BATCH=${SFT_BATCH:-128}
export SFT_MICRO_BSZ=${SFT_MICRO_BSZ:-4}

launch_mpi examples/compositional_trainer/_sft_launch.sh
