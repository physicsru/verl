#!/usr/bin/env bash
# One-shot launcher for the compositional-generalization baseline:
#   1. build the parquet data for POOL (skipped if it already exists)
#   2. qsub Stage 1 (atomic skills, bodies shown), saving HF weights
#   3. qsub Stage 2 (compositions, bodies hidden) with a PBS afterok dependency
#      on Stage 1, loading the Stage-1 checkpoint as the base model.
#
# Usage (run from the repo root, on a login node):
#   bash examples/compositional_trainer/run_baseline.sh
#   POOL=lenpres RL_METHOD=reval bash examples/compositional_trainer/run_baseline.sh
#   DRY_RUN=1 bash examples/compositional_trainer/run_baseline.sh   # print, don't submit
#
# Env knobs (all optional):
#   POOL={paper|lenpres}   RL_METHOD={grpo|reval}
#   STAGE1_STEPS  STAGE2_STEPS  (must be multiples of SAVE_FREQ=100 so the final
#                                checkpoint is written)
set -euo pipefail

POOL=${POOL:-paper}
RL_METHOD=${RL_METHOD:-grpo}
STAGE1_STEPS=${STAGE1_STEPS:-400}
STAGE2_STEPS=${STAGE2_STEPS:-500}
DRY_RUN=${DRY_RUN:-0}

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
cd "${REPO}"

DATA_DIR="${REPO}/data/compositional/${POOL}"
S1_EXP="stage1_${POOL}_${RL_METHOD}_qwen3_4b"
S2_EXP="stage2_${POOL}_${RL_METHOD}_qwen3_4b"
S1_SAVE="${REPO}/checkpoints/compositional/${S1_EXP}"
S2_SAVE="${REPO}/checkpoints/compositional/${S2_EXP}"
# Stage-1 final checkpoint, HF format (SAVE_HF_MODEL=1 writes this).
S1_CKPT="${S1_SAVE}/global_step_${STAGE1_STEPS}/actor/huggingface"

echo "=========================================================="
echo " Compositional baseline:  pool=${POOL}  method=${RL_METHOD}"
echo "   stage1 -> ${S1_SAVE}  (${STAGE1_STEPS} steps)"
echo "   stage2 -> ${S2_SAVE}  (${STAGE2_STEPS} steps, from stage1 ckpt)"
echo "=========================================================="

# ---- 1. data ----
if [[ -f "${DATA_DIR}/stage2_level1to2/train.parquet" ]]; then
    echo "[data] found ${DATA_DIR} — skipping build"
else
    echo "[data] building ${POOL} ..."
    [[ "${DRY_RUN}" == "1" ]] && echo "DRY: bash ${HERE}/build_baseline_data.sh ${POOL}" \
        || bash "${HERE}/build_baseline_data.sh" "${POOL}"
fi

run() { echo "+ $*"; [[ "${DRY_RUN}" == "1" ]] && echo "DRY (not submitted)" || "$@"; }

# ---- 2. Stage 1 ----
S1_VARS="POOL=${POOL},RL_METHOD=${RL_METHOD},EXPERIMENT_NAME=${S1_EXP},SAVE_DIR=${S1_SAVE},TOTAL_TRAINING_STEPS=${STAGE1_STEPS},SAVE_HF_MODEL=1"
echo; echo "[stage1] submitting ..."
if [[ "${DRY_RUN}" == "1" ]]; then
    echo "+ qsub -v \"${S1_VARS}\" ${HERE}/train_stage1.sh"
    JOBID1="<stage1_jobid>"
else
    JOBID1=$(qsub -v "${S1_VARS}" "${HERE}/train_stage1.sh")
    echo "  stage1 job: ${JOBID1}"
fi

# ---- 3. Stage 2 (depends on stage1 success; loads its checkpoint) ----
S2_VARS="POOL=${POOL},RL_METHOD=${RL_METHOD},EXPERIMENT_NAME=${S2_EXP},SAVE_DIR=${S2_SAVE},TOTAL_TRAINING_STEPS=${STAGE2_STEPS},MODEL_PATH=${S1_CKPT}"
echo; echo "[stage2] submitting (afterok:${JOBID1}) ..."
echo "+ qsub -W depend=afterok:${JOBID1} -v \"${S2_VARS}\" ${HERE}/train_stage2.sh"
if [[ "${DRY_RUN}" != "1" ]]; then
    JOBID2=$(qsub -W "depend=afterok:${JOBID1}" -v "${S2_VARS}" "${HERE}/train_stage2.sh")
    echo "  stage2 job: ${JOBID2}"
fi

echo; echo "Done. Monitor with: qstat -a ${JOBID1:-} ${JOBID2:-}"
echo "Stage-2 will load: ${S1_CKPT}"
echo "(If your verl writes HF weights elsewhere, override MODEL_PATH or run 'python -m verl.model_merger'.)"
