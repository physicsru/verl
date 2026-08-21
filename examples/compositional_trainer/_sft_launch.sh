#!/bin/bash
# SFT PRIMITIVE — PER-NODE (multi-node FSDP). Launched once per node by mpirun
# (via launch_mpi in train_pbs_header.sh); each node runs torchrun with its
# --node_rank from the MPI rank, so verl.trainer.sft_trainer shards a 4B model
# across all nodes' GPUs. Shared by train_stage1_sft.sh (standalone SFT) and
# run_stage1_rft.sh (the RFT loop) — RL/RFT/SFT stay separate; this is the one
# SFT entry point both reuse.
#
# Required env (exported by the caller, forwarded by mpirun -x):
#   MODEL_PATH TRAIN_FILE SAVE_DIR EXPERIMENT_NAME CUSTOM_CHAT_TEMPLATE
#   MASTER_ADDR  (+ NUM_NODES from the header)
# Optional: VAL_FILES TORCH_MASTER_PORT SFT_EPOCHS SFT_LR SFT_MAX_LENGTH SFT_BATCH SFT_MICRO_BSZ
#
# The chat template is read from $CUSTOM_CHAT_TEMPLATE via OmegaConf's oc.env
# resolver (Jinja braces never hit the shell/hydra parser). It MUST match what
# Stage-2 uses (concatenate, for the base model).
set -x
set -e

HOSTNAME=$(hostname -s)
RANK=${OMPI_COMM_WORLD_RANK:-0}
WSIZE=${OMPI_COMM_WORLD_SIZE:-1}
echo "[${HOSTNAME}] sft rank=${RANK}/${WSIZE} master=${MASTER_ADDR}"

export CUDA_VISIBLE_DEVICES=0
export PYTHONUNBUFFERED=1
source /work/go39/b20033/code/generalization_venv/bin/activate
cd "${PBS_O_WORKDIR:-/work/go39/b20033/code/generalization/verl}"

: "${MODEL_PATH:?}"; : "${TRAIN_FILE:?}"; : "${SAVE_DIR:?}"; : "${EXPERIMENT_NAME:?}"
: "${CUSTOM_CHAT_TEMPLATE:?}"

_VAL_ARG=()
if [ -n "${VAL_FILES:-}" ]; then
    _VAL_ARG+=("data.val_files=${VAL_FILES}")
fi

torchrun \
    --nnodes="${WSIZE}" --nproc_per_node=1 --node_rank="${RANK}" \
    --master_addr="${MASTER_ADDR}" --master_port="${TORCH_MASTER_PORT:-29411}" \
    -m verl.trainer.sft_trainer \
    data.train_files="${TRAIN_FILE}" \
    "${_VAL_ARG[@]}" \
    data.messages_key=messages \
    +data.apply_chat_template_kwargs.chat_template='${oc.env:CUSTOM_CHAT_TEMPLATE}' \
    data.ignore_input_ids_mismatch=True \
    data.max_length="${SFT_MAX_LENGTH:-2048}" \
    data.truncation=right \
    data.train_batch_size="${SFT_BATCH:-128}" \
    data.micro_batch_size_per_gpu="${SFT_MICRO_BSZ:-4}" \
    data.pad_mode=no_padding \
    data.use_dynamic_bsz=True \
    model.path="${MODEL_PATH}" \
    optim.lr="${SFT_LR:-2e-5}" \
    trainer.total_epochs="${SFT_EPOCHS:-2}" \
    trainer.nnodes="${WSIZE}" \
    trainer.n_gpus_per_node=1 \
    trainer.project_name="${WANDB_PROJECT:-verl_compositional}" \
    trainer.experiment_name="${EXPERIMENT_NAME}" \
    trainer.default_local_dir="${SAVE_DIR}" \
    trainer.logger="[console,wandb]" \
    trainer.save_freq=-1 \
    checkpoint.save_contents="[model,optimizer,extra,hf_model]"
