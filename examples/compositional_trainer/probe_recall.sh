#!/bin/bash
# RECALL PROBE — per-op depth-1 hidden-body accuracy, greedy@1, all 25 ops.
# The gate between stage-1.5 closedbook SFT and the stage-2 relaunch: every op
# should recall >= 0.9 before spending 8-node RL time. Probes TWO checkpoints
# (stage-1.5 vs its stage-1 RFT init) on the same 25x64 unseen probe set, so
# the delta per op is attributable to the closedbook SFT.
#
#   qsub examples/compositional_trainer/probe_recall.sh
#   # overrides: qsub -v "PROBE_MODEL=<hf dir>,BASE_MODEL=<hf dir>" ...
#
#PBS -q regular-g
#PBS -l select=1:mpiprocs=1
#PBS -l walltime=02:00:00
#PBS -W group_list=go39
#PBS -N comp-probe
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"

CKPT_ROOT="${PBS_O_WORKDIR}/checkpoints/compositional"
PROBE_MODEL=${PROBE_MODEL:-${CKPT_ROOT}/stage15_paper_closedbook_cx_qwen3_4b/global_step_312/huggingface}
BASE_MODEL=${BASE_MODEL:-${CKPT_ROOT}/stage1_paper_rftcx_iter1_qwen3_4b/global_step_1984/huggingface}
OUT_ROOT=${OUT_ROOT:-${CKPT_ROOT}/probe_recall_d1}

export STAGE1_FILE="${PBS_O_WORKDIR}/data/compositional/paper/probe_recall_d1/probe.parquet"
export N_SAMPLES=1
export ROLLOUT_TEMP=0.0
export ROLLOUT_MAX_TOKENS=2048
export ROLLOUT_MAX_MODEL_LEN=4096
export MAX_PROBLEMS=-1

export CUR_MODEL="${PROBE_MODEL}"
export ROLLOUT_DIR="${OUT_ROOT}/stage15"
launch_mpi examples/compositional_trainer/_rollout_launch.sh

export CUR_MODEL="${BASE_MODEL}"
export ROLLOUT_DIR="${OUT_ROOT}/stage1_baseline"
launch_mpi examples/compositional_trainer/_rollout_launch.sh

source /work/go39/b20033/code/generalization_venv/bin/activate
cd "${PBS_O_WORKDIR}"
python examples/compositional_trainer/score_probe.py \
    --in "stage15=${OUT_ROOT}/stage15" "stage1_baseline=${OUT_ROOT}/stage1_baseline" \
    --out analysis/probe_recall_stage15.md
