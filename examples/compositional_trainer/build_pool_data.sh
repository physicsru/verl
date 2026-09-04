#!/usr/bin/env bash
# Regenerate a COMPLETE compositional pool under a given op-NAME SCHEME, row-for-row matched to
# the `paper` pool's recipe (build_baseline_data.sh + build_v3_data.sh + the RA stitcher), so a
# name ablation differs from `paper` in nothing but the names (RESULTS_PROVENANCE issue #7: the
# 2026-09-01 paper_alt stage-1.5 set had 36k rows because its comp source contained depth-1 rows).
#
#   bash examples/compositional_trainer/build_pool_data.sh paper_alt  alt     # CPU, login node
#   bash examples/compositional_trainer/build_pool_data.sh paper_alt2 alt2
#   bash examples/compositional_trainer/build_pool_data.sh paper50 num paper50   # n-scaling pool (50 ops)
# Third arg = OPERATOR pool (operators.POOLS key; default paper). Per-op counts stay at the paper
# recipe (800 stage-1.5 rows/op, 400 RA atomic tasks/op), so totals scale with #ops; a non-paper
# operator pool also gets the new-held-out-op test set (eval ops not in the paper pool) and, for
# paper50, the eco_n13 cell (paper50 atomics + the paper pool's 13-train-op comps).
#
# Existing artifacts are skipped unless FORCE=1. A stage15b train set that is not 32,000 rows is
# moved aside (kept for provenance) and rebuilt. Row counts to expect: stage15 20,000/400,
# stage15b 32,000/592, stage2_level1to4 50,000, tests 2,048 each, sft_bootstrap ~25.7k, eco ~19.7k.
set -euo pipefail

POOL=${1:?pool dir name, e.g. paper_alt}
SCHEME=${2:?name scheme: num | alt | alt2}
OPPOOL=${3:-paper}
export COMPOSITIONAL_NAME_SCHEME=${SCHEME}
export COMPOSITIONAL_POOL=${OPPOOL}
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${HERE}/../.." && pwd)"
OUT="${REPO}/data/compositional/${POOL}"
SRC="${OUT}/_v3_src"
PY=${PY:-/work/go39/b20033/code/generalization_venv/bin/python}
GEN="${PY} ${HERE}/generate_data.py"
mkdir -p "${SRC}"
N_OPS=$("${PY}" -c "import sys; sys.path.insert(0,'${HERE}'); import operators as o; print(len(o.POOLS['${OPPOOL}']['all']))")
N_ATOMIC=$((400 * N_OPS)); S15B_ROWS=$((800 * N_OPS + 12000))
NEW_EVAL=$("${PY}" -c "import sys; sys.path.insert(0,'${HERE}'); import operators as o; print(','.join(n for n in o.POOLS['${OPPOOL}']['eval'] if n not in o.PAPER_EVAL_SET))")

skip() { [ "${FORCE:-0}" != "1" ] && [ -f "$1" ] && { echo "[skip] $1 exists"; return 0; }; return 1; }
rows() { "${PY}" -c "import pandas as pd,sys; print(len(pd.read_parquet(sys.argv[1])))" "$1"; }

echo "=== pool=${POOL} scheme=${SCHEME} ops=${OPPOOL} (${N_OPS} ops, n_atomic=${N_ATOMIC}, stage15b rows=${S15B_ROWS}) -> ${OUT}"

echo "=== 1/6 stage-1.5 source pools (build_v3_data.sh recipe) ==="
skip "${SRC}/cb_src_trainops.parquet" || ${GEN} --pool ${OPPOOL} --stage 2 --split train --min_level 1 --max_level 1 \
    --data_num 30000 --dedup program_input --seed 20260715 --save_path "${SRC}/cb_src_trainops.parquet"
skip "${SRC}/cb_src_evalops.parquet" || ${GEN} --pool ${OPPOOL} --stage 2 --split test --min_level 1 --max_level 1 \
    --data_num 30000 --dedup program_input --seed 20260716 --save_path "${SRC}/cb_src_evalops.parquet"
skip "${SRC}/comp_src_trainops.parquet" || ${GEN} --pool ${OPPOOL} --stage 2 --split train --min_level 2 --max_level 4 \
    --data_num 30000 --dedup program_input --seed 20260728 --save_path "${SRC}/comp_src_trainops.parquet"

echo "=== 2/6 stage-1.5 atomic set (20k, the RA stitcher's --atomic_path) ==="
skip "${OUT}/stage15_closedbook_codeexec/train.parquet" || ${PY} "${HERE}/build_closedbook_codeexec.py" \
    --src "${SRC}/cb_src_trainops.parquet" "${SRC}/cb_src_evalops.parquet" \
    --pool "${OPPOOL}" --out_dir "${OUT}/stage15_closedbook_codeexec" --per_op 800 --val_per_op 16 --seed 7

echo "=== 3/6 stage-1.5b set (20k atomics + 12k depth-2..4 train-op comps) ==="
S15B="${OUT}/stage15b_closedbook_codeexec"
if [ -f "${S15B}/train.parquet" ] && [ "$(rows "${S15B}/train.parquet")" != "${S15B_ROWS}" ]; then
    ASIDE="${S15B}_unmatched_$(date +%Y%m%d)"
    echo "[build-pool] ${S15B} has $(rows "${S15B}/train.parquet") rows (expected ${S15B_ROWS}) -> moving to ${ASIDE}"
    mv "${S15B}" "${ASIDE}"
fi
skip "${S15B}/train.parquet" || ${PY} "${HERE}/build_closedbook_codeexec.py" \
    --src "${SRC}/cb_src_trainops.parquet" "${SRC}/cb_src_evalops.parquet" \
    --comp_src "${SRC}/comp_src_trainops.parquet" --comp_min_depth 2 --pool "${OPPOOL}" \
    --out_dir "${S15B}" --per_op 800 --val_per_op 16 --comp_per_depth 4000 --comp_val_per_depth 64 --seed 7
[ "$(rows "${S15B}/train.parquet")" = "${S15B_ROWS}" ] || { echo "[build-pool][ERROR] stage15b rows != ${S15B_ROWS}"; exit 1; }

echo "=== 4/6 RA comp source: stage-2 train-op compositions, depths 1-4 -> code-exec ==="
skip "${OUT}/stage2_level1to4/train.parquet" || ${GEN} --pool ${OPPOOL} --stage 2 --split train --min_level 1 --max_level 4 \
    --data_num 50000 --seed 42 --save_path "${OUT}/stage2_level1to4/train.parquet"
skip "${OUT}/stage2_level1to4_codeexec/train.parquet" || ${PY} "${HERE}/build_codeexec_data.py" \
    --in "${OUT}/stage2_level1to4/train.parquet" --out "${OUT}/stage2_level1to4_codeexec/train.parquet"

echo "=== 5/6 test sets: held-out ops and train ops, depths 1-8 (2048 rows, seed 7) ==="
skip "${OUT}/stage2_level1to8/test.parquet" || ${GEN} --pool ${OPPOOL} --stage 2 --split test --min_level 1 --max_level 8 \
    --data_num 2048 --seed 7 --save_path "${OUT}/stage2_level1to8/test.parquet"
skip "${OUT}/stage2_level1to8_codeexec/test.parquet" || ${PY} "${HERE}/build_codeexec_data.py" \
    --in "${OUT}/stage2_level1to8/test.parquet" --out "${OUT}/stage2_level1to8_codeexec/test.parquet"
skip "${OUT}/stage2_level1to8_trainops/test.parquet" || ${GEN} --pool ${OPPOOL} --stage 2 --split train --min_level 1 --max_level 8 \
    --data_num 2048 --seed 7 --save_path "${OUT}/stage2_level1to8_trainops/test.parquet"
skip "${OUT}/stage2_level1to8_trainops_codeexec/test.parquet" || ${PY} "${HERE}/build_codeexec_data.py" \
    --in "${OUT}/stage2_level1to8_trainops/test.parquet" --out "${OUT}/stage2_level1to8_trainops_codeexec/test.parquet"
if [ -n "${NEW_EVAL}" ]; then
    echo "=== 5b/6 test set over the NEW held-out ops only (${NEW_EVAL}) ==="
    skip "${OUT}/stage2_level1to8_new12/test.parquet" || ${GEN} --pool "${OPPOOL}" --stage 2 --split test --min_level 1 --max_level 8 \
        --data_num 2048 --seed 7 --ops "${NEW_EVAL}" --save_path "${OUT}/stage2_level1to8_new12/test.parquet"
    skip "${OUT}/stage2_level1to8_new12_codeexec/test.parquet" || ${PY} "${HERE}/build_codeexec_data.py" \
        --in "${OUT}/stage2_level1to8_new12/test.parquet" --out "${OUT}/stage2_level1to8_new12_codeexec/test.parquet"
fi

echo "=== 6/6 RA stitched SFT data: v1 (single-task atomics) and E-co (co-occurrence atomics) ==="
STITCH="${PY} ${HERE}/build_ra_sft_data.py --comp_path ${OUT}/stage2_level1to4_codeexec/train.parquet \
    --atomic_path ${OUT}/stage15_closedbook_codeexec/train.parquet --format v1 --n_funcless 0 \
    --n_comp 16000 --min_comp_depth 2 --max_comp_depth 4 --n_atomic ${N_ATOMIC} --pool ${OPPOOL}"
skip "${OUT}/ra_rft/sft_bootstrap/train.parquet" || ${STITCH} --out_dir "${OUT}/ra_rft/sft_bootstrap"
skip "${OUT}/ra_rft/sft_bootstrap_eco/train.parquet" || ${STITCH} --multi_atomic --out_dir "${OUT}/ra_rft/sft_bootstrap_eco"
if [ "${OPPOOL}" = "paper50" ]; then
    echo "=== 6b/6 eco_n13: paper50 atomics + the paper pool's 16k comps over its 13 train ops ==="
    skip "${OUT}/ra_rft/sft_bootstrap_eco_n13/train.parquet" || ${PY} "${HERE}/build_ra_sft_data.py" \
        --comp_path "${REPO}/data/compositional/paper/stage2_level1to4_codeexec/train.parquet" \
        --atomic_path "${OUT}/stage15_closedbook_codeexec/train.parquet" --format v1 --n_funcless 0 \
        --n_comp 16000 --min_comp_depth 2 --max_comp_depth 4 --n_atomic ${N_ATOMIC} --pool ${OPPOOL} \
        --multi_atomic --out_dir "${OUT}/ra_rft/sft_bootstrap_eco_n13"
fi

echo "Done. Row counts:"
for f in stage15_closedbook_codeexec/train stage15b_closedbook_codeexec/train stage2_level1to4_codeexec/train \
         stage2_level1to8_codeexec/test stage2_level1to8_trainops_codeexec/test stage2_level1to8_new12_codeexec/test \
         ra_rft/sft_bootstrap/train ra_rft/sft_bootstrap_eco/train ra_rft/sft_bootstrap_eco_n13/train; do
    [ -f "${OUT}/${f}.parquet" ] && printf "  %-45s %s\n" "${f}" "$(rows "${OUT}/${f}.parquet")"
done
