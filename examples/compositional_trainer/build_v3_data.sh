#!/usr/bin/env bash
# Build ALL v3 data (CPU-only, run on a login node):
#   1. stage-1.5b closed-book SFT set = depth-1 all 25 ops (as stage-1.5)
#      + depth-2..4 TRAIN-op multi-helper compositions (the v2 autopsy fix)
#   2. stage-2 v3 RL train set at depths 1-4 (was 1-2), code-exec condition
# Val stays the existing held-out stage2_level1to8_codeexec/test.parquet.
#
#   bash examples/compositional_trainer/build_v3_data.sh
#
# NOTE the EOS fix lives in train_pbs_header.sh (CUSTOM_CHAT_TEMPLATE now ends
# assistant turns with eos_token) — data targets are unchanged; the template
# adds EOS at tokenization time, inside the SFT loss mask.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
OUT="${REPO}/data/compositional/paper"
SRC="${OUT}/_v3_src"
PY=${PY:-/work/go39/b20033/code/generalization_venv/bin/python}
GEN="${PY} ${HERE}/generate_data.py"

echo "=== 1/4 source pools for the SFT builder ==="
${GEN} --pool paper --stage 2 --split train --min_level 1 --max_level 1 \
    --data_num 30000 --dedup program_input --seed 20260715 \
    --save_path "${SRC}/cb_src_trainops.parquet"
${GEN} --pool paper --stage 2 --split test --min_level 1 --max_level 1 \
    --data_num 30000 --dedup program_input --seed 20260716 \
    --save_path "${SRC}/cb_src_evalops.parquet"
${GEN} --pool paper --stage 2 --split train --min_level 2 --max_level 4 \
    --data_num 30000 --dedup program_input --seed 20260728 \
    --save_path "${SRC}/comp_src_trainops.parquet"

echo "=== 2/4 stage-1.5b closed-book SFT data (depth-1 + multi-helper) ==="
${PY} "${HERE}/build_closedbook_codeexec.py" \
    --src "${SRC}/cb_src_trainops.parquet" "${SRC}/cb_src_evalops.parquet" \
    --comp_src "${SRC}/comp_src_trainops.parquet" \
    --out_dir "${OUT}/stage15b_closedbook_codeexec" \
    --per_op 800 --val_per_op 16 --comp_per_depth 4000 --comp_val_per_depth 64 --seed 7

echo "=== 3/4 stage-2 v3 RL train data, depths 1-4 (train ops) ==="
${GEN} --pool paper --stage 2 --split train --min_level 1 --max_level 4 \
    --data_num 50000 --seed 42 --save_path "${OUT}/stage2_level1to4/train.parquet"

echo "=== 4/4 convert RL data to the code-exec condition ==="
${PY} "${HERE}/build_codeexec_data.py" \
    --in "${OUT}/stage2_level1to4/train.parquet" \
    --out "${OUT}/stage2_level1to4_codeexec/train.parquet"

echo "Done. Tree:"
find "${OUT}/stage15b_closedbook_codeexec" "${OUT}/stage2_level1to4_codeexec" -name '*.parquet' | sort
