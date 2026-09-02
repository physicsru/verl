#!/usr/bin/env bash
# Submit the H0-vs-H1 campaign (analysis/RESULTS_PROVENANCE.md "H0/H1 PLAN").
#   DRY_RUN=1 (default) only prints the qsub lines; DRY_RUN=0 submits.
#   PARTS=cells,names (default both); GROUP=gj26|go39 (pick by free room, qstat --limit);
#   SEEDS="1 7 123".
# cells : sub0/3/6/9, dose25/50/75, nops4/8 × seeds on the paper pool — data from
#         build_h01_cells.sh — 27 RA jobs (8 nodes each, run_ra_depth_ablation.sh).
# names : matched name ablation — stage-1.5 from base for paper_alt and paper_alt2 (data from
#         build_pool_data.sh), then RA v1 + eco × seeds per pool queued behind it with
#         -W depend=afterok; plus the num side re-done from stage15b_num_frombase (job 3278516):
#         v1 s7/s123 (s1 = job 3279397) and eco s1/s7/s123, tagged numfb. 2 + 12 + 5 jobs.
# NB gotcha 1 (doc/CLAUDE.md): train_pbs_header.sh pre-exports MODEL_PATH=Qwen/Qwen3-4B-Base, so
# the stage-1.5 jobs run from base whatever -v says; MODEL_PATH is passed anyway for the record.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."          # PBS_O_WORKDIR must be the repo root
ROOT="$(pwd)"
CT=examples/compositional_trainer
GROUP=${GROUP:-gj26}
DRY_RUN=${DRY_RUN:-1}
PARTS=${PARTS:-cells,names}
SEEDS=${SEEDS:-1 7 123}
Q="qsub -p 1023 -W group_list=${GROUP}"
PY=${PY:-/work/go39/b20033/code/generalization_venv/bin/python}

run() { echo "+ $*"; [ "${DRY_RUN}" = "1" ] || "$@"; }
submit() { echo "+ $*" >&2; if [ "${DRY_RUN}" = "1" ]; then echo "DRYRUN.${RANDOM}"; else "$@"; fi; }

if [[ ",${PARTS}," == *",cells,"* ]]; then
    echo "### cells (paper pool)"
    for CELL in sub0 sub3 sub6 sub9 dose25 dose50 dose75 nops4 nops8; do
        if [ ! -f "data/compositional/paper/ra_rft/sft_bootstrap_${CELL}/train.parquet" ]; then
            echo "[skip] ${CELL}: no data (run ${CT}/build_h01_cells.sh)"; continue
        fi
        for S in ${SEEDS}; do
            run ${Q} -N "ra-${CELL}-s${S}" \
                -v "ABL_VARIANTS=${CELL},SFT_SEED=${S},ABL_TEST_SETS=heldout+trainops" \
                "${CT}/run_ra_depth_ablation.sh"
        done
    done
fi

if [[ ",${PARTS}," == *",names,"* ]]; then
    echo "### names (matched pools)"
    for P in paper_alt paper_alt2; do
        F="data/compositional/${P}/stage15b_closedbook_codeexec/train.parquet"
        NROWS=$([ -f "${F}" ] && "${PY}" -c "import pandas as pd,sys; print(len(pd.read_parquet(sys.argv[1])))" "${F}" || echo 0)
        if [ "${NROWS}" != "32000" ]; then
            echo "[skip] ${P}: stage15b train has ${NROWS} rows, need the matched 32000 (run ${CT}/build_pool_data.sh ${P} ${P#paper_})"; continue
        fi
        EXP="stage15b_${P}_frombase_matched_qwen3_4b"
        JID=$(submit ${Q} -N "s15b-${P#paper_}" \
                -v "POOL=${P},EXPERIMENT_NAME=${EXP},MODEL_PATH=Qwen/Qwen3-4B-Base" \
                "${CT}/train_stage15b_closedbook_codeexec.sh")
        for VAR in v1 eco; do
            for S in ${SEEDS}; do
                run ${Q} -W "depend=afterok:${JID}" -N "ra-${P#paper_}-${VAR}-s${S}" \
                    -v "POOL=${P},ABL_VARIANTS=${VAR},SFT_SEED=${S},ABL_TEST_SETS=heldout+trainops,RA_INIT=${ROOT}/checkpoints/compositional/${EXP}" \
                    "${CT}/run_ra_depth_ablation.sh"
            done
        done
    done
    NUM="${ROOT}/checkpoints/compositional/stage15b_num_frombase_qwen3_4b/global_step_500/huggingface"
    for S in 7 123; do
        run ${Q} -N "ra-numfb-v1-s${S}" \
            -v "ABL_VARIANTS=v1,ABL_TAG=numfb,SFT_SEED=${S},ABL_TEST_SETS=heldout+trainops,RA_INIT=${NUM}" \
            "${CT}/run_ra_depth_ablation.sh"
    done
    for S in ${SEEDS}; do
        run ${Q} -N "ra-numfb-eco-s${S}" \
            -v "ABL_VARIANTS=eco,ABL_TAG=numfb,SFT_SEED=${S},ABL_TEST_SETS=heldout+trainops,RA_INIT=${NUM}" \
            "${CT}/run_ra_depth_ablation.sh"
    done
fi
echo "### done (DRY_RUN=${DRY_RUN})"
