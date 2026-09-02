#!/bin/bash
# RA bootstrap-SFT VARIANT driver: one SFT per variant from the same init, then
# greedy d1-8 sweep(s) + CI report. Originally the composition-depth ABLATION
# (WALKTHROUGH §15); now also the RA-v2 stitcher campaign
# (doc/COMPOSITIONAL_HISTORY.md §10) — same pattern, more knobs.
#
# A variant = a stitched data dir data/compositional/<pool>/ra_rft/sft_bootstrap_<VAR>
# built by build_ra_sft_data.py (the driver builds nothing, only trains + sweeps):
#   d1   atomics only (zero composition practice)
#   d12  + depth-2 comps            (12.5k, all that exist)
#   d13  + depth-2..3 comps         (16k)
#   d14  + depth-2..4 comps         (16k) — `sft_bootstrap` (no suffix); with
#        SFT_SEED=1 this is the EXISTING best ckpt (job 2490799) and is only swept
#   v1   alias of d14's data for extra SFT seeds of the v1 format
#   v2   RA-v2 format (--format v2), d2-4 comps + atomics + funcless rows
#   v2_sc  v2 + --self-check lines
#
# Knobs (PBS -v; '+'-separated lists — PBS -v treats commas as separators):
#   ABL_VARIANTS   d1+d12+d13+d14 (default) | v2+v2_sc | ...
#   SFT_SEED       trainer.seed (default 1). Seeds != 1 get a `_s<seed>` tag on
#                  the experiment name / sweep dir / CI report (§10.2 C1: 3 seeds).
#   ROLLOUT_MAX_TOKENS  sweep budget (default 3072 = the fair budget, §10.2 B3;
#                  the §15/§16 sweeps used 1536). Sweep dirs carry `_b<budget>`.
#   ABL_TEST_SETS  heldout (default) | heldout+trainops — sweep both test sets
#                  (§10.5 step 4); train-op sweeps land in trainops_sweep_<...>.
#
#   qsub -N ra-v2-s1  -v ABL_VARIANTS=v2+v2_sc,SFT_SEED=1   examples/compositional_trainer/run_ra_depth_ablation.sh
#   qsub -N ra-v1-s7  -v ABL_VARIANTS=v1,SFT_SEED=7,ABL_TEST_SETS=heldout+trainops ...
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
export SFT_SEED=${SFT_SEED:-1}
SEED_TAG=""; [ "${SFT_SEED}" != "1" ] && SEED_TAG="_s${SFT_SEED}"

_BASE="${PBS_O_WORKDIR}/data/compositional/${POOL}"
RA_ROOT="${_BASE}/ra_rft"
HELDOUT_FILE="${_BASE}/stage2_level1to8_codeexec/test.parquet"
TRAINOPS_FILE="${_BASE}/stage2_level1to8_trainops_codeexec/test.parquet"
# NB: RA_INIT, not MODEL_PATH — the header pre-exports MODEL_PATH (see §14).
INIT=${RA_INIT:-${PBS_O_WORKDIR}/checkpoints/compositional/stage15b_paper_closedbook_cx_qwen3_4b/global_step_500/huggingface}

resolve_hf_ckpt() { find "$1" -type d -name huggingface 2>/dev/null | sort | tail -1; }

# rollout knobs for the greedy sweeps
export N_SAMPLES=1
export ROLLOUT_TEMP=0.0
export ROLLOUT_TOP_P=1.0
export ROLLOUT_MAX_TOKENS=${ROLLOUT_MAX_TOKENS:-3072}
export ROLLOUT_MAX_MODEL_LEN=${ROLLOUT_MAX_MODEL_LEN:-4096}
export MAX_PROBLEMS=-1
BUDGET_TAG="_b${ROLLOUT_MAX_TOKENS}"

VARIANTS=$(echo "${ABL_VARIANTS:-d1+d12+d13+d14}" | tr '+,' '  ')
TEST_SETS=$(echo "${ABL_TEST_SETS:-heldout}" | tr '+,' '  ')
# CI md name carries the pool when it is not the default one: two pools running the
# same ABL_VARIANTS used to overwrite each other's analysis/ci_ra_abl_<tag>.md
# (RESULTS_PROVENANCE issue #1). Sweep dirs/ckpts were never affected (per-pool paths).
POOL_TAG=""; [ "${POOL}" != "paper" ] && POOL_TAG="${POOL}_"
CI_TAG="${POOL_TAG}$(echo "${VARIANTS}" | tr ' ' '_')${SEED_TAG}${BUDGET_TAG}"

declare -A CI_ARGS   # test set -> "label=dir ..." list
N_ROLLOUTS=0
for VAR in ${VARIANTS}; do
    echo "==================== RA variant ${VAR} seed=${SFT_SEED} ===================="
    case "${VAR}" in
        d14|v1) DATA_DIR="${RA_ROOT}/sft_bootstrap" ;;
        *)      DATA_DIR="${RA_ROOT}/sft_bootstrap_${VAR}" ;;
    esac
    if [ "${VAR}" = "d14" ] && [ "${SFT_SEED}" = "1" ]; then
        CKPT="$(resolve_hf_ckpt "${PBS_O_WORKDIR}/checkpoints/compositional/ra_sft_bootstrap_paper_qwen3_4b")"
    else
        if [ ! -f "${DATA_DIR}/train.parquet" ]; then
            echo "[ra-abl][ERROR] no stitched data at ${DATA_DIR} (build_ra_sft_data.py first)"; exit 1
        fi
        export EXPERIMENT_NAME="ra_sft_bootstrap_${POOL}_${VAR}${SEED_TAG}_qwen3_4b"
        export SAVE_DIR="${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}"
        export TRAIN_FILE="${DATA_DIR}/train.parquet"
        export VAL_FILES="${DATA_DIR}/test.parquet"
        export MODEL_PATH="${INIT}"
        launch_mpi ${CT}/_sft_launch.sh
        CKPT="$(resolve_hf_ckpt "${SAVE_DIR}")"
    fi
    if [ -z "${CKPT}" ]; then
        echo "[ra-abl][ERROR] no checkpoint for ${VAR}; aborting."; exit 1
    fi
    echo "[ra-abl] ${VAR} ckpt = ${CKPT}"
    export CUR_MODEL="${CKPT}"
    for TS in ${TEST_SETS}; do
        case "${TS}" in
            heldout)  export STAGE1_FILE="${HELDOUT_FILE}"
                      export ROLLOUT_DIR="${RA_ROOT}/ablation_sweep_${VAR}${SEED_TAG}${BUDGET_TAG}" ;;
            trainops) export STAGE1_FILE="${TRAINOPS_FILE}"
                      export ROLLOUT_DIR="${RA_ROOT}/trainops_sweep_${VAR}${SEED_TAG}${BUDGET_TAG}" ;;
            *) echo "[ra-abl][ERROR] unknown test set ${TS}"; exit 1 ;;
        esac
        N_ROLLOUTS=$((N_ROLLOUTS + 1))
        export RFT_ITER=9${N_ROLLOUTS}   # distinct rollout seed per sweep
        launch_mpi ${CT}/_rollout_launch.sh
        CI_ARGS[${TS}]+="${VAR}${SEED_TAG}=${ROLLOUT_DIR} "
    done
done

for TS in ${TEST_SETS}; do
    SUFFIX=""; [ "${TS}" = "trainops" ] && SUFFIX="_trainops"
    # shellcheck disable=SC2086
    python3 ${CT}/compositionality_index.py \
        --sweep ${CI_ARGS[${TS}]} \
        --out "${PBS_O_WORKDIR}/analysis/ci_ra_abl_${CI_TAG}${SUFFIX}.md"
    echo "CI report (${TS}): analysis/ci_ra_abl_${CI_TAG}${SUFFIX}.md"
done
echo "==================== RA variants (${CI_TAG}) finished ===================="
