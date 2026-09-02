#!/usr/bin/env bash
# Build the SFT data cells of the H0-vs-H1 campaign (paper pool, CPU on a login node).
#   H0: load-robust name->def binding must be installed per op (data ∝ #ops).
#   H1: it transfers across ops / can be removed at the representation level.
# Cells (all = E-co recipe: 16k mixed d2-4 train-op comps + 10k atomics; only the knob differs):
#   sub{0,3,6,9}    subset transfer — only K of the 12 held-out ops get co-occurrence practice
#                   (nested prefixes of one seeded permutation); K=12 is the existing eco cell.
#                   Readout: treated vs untreated ops (ci *_groups.md, cls_*.md per-op table).
#   dose{25,50,75}  dose curve — fraction of atomic tasks that enter grouping; 0 = v1, 100 = eco.
#   nops{4,8}       operator diversity — comps drawn from only N of the 13 train ops (nested,
#                   seed 1), total comp count fixed at 16k; N=13 is eco, N=0 is c1.
# Usage:  bash examples/compositional_trainer/build_h01_cells.sh          (FORCE=1 rebuilds)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; export HERE
REPO="$(cd "${HERE}/../.." && pwd)"
D="${REPO}/data/compositional/paper"
PY=${PY:-/work/go39/b20033/code/generalization_venv/bin/python}
GEN="${PY} ${HERE}/generate_data.py"
COMP="${D}/stage2_level1to4_codeexec/train.parquet"
ATOM="${D}/stage15_closedbook_codeexec/train.parquet"
STITCH="${PY} ${HERE}/build_ra_sft_data.py --atomic_path ${ATOM} --format v1 --n_funcless 0 \
    --n_comp 16000 --min_comp_depth 2 --max_comp_depth 4 --n_atomic 10000 --multi_atomic"
skip() { [ "${FORCE:-0}" != "1" ] && [ -f "$1" ] && { echo "[skip] $1 exists"; return 0; }; return 1; }

echo "=== subset transfer: sub0 sub3 sub6 sub9 ==="
for K in 0 3 6 9; do
    O="${D}/ra_rft/sft_bootstrap_sub${K}"
    skip "${O}/train.parquet" || ${STITCH} --comp_path "${COMP}" --cooc_heldout_k "${K}" --cooc_heldout_seed 1 --out_dir "${O}"
done

echo "=== dose curve: dose25 dose50 dose75 ==="
for F in 25 50 75; do
    O="${D}/ra_rft/sft_bootstrap_dose${F}"
    skip "${O}/train.parquet" || ${STITCH} --comp_path "${COMP}" --multi_frac "0.${F}" --out_dir "${O}"
done

echo "=== operator diversity: nops4 nops8 (regenerated comp sources) ==="
for N in 4 8; do
    OPS=$("${PY}" - "${N}" <<'PYEOF'
import os, random, sys
sys.path.insert(0, os.environ["HERE"])
import operators as o
names = sorted(o.PAPER_TRAIN_SET, key=lambda n: o.FUNC_ORDER[o.func_name_mapping[n]])
perm = random.Random(1).sample(names, len(names))   # nested prefixes: nops4 is a subset of nops8
print(",".join(perm[: int(sys.argv[1])]))
PYEOF
)
    echo "[nops${N}] train ops in compositions: ${OPS}"
    RAW="${D}/stage2_level1to4_nops${N}/train.parquet"
    CX="${D}/stage2_level1to4_nops${N}_codeexec/train.parquet"
    skip "${RAW}" || ${GEN} --pool paper --stage 2 --split train --min_level 1 --max_level 4 \
        --data_num 50000 --seed 42 --dedup program_input --ops "${OPS}" --save_path "${RAW}"
    skip "${CX}" || ${PY} "${HERE}/build_codeexec_data.py" --in "${RAW}" --out "${CX}"
    O="${D}/ra_rft/sft_bootstrap_nops${N}"
    skip "${O}/train.parquet" || { ${STITCH} --comp_path "${CX}" --out_dir "${O}"; echo "${OPS}" > "${O}/train_ops.txt"; }
done
echo "Done."
