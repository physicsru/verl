#!/bin/bash
# Stage-1 SFT (standalone, multi-node FSDP). Supervise the base model on a
# messages-format parquet — e.g. the synthetic-trace data from build_sft_data.py.
# This is the plain-SFT path; the faithful iterative RFT is run_stage1_rft.sh
# (which reuses the same SFT primitive, _sft_launch.sh).
#
#   # 1. build synthetic SFT data
#   python examples/compositional_trainer/build_sft_data.py --pool paper \
#       --in_dir data/compositional/paper/stage1_level1 \
#       --out_dir data/compositional/paper/stage1_sft
#   # 2. submit
#   POOL=paper qsub examples/compositional_trainer/train_stage1_sft.sh
#
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=48:00:00
#PBS -W group_list=go39
#PBS -N comp-s1-sft
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"

POOL=${POOL:-paper}
export EXPERIMENT_NAME=${EXPERIMENT_NAME:-stage1_${POOL}_sft_qwen3_4b}
export SAVE_DIR=${SAVE_DIR:-${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}}

_D="${PBS_O_WORKDIR}/data/compositional/${POOL}/stage1_sft"
export TRAIN_FILE=${TRAIN_FILE:-${_D}/train.parquet}
export VAL_FILES=${VAL_FILES:-${_D}/test.parquet}

# MODEL_PATH defaults to the base model (set in train_pbs_header.sh).
export TORCH_MASTER_PORT=${TORCH_MASTER_PORT:-29411}
export SFT_EPOCHS=${SFT_EPOCHS:-2}
export SFT_LR=${SFT_LR:-2e-5}
export SFT_MAX_LENGTH=${SFT_MAX_LENGTH:-2048}
export SFT_BATCH=${SFT_BATCH:-128}
export SFT_MICRO_BSZ=${SFT_MICRO_BSZ:-4}

launch_mpi examples/compositional_trainer/_sft_launch.sh
