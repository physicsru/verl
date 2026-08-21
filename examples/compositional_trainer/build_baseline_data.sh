#!/usr/bin/env bash
# Generate all parquet datasets for the compositional-generalization baseline.
#
#   bash examples/compositional_trainer/build_baseline_data.sh paper     # paper baseline
#   bash examples/compositional_trainer/build_baseline_data.sh lenpres   # deep track
#   SMOKE=1 bash examples/compositional_trainer/build_baseline_data.sh lenpres   # tiny, fast
#
# Output layout:  data/compositional/<pool>/<split_dir>/{train,test}.parquet
set -euo pipefail

POOL=${1:-paper}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
OUT="${REPO}/data/compositional/${POOL}"
GEN="python ${HERE}/generate_data.py"

if [[ "${SMOKE:-0}" == "1" ]]; then
    N_TRAIN=200; N_EVAL=40; N_PAPER_EVAL=16   # paper level1to8 needs ÷8
else
    N_TRAIN=50000; N_EVAL=512; N_PAPER_EVAL=2048
fi

echo "Building '${POOL}' data -> ${OUT}  (N_TRAIN=${N_TRAIN}, N_EVAL=${N_EVAL})"

# --- Stage 1: atomic skills, bodies SHOWN, full op set, depth 1 ---
${GEN} --pool "${POOL}" --stage 1 --split train --min_level 1 --max_level 1 \
    --data_num "${N_TRAIN}" --seed 42 --save_path "${OUT}/stage1_level1/train.parquet"
${GEN} --pool "${POOL}" --stage 1 --split test  --min_level 1 --max_level 1 \
    --data_num "${N_EVAL}"  --seed 7  --save_path "${OUT}/stage1_level1/test.parquet"

# --- Stage 2: compositions, bodies HIDDEN, train ops, depth 1-2 ---
${GEN} --pool "${POOL}" --stage 2 --split train --min_level 1 --max_level 2 \
    --data_num "${N_TRAIN}" --seed 42 --save_path "${OUT}/stage2_level1to2/train.parquet"

if [[ "${POOL}" == "lenpres" ]]; then
    # Depth-tiered eval. IID = train ops shallow; OOD tiers = held-out ops.
    ${GEN} --pool lenpres --stage 2 --split train --min_level 1 --max_level 2 \
        --data_num "${N_EVAL}" --seed 7 --save_path "${OUT}/eval_iid/test.parquet"
    ${GEN} --pool lenpres --stage 2 --split test  --min_level 2 --max_level 3 \
        --data_num "${N_EVAL}" --seed 7 --save_path "${OUT}/eval_easy/test.parquet"
    ${GEN} --pool lenpres --stage 2 --split test  --min_level 10 --max_level 10 \
        --data_num "${N_EVAL}" --seed 7 --save_path "${OUT}/eval_medium/test.parquet"
    ${GEN} --pool lenpres --stage 2 --split test  --min_level 100 --max_level 100 \
        --data_num "${N_EVAL}" --seed 7 --save_path "${OUT}/eval_hard/test.parquet"
else
    # Paper baseline: held-out compositional eval, levels 1-8 (matches the paper).
    ${GEN} --pool paper --stage 2 --split test --min_level 1 --max_level 8 \
        --data_num "${N_PAPER_EVAL}" --seed 7 --save_path "${OUT}/stage2_level1to8/test.parquet"
fi

echo "Done. Tree:"
find "${OUT}" -name '*.parquet' | sort
