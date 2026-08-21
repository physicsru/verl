#!/bin/bash
# TRAIN-OP depth-1-8 sweep (WALKTHROUGH §16): evaluate checkpoints on
# compositions of the 13 TRAIN operators — atoms fully practiced (incl. inside
# compositions), so held-out-op generalization is removed and what remains is
# pure DEPTH extrapolation (depth 5-8 unseen for every variant; depth 3-8
# unseen for d12). Side-by-side with the held-out-op sweeps this decomposes
# op-generalization vs depth-generalization.
#
# Sweeps (greedy, 2048 problems each) over: stage15b baseline + RA ablation
# variants d1/d12/d13b/d14. Data: stage2_level1to8_trainops_codeexec (seed 7;
# NB depth<=4 rows may coincide with training programs — that's acceptable
# here, in-distribution is the point at shallow depth).
#
#   qsub examples/compositional_trainer/run_trainops_sweep.sh
#
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=06:00:00
#PBS -W group_list=go39
#PBS -N comp-tops-swp
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"
set -e
CT=examples/compositional_trainer
export REWARD_FN="${PBS_O_WORKDIR}/${CT}/reward_fn_codeexec.py"

_BASE="${PBS_O_WORKDIR}/data/compositional/paper"
CKROOT="${PBS_O_WORKDIR}/checkpoints/compositional"
export STAGE1_FILE="${_BASE}/stage2_level1to8_trainops_codeexec/test.parquet"
export N_SAMPLES=1
export ROLLOUT_TEMP=0.0
export ROLLOUT_TOP_P=1.0
export ROLLOUT_MAX_TOKENS=1536
export ROLLOUT_MAX_MODEL_LEN=4096
export MAX_PROBLEMS=-1

resolve_hf_ckpt() { find "$1" -type d -name huggingface 2>/dev/null | sort | tail -1; }

SWEEPS=(
  "baseline=${CKROOT}/stage15b_paper_closedbook_cx_qwen3_4b/global_step_500/huggingface"
  "d1=$(resolve_hf_ckpt ${CKROOT}/ra_sft_bootstrap_paper_d1_qwen3_4b)"
  "d12=$(resolve_hf_ckpt ${CKROOT}/ra_sft_bootstrap_paper_d12_qwen3_4b)"
  "d13b=$(resolve_hf_ckpt ${CKROOT}/ra_sft_bootstrap_paper_d13b_qwen3_4b)"
  "d14=$(resolve_hf_ckpt ${CKROOT}/ra_sft_bootstrap_paper_qwen3_4b)"
)

CI_ARGS=()
SEED=91
for SPEC in "${SWEEPS[@]}"; do
    LABEL="${SPEC%%=*}"; CKPT="${SPEC#*=}"
    if [ -z "${CKPT}" ] || [ ! -d "${CKPT}" ]; then
        echo "[tops][ERROR] missing checkpoint for ${LABEL}: '${CKPT}'"; exit 1
    fi
    echo "==================== train-op sweep ${LABEL} (${CKPT}) ===================="
    export CUR_MODEL="${CKPT}"
    export RFT_ITER=${SEED}; SEED=$((SEED+1))
    export ROLLOUT_DIR="${_BASE}/ra_rft/trainops_sweep_${LABEL}"
    launch_mpi ${CT}/_rollout_launch.sh
    CI_ARGS+=("${LABEL}=${ROLLOUT_DIR}")
done

python3 ${CT}/compositionality_index.py \
    --sweep "${CI_ARGS[@]}" \
    --out "${PBS_O_WORKDIR}/analysis/ci_trainops_sweep.md"

echo "==================== train-op sweep finished ===================="
echo "CI report: analysis/ci_trainops_sweep.md"
