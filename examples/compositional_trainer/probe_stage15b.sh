#!/bin/bash
# STAGE-1.5b GATE — two greedy@1 measurements of the stage-1.5b ckpt BEFORE
# spending 8-node RL time, so v3's RL contribution is attributable:
#   (a) per-op depth-1 recall probe (25 ops x 64), vs the old stage-1.5 ckpt
#       -> did the multi-helper data or EOS fix hurt atomic recall?
#   (b) held-out-op depth-1..8 sweep on the stage-2 val set
#       -> the pre-RL compositional baseline; v3's step-0 val must match it,
#          and (v3 curve - this table) = what RL adds. Response length per
#          depth also verifies the EOS fix (pre-fix: always ~max_tokens).
#
#   qsub examples/compositional_trainer/probe_stage15b.sh
#   # overrides: qsub -v "PROBE_MODEL=<hf dir>" ...
#
#PBS -q regular-g
#PBS -l select=1:mpiprocs=1
#PBS -l walltime=03:00:00
#PBS -W group_list=go39
#PBS -N comp-probe-15b
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"

CKPT_ROOT="${PBS_O_WORKDIR}/checkpoints/compositional"
# Default: latest global_step under the stage-1.5b save dir.
if [ -z "${PROBE_MODEL:-}" ]; then
    PROBE_MODEL=$(ls -d "${CKPT_ROOT}/stage15b_paper_closedbook_cx_qwen3_4b/global_step_"*/huggingface | sort -t_ -k3 -n | tail -1)
fi
OLD_MODEL=${OLD_MODEL:-${CKPT_ROOT}/stage15_paper_closedbook_cx_qwen3_4b/global_step_312/huggingface}
OUT_ROOT=${OUT_ROOT:-${CKPT_ROOT}/probe_stage15b}
echo "[probe] PROBE_MODEL=${PROBE_MODEL}"

# --- (a) per-op depth-1 recall probe (same 25x64 set as the stage-1.5 gate) ---
export N_SAMPLES=1
export ROLLOUT_TEMP=0.0
export ROLLOUT_MAX_TOKENS=2048
export ROLLOUT_MAX_MODEL_LEN=4096
export MAX_PROBLEMS=-1

export STAGE1_FILE="${PBS_O_WORKDIR}/data/compositional/paper/probe_recall_d1/probe.parquet"
export CUR_MODEL="${PROBE_MODEL}"
export ROLLOUT_DIR="${OUT_ROOT}/recall_stage15b"
launch_mpi examples/compositional_trainer/_rollout_launch.sh

# --- (b) held-out-op depth-1..8 sweep (the stage-2 val set, pre-RL) ---------
export STAGE1_FILE="${PBS_O_WORKDIR}/data/compositional/paper/stage2_level1to8_codeexec/test.parquet"
export ROLLOUT_MAX_TOKENS=4096
export ROLLOUT_MAX_MODEL_LEN=8192
export ROLLOUT_DIR="${OUT_ROOT}/depth_sweep_stage15b"
launch_mpi examples/compositional_trainer/_rollout_launch.sh

source /work/go39/b20033/code/generalization_venv/bin/activate
cd "${PBS_O_WORKDIR}"
python examples/compositional_trainer/score_probe.py \
    --in "stage15b=${OUT_ROOT}/recall_stage15b" \
    --out analysis/probe_recall_stage15b.md
python examples/compositional_trainer/score_depth_sweep.py \
    --in "stage15b=${OUT_ROOT}/depth_sweep_stage15b" \
    --out analysis/depth_sweep_stage15b.md
