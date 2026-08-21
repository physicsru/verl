#!/bin/bash
# RECALL-THEN-ASSEMBLE prompted RFT — the ladder-step-1 intervention against
# composition interference (WALKTHROUGH §§11-13).
#
# Atomic closed-book recall of every held-out op is perfect (x_i = 1.0), but
# multi-def emission degrades per-op reliability to ~0.4-0.6. This loop teaches
# an OP-AGNOSTIC format that reduces a composition to sequential isolated
# recall episodes + an assemble block, via prompted RFT on TRAIN-op
# compositions (depth 2-4):
#
#   for it in 1..RA_ITERS:
#     1) rollout the CURRENT model on ELICITATION prompts (format instruction +
#        one train-op worked example) — _rollout_launch.sh, data-parallel
#     2) verify HARD (full-program exec AND per-recall-block unit tests vs the
#        hidden reference), strip the scaffold -> SFT pairs on the ORIGINAL
#        stage-2 prompt, + depth-1 all-25-op recall replay  — build_ra_rft_data.py
#     3) multi-node FSDP SFT — _sft_launch.sh
#   finally: greedy sweep of the held-out depth-1-8 test set + CI report.
#
# Success metric: held-out CI(2) / CI(3) from the final report vs the 0.67/0.21
# baseline (analysis/ci_stage15b.md; stage15/312 init is similar).
#
#   qsub examples/compositional_trainer/run_ra_rft.sh
#
# Requires (CPU, done beforehand):
#   python examples/compositional_trainer/build_ra_elicit_data.py \
#       --in_path data/compositional/paper/stage2_level1to4_codeexec/train.parquet \
#       --out_path data/compositional/paper/ra_rft/elicit.parquet
#
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=24:00:00
#PBS -W group_list=go39
#PBS -N comp-ra-rft
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"
set -e
CT=examples/compositional_trainer
export REWARD_FN="${PBS_O_WORKDIR}/${CT}/reward_fn_codeexec.py"

POOL=${POOL:-paper}
RA_ITERS=${RA_ITERS:-1}
export N_SAMPLES=${N_SAMPLES:-4}
export ROLLOUT_TEMP=${ROLLOUT_TEMP:-1.0}
export ROLLOUT_TOP_P=${ROLLOUT_TOP_P:-1.0}
export ROLLOUT_MAX_TOKENS=${ROLLOUT_MAX_TOKENS:-1536}
export ROLLOUT_MAX_MODEL_LEN=${ROLLOUT_MAX_MODEL_LEN:-4096}
export MAX_PROBLEMS=${MAX_PROBLEMS:-12000}    # per iter, fresh seed each iter
MAX_KEEP=${MAX_KEEP:-2}
REPLAY_N=${REPLAY_N:-8000}

export TORCH_MASTER_PORT=${TORCH_MASTER_PORT:-29412}
export SFT_EPOCHS=${SFT_EPOCHS:-2}
export SFT_LR=${SFT_LR:-2e-5}
export SFT_MAX_LENGTH=${SFT_MAX_LENGTH:-3072}
export SFT_BATCH=${SFT_BATCH:-128}
export SFT_MICRO_BSZ=${SFT_MICRO_BSZ:-4}

_BASE="${PBS_O_WORKDIR}/data/compositional/${POOL}"
export STAGE1_FILE="${_BASE}/ra_rft/elicit.parquet"
# Replay for RFT iters = the STITCHED (RA-format) data, incl. all-25-op
# atomics — replaying native-format stage15 rows here would re-teach the
# one-block habit the bootstrap just removed.
REPLAY_FILE="${_BASE}/ra_rft/sft_bootstrap/train.parquet"
TEST_FILE="${_BASE}/stage2_level1to8_codeexec/test.parquet"
RA_ROOT="${_BASE}/ra_rft"

# Init = stage15b/500, NOT the less-baked stage15/312: smoke 2487679 showed
# stage15/312 predates the EOS fix (88% of rollouts cap-fill with repeated
# single-op episodes) and ignores the multi-recall format entirely, so it
# cannot be prompted-RFT elicited. stage15b terminates and follows formats.
# NB: use RA_INIT, not MODEL_PATH — train_pbs_header.sh has already exported
# MODEL_PATH=Qwen/Qwen3-4B-Base by this point, so a ${MODEL_PATH:-...} fallback
# never fires (job 2488926 silently ran the whole pipeline from base).
export CUR_MODEL=${RA_INIT:-${PBS_O_WORKDIR}/checkpoints/compositional/stage15b_paper_closedbook_cx_qwen3_4b/global_step_500/huggingface}

resolve_hf_ckpt() { find "$1" -type d -name huggingface 2>/dev/null | sort | tail -1; }

# ---- phase 0: BOOTSTRAP SFT on synthetically stitched RA targets.
# Elicitation from stage15b yields 0.4% verified (smokes 2487685/2488107/
# 2488215 — the one-block habit resists prompting), so the format is first
# installed by SFT on stitched data (build_ra_sft_data.py: content = the
# model's own stage-1.5 target distribution, structure = RA). RFT iterations
# below then refine ON-POLICY from this checkpoint.
RA_BOOTSTRAP=${RA_BOOTSTRAP:-1}
if [ "${RA_BOOTSTRAP}" = "1" ]; then
    echo "==================== RA bootstrap SFT (model=${CUR_MODEL}) ===================="
    export EXPERIMENT_NAME="ra_sft_bootstrap_${POOL}_qwen3_4b"
    export SAVE_DIR="${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}"
    export TRAIN_FILE="${RA_ROOT}/sft_bootstrap/train.parquet"
    export VAL_FILES="${RA_ROOT}/sft_bootstrap/test.parquet"
    export MODEL_PATH="${CUR_MODEL}"
    launch_mpi ${CT}/_sft_launch.sh
    NEW_CKPT="$(resolve_hf_ckpt "${SAVE_DIR}")"
    if [ -z "${NEW_CKPT}" ]; then
        echo "[ra-rft][ERROR] bootstrap SFT produced no checkpoint; aborting."; exit 1
    fi
    echo "[ra-rft] bootstrap done -> ${NEW_CKPT}"
    export CUR_MODEL="${NEW_CKPT}"
fi

for ((it=1; it<=RA_ITERS; it++)); do
    echo "==================== RA-RFT iteration ${it}/${RA_ITERS} (model=${CUR_MODEL}) ===================="
    export RFT_ITER=${it}
    ITDIR="${RA_ROOT}/iter${it}"
    export ROLLOUT_DIR="${ITDIR}/rollouts"
    SFT_DATA="${ITDIR}/sft_data"
    export EXPERIMENT_NAME="ra_rft_${POOL}_iter${it}_qwen3_4b"
    export SAVE_DIR="${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}"
    export TRAIN_FILE="${SFT_DATA}/train.parquet"
    export VAL_FILES="${SFT_DATA}/test.parquet"
    export MODEL_PATH="${CUR_MODEL}"

    launch_mpi ${CT}/_rollout_launch.sh

    python3 ${CT}/build_ra_rft_data.py --rollout_path "${ROLLOUT_DIR}" \
        --out_dir "${SFT_DATA}" --val_size 256 --max_keep_per_problem "${MAX_KEEP}" \
        --replay_file "${REPLAY_FILE}" --replay_n "${REPLAY_N}"

    launch_mpi ${CT}/_sft_launch.sh

    NEW_CKPT="$(resolve_hf_ckpt "${SAVE_DIR}")"
    if [ -z "${NEW_CKPT}" ]; then
        echo "[ra-rft][ERROR] no HF checkpoint found under ${SAVE_DIR}; aborting."; exit 1
    fi
    echo "[ra-rft] iteration ${it} done -> ${NEW_CKPT}"
    export CUR_MODEL="${NEW_CKPT}"
done

# ---- final verdict: greedy held-out depth-1-8 sweep + Compositionality Index
echo "==================== RA-RFT sweep+CI (model=${CUR_MODEL}) ===================="
export RFT_ITER=99
export STAGE1_FILE="${TEST_FILE}"
export ROLLOUT_DIR="${RA_ROOT}/final_sweep"
export N_SAMPLES=1
export ROLLOUT_TEMP=0.0
export MAX_PROBLEMS=-1
launch_mpi ${CT}/_rollout_launch.sh

python3 ${CT}/compositionality_index.py \
    --sweep ra_rft="${ROLLOUT_DIR}" \
    --out "${PBS_O_WORKDIR}/analysis/ci_ra_rft.md"

echo "==================== RA-RFT finished. Final model: ${CUR_MODEL} ===================="
echo "CI report: analysis/ci_ra_rft.md (baseline: analysis/ci_stage15b.md)"
