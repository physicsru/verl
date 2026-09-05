#!/bin/bash
# Greedy held-out (or other) sweep of ONE checkpoint + CI + failure classification, on a
# small node count — for diagnosing RL/SFT checkpoints outside the ablation driver.
#   qsub -p 1023 -W group_list=go39 -N sw-<tag> \
#        -v CKPT=<huggingface dir>,TAG=<tag>[,POOL=paper][,TEST=heldout|trainops|orig12|new12|custom,TEST_FILE=<parquet>] \
#        examples/compositional_trainer/run_ckpt_sweep.sh
# Outputs: data/compositional/<POOL>/ra_rft/ckpt_sweep_<TAG>_<TEST>_b3072/, analysis/ci_ckpt_<TAG>_<TEST>.md,
#          analysis/cls_ckpt_<TAG>_<TEST>.md (per-op episode verdicts).
#PBS -q regular-g
#PBS -l select=2:mpiprocs=1
#PBS -l walltime=02:00:00
#PBS -W group_list=go39
#PBS -N ckpt-sweep
#PBS -j oe
#PBS -p 1023
source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"
set -e
CT=examples/compositional_trainer
: "${CKPT:?huggingface dir}"; : "${TAG:?tag}"
POOL=${POOL:-paper}; TEST=${TEST:-heldout}
case "${POOL}" in paper_alt) export COMPOSITIONAL_NAME_SCHEME=alt ;; paper_alt2) export COMPOSITIONAL_NAME_SCHEME=alt2 ;; esac
export COMPOSITIONAL_POOL=$([ "${POOL}" = "paper50" ] && echo paper50 || echo paper)
_BASE="${PBS_O_WORKDIR}/data/compositional/${POOL}"
case "${TEST}" in
    heldout)  F="${_BASE}/stage2_level1to8_codeexec/test.parquet" ;;
    trainops) F="${_BASE}/stage2_level1to8_trainops_codeexec/test.parquet" ;;
    orig12)   F="${PBS_O_WORKDIR}/data/compositional/paper/stage2_level1to8_codeexec/test.parquet" ;;
    new12)    F="${_BASE}/stage2_level1to8_new12_codeexec/test.parquet" ;;
    custom)   F="${TEST_FILE:?TEST=custom needs TEST_FILE}" ;;
    *) echo "unknown TEST ${TEST}"; exit 1 ;;
esac
export CUR_MODEL="${CKPT}" STAGE1_FILE="${F}"
export ROLLOUT_DIR="${_BASE}/ra_rft/ckpt_sweep_${TAG}_${TEST}_b3072"
export N_SAMPLES=1 ROLLOUT_TEMP=0.0 ROLLOUT_TOP_P=1.0 MAX_PROBLEMS=-1 RFT_ITER=97
export ROLLOUT_MAX_TOKENS=${ROLLOUT_MAX_TOKENS:-3072} ROLLOUT_MAX_MODEL_LEN=${ROLLOUT_MAX_MODEL_LEN:-4096}
echo "==================== ckpt sweep ${TAG} (${TEST}) ${CKPT} ===================="
launch_mpi ${CT}/_rollout_launch.sh
python3 ${CT}/compositionality_index.py --sweep "${TAG}=${ROLLOUT_DIR}" --out "${PBS_O_WORKDIR}/analysis/ci_ckpt_${TAG}_${TEST}.md"
python3 ${CT}/classify_ra_failures.py --sweep "${TAG}=${ROLLOUT_DIR}" --min_depth 5 --workers 12 --out "${PBS_O_WORKDIR}/analysis/cls_ckpt_${TAG}_${TEST}.md" || true
echo "==================== ckpt sweep ${TAG} finished ===================="
