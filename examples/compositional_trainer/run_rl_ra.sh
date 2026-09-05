#!/bin/bash
# GRPO on the RA-v1 format — the "does RL learn a transferable composition
# procedure?" test (COMPOSITIONAL_HISTORY §10.6 / §12). Init = RA-v1 bootstrap
# SFT ckpt; train = compositions of 10 TRAIN ops (3 train ops = PROBE ops are
# kept out of every RL composition; 12 held-out ops never appear anywhere).
#
# Two phases (RL_PHASE=prefilter|train|all):
#   prefilter  roll the init out on the RL prompt pool (n=8, T=1) and keep only
#              prompts with MIXED outcomes — GRPO has zero advantage on
#              all-correct groups and RA-v1 is ~1.0 greedy on train ops (the §10
#              saturation death). Writes train_d2to4/ and train_d2to6/ plus the
#              per-depth signal table (go/no-go for the depth range).
#   train      GRPO (verl main_ppo) with the RA reward (final program +
#              per-episode partial reward), KL to the init, val every TEST_FREQ
#              steps on heldout / rlops / probe (tagged data_sources).
#
#   qsub -v RL_PHASE=prefilter                       examples/compositional_trainer/run_rl_ra.sh
#   qsub -v RL_PHASE=train,RL_DEPTHS=d2to4           examples/compositional_trainer/run_rl_ra.sh
#   alt init: -v RL_PHASE=prefilter,RL_TAG=d1init,RA_INIT=<path>  (PBS -v: no commas in path)
#   deep option: -v RL_PHASE=prefilter,RL_POOL=d7to10,RL_RANGES=d7to10:7:10  (train: RL_DEPTHS=d7to10)
#   knobs: KL_COEF (0.01) RA_EPISODE_BONUS (0.2) M_PROMPTS (64) ROLLOUT_N (8)
#          TOTAL_TRAINING_STEPS (300) TOTAL_EPOCHS (3) TEST_FREQ (10) RA_INIT
#
#PBS -q regular-g
#PBS -l select=8:mpiprocs=1
#PBS -l walltime=24:00:00
#PBS -W group_list=go39
#PBS -N comp-rl-ra
#PBS -j oe
#PBS -p 1023

source "${PBS_O_WORKDIR}/examples/compositional_trainer/train_pbs_header.sh"
set -e
CT=examples/compositional_trainer
export REWARD_FN="${PBS_O_WORKDIR}/${CT}/reward_fn_codeexec_ra.py"

RL_PHASE=${RL_PHASE:-all}
RL_DEPTHS=${RL_DEPTHS:-d2to4}
# RL_TAG: suffix for prefilter/train dirs + experiment name when the init is not
# the RA-v1 d14 ckpt (e.g. RA_INIT=<d1 atomics-only ckpt> RL_TAG=d1init).
RL_TAG=${RL_TAG:-}
SUF=${RL_TAG:+_${RL_TAG}}
D="${PBS_O_WORKDIR}/data/compositional/paper/rl_ra"
# RL prompt pool (prefilter input); RL_POOL=d7to10 for the deep-training option.
RL_POOL=${RL_POOL:-d2to6}
POOL_FILE="${RL_POOL_FILE:-${D}/stage2_rlops_${RL_POOL}_codeexec/train.parquet}"   # RL_POOL_FILE: explicit pool parquet (structured pools)
# NB: RA_INIT, not MODEL_PATH (header pre-exports MODEL_PATH; doc/CLAUDE.md gotcha 1).
INIT=${RA_INIT:-${PBS_O_WORKDIR}/checkpoints/compositional/ra_sft_bootstrap_paper_qwen3_4b/global_step_400/huggingface}
export COMPOSITIONAL_NUM_EXAMINE=${COMPOSITIONAL_NUM_EXAMINE:-2}

if [ "${RL_PHASE}" = "prefilter" ] || [ "${RL_PHASE}" = "all" ]; then
    echo "==================== RL-RA prefilter rollout (init @ T=1, n=8) ===================="
    export CUR_MODEL="${INIT}"
    export STAGE1_FILE="${POOL_FILE}"
    export ROLLOUT_DIR="${D}/prefilter_rollout_${RL_POOL}${SUF}"
    export N_SAMPLES=${RL_PREFILTER_N:-8} ROLLOUT_TEMP=1.0 ROLLOUT_TOP_P=1.0
    export ROLLOUT_MAX_TOKENS=2048 ROLLOUT_MAX_MODEL_LEN=4096 MAX_PROBLEMS=-1 RFT_ITER=11
    launch_mpi ${CT}/_rollout_launch.sh
    # depth ranges to materialize as RL train sets (RL_RANGES: '+'-separated NAME:LO:HI)
    RANGES=$(echo "${RL_RANGES:-d2to4:2:4+d2to6:2:6}" | tr '+' ' ')
    for R in ${RANGES}; do
        IFS=: read -r NAME LO HI <<< "${R}"
        # RL_KEEP_ALL_WRONG=1 (default): drop only ALL-CORRECT groups. All-wrong
        # groups stay — they carry episode-level partial-reward variance and can be
        # unlocked as the policy improves (a static filter reflects the init only).
        python3 ${CT}/build_rl_ra_data.py filter-train --reward "${RL_FILTER_REWARD:-correctness}" \
            $( [ "${RL_KEEP_ALL_WRONG:-1}" = "1" ] && echo --keep_all_wrong ) \
            --rollout_dir "${ROLLOUT_DIR}" --src "${POOL_FILE}" \
            --out "${D}/train_${NAME}${SUF}/train.parquet" --min_depth "${LO}" --max_depth "${HI}"
    done
fi

if [ "${RL_PHASE}" = "train" ] || [ "${RL_PHASE}" = "all" ]; then
    echo "==================== RL-RA GRPO train (${RL_DEPTHS}) ===================="
    export RL_METHOD=grpo
    export MODEL_PATH="${INIT}"
    export TRAIN_FILE="${RL_TRAIN_FILE:-${D}/train_${RL_DEPTHS}${SUF}/train.parquet}"
    [ -f "${TRAIN_FILE}" ] || { echo "[rl-ra][ERROR] no ${TRAIN_FILE} — run RL_PHASE=prefilter first"; exit 1; }
    export VAL_FILES="${RL_VAL_FILES:-${D}/val/heldout.parquet,${D}/val/rlops.parquet,${D}/val/probe.parquet}"
    export EXPERIMENT_NAME=${EXPERIMENT_NAME:-rl_ra_grpo_${RL_DEPTHS}${SUF}_qwen3_4b}
    export SAVE_DIR="${PBS_O_WORKDIR}/checkpoints/compositional/${EXPERIMENT_NAME}"
    export SAVE_HF_MODEL=1
    export M_PROMPTS=${M_PROMPTS:-64}
    export ROLLOUT_N=${ROLLOUT_N:-8}
    export PPO_MINI_BATCH_SIZE=${PPO_MINI_BATCH_SIZE:-64}
    export MAX_PROMPT_LENGTH=2048
    export MAX_RESPONSE_LENGTH=${MAX_RESPONSE_LENGTH:-4096}   # val goes to depth 12 (k~11 defs)
    export KL_COEF=${KL_COEF:-0.01}
    export RA_EPISODE_BONUS=${RA_EPISODE_BONUS:-0.2}
    export TOTAL_TRAINING_STEPS=${TOTAL_TRAINING_STEPS:-300}
    export TOTAL_EPOCHS=${TOTAL_EPOCHS:-3}
    export TEST_FREQ=${TEST_FREQ:-10}
    export SAVE_FREQ=${SAVE_FREQ:-50}
    export EARLY_STOP_RESP_LEN=${EARLY_STOP_RESP_LEN:-}   # e.g. 1500 with SAVE_FREQ=10 (RL-E-co rerun)
    # CKPT_KEEP: last-N actor ckpts to keep (verl max_actor_ckpt_to_keep); default 3. An EMPTY
    # value does NOT mean keep-all (`:-` treats empty as unset, and verl pruned steps 5-15 of
    # job 3292270 that way — ledger #10); pass CKPT_KEEP=all (or a large number) for keep-all.
    export CKPT_KEEP=${CKPT_KEEP:-3}
    [ "${CKPT_KEEP}" = "all" ] && export CKPT_KEEP=100000
    export VAL_BATCH_SIZE=${VAL_BATCH_SIZE:-512}
    launch_training
    [ -n "${RL_VAL_FILES:-}" ] && { echo "==================== RL-RA (${RL_PHASE}) finished ===================="; exit 0; }
    for FAM in heldout rlops probe; do
        case ${FAM} in
            heldout) TP="${D}/val/heldout.parquet" ;;
            rlops)   TP="${D}/val/rlops.parquet" ;;
            probe)   TP="${D}/val/probe.parquet" ;;
        esac
        python3 ${CT}/compositionality_index.py --log "${PBS_O_WORKDIR}/${PBS_JOBNAME}.o${PBS_JOBID%%.*}" \
            --test-parquet "${TP}" --source "${FAM}" --all-steps \
            --out "${PBS_O_WORKDIR}/analysis/ci_${EXPERIMENT_NAME}_${FAM}.md" || true
    done
fi
echo "==================== RL-RA (${RL_PHASE}) finished ===================="
