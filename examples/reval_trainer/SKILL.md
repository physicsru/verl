---
name: miyabi
description: "Miyabi HPC (GH200) reference. Use when working with miyabi: PBS templates, queue selection, node sizing, Singularity+MPI, filesystem layout."
argument-hint: "[question]"
---

# miyabi HPC

NVIDIA GH200 Grace Hopper (Grace CPU 72cores/120GB + H100 GPU 96GB HBM3), NVLink C2C.
1120 G-nodes, PBS scheduler, CUDA 12.6.

Group name is specified via the `MIYABI_GROUP` environment variable.

## Filesystem

| Path | Description | Capacity | Backup |
|------|-------------|----------|--------|
| `/home/$USER/` | Home | 25GB | Yes |
| `/work/$MIYABI_GROUP/$USER/` | Work (`$WORKDIR`) | Group allocation | No |
| `/scratch/$USER/` | Temporary (deleted after job ends) | - | No |

`$WORKDIR` = `/work/$MIYABI_GROUP/$USER/` is the main working directory.

## G-Node Batch Queues

| Queue | Nodes | walltime | Notes |
|-------|-------|----------|-------|
| debug-g | 1-16 | 30min | For debugging |
| short-g | 1-8 | 8h | Short jobs |
| small-g | 1-16 | 48h | Subset of regular-g |
| medium-g | 17-64 | 48h | |
| large-g | 65-128 | 24h | |
| x-large-g | 129-256 | 24h | |

All queues: 100GiB memory/node.

## MIG Queues (GPU Partitioning)

| Queue | MIG Instances | walltime |
|-------|---------------|----------|
| debug-mig | 1-4 | 30min |
| short-mig | 1-4 | 8h |
| regular-mig | 1-4 | 48h |

MIG: Partitions 1 GPU into up to 7 instances. For small-scale inference.

## Interactive Queues

| Queue | Nodes | walltime |
|-------|-------|----------|
| interact-g | 1 | 2h |
| interact-g | 2-8 | 10min |

`qsub -I -l select=1 -q interact-g -W group_list=$MIYABI_GROUP -l walltime=01:00:00`

## Group Limits (G-Nodes)

- Max concurrent running jobs: scales with set count (2 sets→4, 4→8, 8→16, then +2 per set)
- Max concurrent nodes: 256 nodes
- Max concurrent MIG instances: 24
- Max submittable jobs: max concurrent jobs × 8

## Node Count Selection Guide

GH200 has 1 node = 1 GPU (96GB HBM3 + 120GB LPDDR5X CPU). Use the following as a guide:

| Use Case | Nodes | Guide |
|----------|-------|-------|
| Debugging / testing | 1 | debug-g, walltime 30min |
| Small model (<1B params) | 1-2 | Check if batch_size fits in GPU memory |
| Medium model (1-7B params) | 4-8 | DDP or FSDP |
| Large model (>7B params) | 8-16+ | FSDP + activation checkpointing |

### How to Decide
1. **Calculate from GPU memory**: Check if model + optimizer state + activations + batch fit in 96GB
   - bf16: params × 2 bytes (inference) / params × 18 bytes (AdamW training)
   - If it doesn't fit, shard with FSDP and add nodes
2. **Calculate from batch_size**: global_batch_size ÷ per_gpu_batch_size = required GPUs
3. **Walltime × node count tradeoff**: More nodes reduce walltime but increase communication overhead
4. **Match queue constraints**: Available queues are determined by the combination of node count and walltime

## PBS Templates

### Sequential Job
```bash
#PBS -q debug-g
#PBS -l select=1
#PBS -l walltime=00:30:00
#PBS -W group_list=$MIYABI_GROUP
#PBS -N job-name
#PBS -j oe

cd ${PBS_O_WORKDIR}
./a.out
```

### MPI Parallel Job (Single Node)
```bash
#PBS -q short-g
#PBS -l select=1:mpiprocs=48
#PBS -l walltime=08:00:00
#PBS -W group_list=$MIYABI_GROUP
#PBS -j oe

cd ${PBS_O_WORKDIR}
mpirun ./a.out
```

### MPI Parallel Job (Multi-Node)
```bash
#PBS -q small-g
#PBS -l select=N:mpiprocs=48
#PBS -l walltime=HH:MM:SS
#PBS -W group_list=$MIYABI_GROUP
#PBS -j oe

cd ${PBS_O_WORKDIR}
mpirun ./a.out
```
mpiprocs: Total MPI processes = mpiprocs × node count (G-nodes have 48 cores/node)

### Hybrid Parallel Job (MPI + OpenMP)
```bash
#PBS -q short-g
#PBS -l select=1:mpiprocs=4:ompthreads=12
#PBS -l walltime=04:00:00
#PBS -W group_list=$MIYABI_GROUP
#PBS -j oe

cd ${PBS_O_WORKDIR}
mpirun ./a.out
```

## PBS Options

| Option | Description |
|--------|-------------|
| `-q queue` | Queue specification |
| `-l select=N[:mpiprocs=M][:ompthreads=T]` | Resources (nodes:MPI processes:OpenMP threads) |
| `-l walltime=HH:MM:SS` | Wall time limit |
| `-W group_list=GROUP` | Group specification (required) |
| `-N name` | Job name |
| `-j oe` | Merge stderr into stdout |
| `-o path` | stdout file path |
| `-m abe` | Email notifications (a:abort, b:begin, e:end) |
| `-J 0-99` | Array job |
| `-W depend=afterok:JOBID` | Job dependency |

## Compiler Environment

- **Miyabi-G batch**: NVIDIA HPC SDK is auto-loaded (`nvc`, `nvc++`, `nvfortran`)
- **Using GCC**: `module purge && module load gcc` (OpenMPI: also `module load ompi`)
- **Interactive**: NVIDIA HPC SDK auto-loaded (`module load nvidia, nv-hpcx` not needed)

## Pitfalls
- `ngpus` cannot be specified (GPU is provided by the queue)
- `$USER` is not expanded inside `#PBS` directives
- walltime must fit within the scheduled downtime window
- NVIDIA HPC SDK is auto-loaded for G-node batch jobs, so `module load` is not needed
- Singularity + MPI setup below

## Singularity + MPI
```bash
module purge && module load singularity/4.2.1 nvidia/25.9 nv-hpcx/25.9
unset OMPI_MCA_mca_base_env_list
mpirun -np $NUM_NODES --hostfile $PBS_NODEFILE -bind-to none -map-by node \
  -x PATH -x LD_LIBRARY_PATH -x MASTER_ADDR -x MASTER_PORT \
  singularity exec --nv container.sif {command}
```
