#!/bin/bash
# RA composition-depth ABLATION (WALKTHROUGH §15): how much composition-depth
# exposure does the RA format need before it extrapolates?
#
# Four bootstrap-only variants, single variable = the depth range of the
# stitched COMP data (atomics d1 all-25-ops always included; NO RFT round, so
# the comparison is one SFT each from the same init):
#   d1   atomics only (zero composition practice)
#   d12  + depth-2 comps            (12.5k, all that exist)
#   d13  + depth-2..3 comps         (16k)
#   d14  + depth-2..4 comps         (16k) — EXISTING ckpt from job 2490799's
#        bootstrap phase (ra_sft_bootstrap_paper_qwen3_4b); only swept here.
#
# Each variant: SFT from stage15b/500 -> greedy held-out d1-8 sweep. Final CI
# report with all four sweeps -> analysis/ci_ra_depth_ablation.md.
#
# Data first (CPU): build_ra_sft_data.py --max_comp_depth {2,3} / --n_comp 0
# (already built: ra_rft/sft_bootstrap_{d1,d12,d13}).
#
#   qsub examples/compositional_trainer/run_ra_depth_ablation.sh
#
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=24:00:00
#PBS -W group_list=go39
#PBS -N comp-ra-abl
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"
set -e
CT=examples/compositional_trainer
export REWARD_FN="${PBS_O_WORKDIR}/${CT}/reward_fn_codeexec.py"

POOL=${POOL:-paper}
export TORCH_MASTER_PORT=${TORCH_MASTER_PORT:-29413}
export SFT_EPOCHS=${SFT_EPOCHS:-2}
export SFT_LR=${SFT_LR:-2e-5}
export SFT_MAX_LENGTH=${SFT_MAX_LENGTH:-3072}
export SFT_BATCH=${SFT_BATCH:-128}
export SFT_MICRO_BSZ=${SFT_MICRO_BSZ:-4}

_BASE="${PBS_O_WORKDIR}/data/compositional/${POOL}"
RA_ROOT="${_BASE}/ra_rft"
TEST_FILE="${_BASE}/stage2_level1to8_codeexec/test.parquet"
# NB: RA_INIT, not MODEL_PATH — the header pre-exports MODEL_PATH (see §14).
INIT=${RA_INIT:-${PBS_O_WORKDIR}/checkpoints/compositional/stage15b_paper_closedbook_cx_qwen3_4b/global_step_500/huggingface}

resolve_hf_ckpt() { find "$1" -type d -name huggingface 2>/dev/null | sort | tail -1; }

# rollout knobs for the greedy sweeps
export N_SAMPLES=1
export ROLLOUT_TEMP=0.0
export ROLLOUT_TOP_P=1.0
export ROLLOUT_MAX_TOKENS=1536
export ROLLOUT_MAX_MODEL_LEN=4096
export MAX_PROBLEMS=-1
export STAGE1_FILE="${TEST_FILE}"

# '+'-separated variant list -> lets the sweep be split into parallel jobs
# (PBS -v treats commas as its own separator, hence '+'):
#   qsub -v ABL_VARIANTS=d1+d14 ...   (d14 = sweep-only, cheap)
#   qsub -v ABL_VARIANTS=d12    ...
#   qsub -v ABL_VARIANTS=d13    ...
VARIANTS=$(echo "${ABL_VARIANTS:-d1+d12+d13+d14}" | tr '+,' '  ')
CI_TAG=$(echo "${VARIANTS}" | tr ' ' '_')

CI_ARGS=()
for VAR in ${VARIANTS}; do
    echo "==================== RA depth-ablation variant ${VAR} ===================="
    if [ "${VAR}" = "d14" ]; then
        CKPT="$(resolve_hf_ckpt "${PBS_O_WORKDIR}/checkpoints/compositional/ra_sft_bootstrap_paper_qwen3_4b")"
    else
        export EXPERIMENT_NAME="ra_sft_bootstrap_${POOL}_${VAR}_qwen3_4b"
        export SAVE_DIR="${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}"
        export TRAIN_FILE="${RA_ROOT}/sft_bootstrap_${VAR}/train.parquet"
        export VAL_FILES="${RA_ROOT}/sft_bootstrap_${VAR}/test.parquet"
        export MODEL_PATH="${INIT}"
        launch_mpi ${CT}/_sft_launch.sh
        CKPT="$(resolve_hf_ckpt "${SAVE_DIR}")"
    fi
    if [ -z "${CKPT}" ]; then
        echo "[ra-abl][ERROR] no checkpoint for ${VAR}; aborting."; exit 1
    fi
    echo "[ra-abl] ${VAR} ckpt = ${CKPT}"
    export CUR_MODEL="${CKPT}"
    export RFT_ITER=9${#CI_ARGS[@]}   # distinct rollout seed per variant
    export ROLLOUT_DIR="${RA_ROOT}/ablation_sweep_${VAR}"
    launch_mpi ${CT}/_rollout_launch.sh
    CI_ARGS+=("${VAR}=${ROLLOUT_DIR}")
done

python3 ${CT}/compositionality_index.py \
    --sweep "${CI_ARGS[@]}" \
    --out "${PBS_O_WORKDIR}/analysis/ci_ra_abl_${CI_TAG}.md"

echo "==================== RA depth ablation (${CI_TAG}) finished ===================="
echo "CI report: analysis/ci_ra_abl_${CI_TAG}.md"
