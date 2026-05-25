# Copyright 2026 verl contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""ReVal: Off-Policy Value-Based RL for LLMs (arXiv:2603.23355).

Single-model, logits-as-Q algorithm:

    L(θ) = E_{τ ~ D_replay} [ ( V_θ(s_1) − V_ref(s_1)
                                + Σ_h log π_θ(a_h|s_h)
                                − r(τ)/β
                                − Σ_h log π_ref(a_h|s_h) )^2 ]   (Eq. 2)

with V(s) := logsumexp_a Q(s, a) and Q := raw LLM logits.

This module wires ReVal into verl by subclassing the synchronous PPO trainer:
- the ref forward emits ``init_state_value`` (logsumexp at every token position),
  which is persisted on the TransferQueue as ``ref_init_state_value``;
- the actor's training forward also emits ``init_state_value``, consumed by the
  registered ``reval`` policy loss in :mod:`verl.trainer.ppo.core_algos`;
- ``actor_rollout_ref.actor.ppo_epochs`` controls K updates per fresh batch
  (paper's K=2). A persistent across-iteration FIFO replay buffer is left as an
  extension point — see the README under ``examples/reval_trainer/``.
- π_ref ← π_θ resets every ``algorithm.reval_ref_reset_freq`` global steps. This
  prototype skips the actual weight sync (logs a warning); see ``_reset_reference_policy``.
"""

import copy
import logging
import os
import time
from pprint import pprint
from typing import Any

import hydra
import numpy as np
import ray
from omegaconf import OmegaConf
from tensordict import TensorDict

try:
    import transfer_queue as tq
    from transfer_queue import KVBatchMeta
except ImportError:
    from verl.utils.transferqueue_utils import KVBatchMeta, tq

from verl.trainer.main_ppo import run_ppo
from verl.trainer.main_ppo_sync import PPOTrainer, TaskRunner as _PPOTaskRunnerActor
from verl.trainer.ppo.utils import need_critic, need_reference_policy

# main_ppo_sync.TaskRunner is decorated with @ray.remote, so it is a Ray ActorClass
# and Ray forbids inheriting from actor classes. Pull the underlying Python class
# off the ActorClass via Ray's public-ish __ray_actor_class__ attribute, then
# re-wrap our subclass with @ray.remote below.
PPOTaskRunner = _PPOTaskRunnerActor.__ray_actor_class__
from verl.utils.config import validate_config
from verl.utils.debug import marked_timer
from verl.utils.device import auto_set_device
from verl.workers.utils.padding import response_from_nested

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("VERL_LOGGING_LEVEL", "INFO"))


class RevalReplayBuffer:
    """FIFO replay buffer over TransferQueue trajectory keys (paper M=5120).

    Each entry is a ``(key, tag, partition_id)`` triple referencing data already
    materialised in the TransferQueue. The trainer guarantees those keys are
    *not* cleared after a step (see ``RevalTrainer.fit``), so a uniform sample
    from the buffer is a valid KVBatchMeta for an off-policy actor update.

    Padding rows (``tag["is_padding"]`` set by ``upsample_batch_to_divisible_size``)
    are filtered out at insertion — synthetic samples must never be replayed.
    """

    def __init__(self, capacity: int, off_policy_size: int, seed: int = 42):
        self.capacity = int(capacity)
        self.off_policy_size = int(off_policy_size)
        self.entries: list[tuple[str, dict, str]] = []
        self.rng = np.random.default_rng(seed)

    def push(
        self,
        keys: list[str],
        tags: list[dict],
        partition_id: str,
    ) -> list[tuple[str, str]]:
        """Append non-padding entries. Returns ``(key, partition_id)`` pairs
        evicted by capacity so the caller can ``tq.kv_clear`` them."""
        for k, t in zip(keys, tags):
            if t.get("is_padding", False):
                continue
            self.entries.append((k, copy.deepcopy(t), partition_id))
        evicted: list[tuple[str, str]] = []
        while len(self.entries) > self.capacity:
            k, _, p = self.entries.pop(0)
            evicted.append((k, p))
        return evicted

    def sample(self) -> tuple[list[str], list[dict], str] | None:
        """Uniformly sample ``off_policy_size`` entries; return None if buffer
        is not yet warm."""
        if len(self.entries) < self.off_policy_size:
            return None
        idxs = self.rng.choice(len(self.entries), size=self.off_policy_size, replace=False)
        keys = [self.entries[int(i)][0] for i in idxs]
        tags = [copy.deepcopy(self.entries[int(i)][1]) for i in idxs]
        partition_id = self.entries[int(idxs[0])][2]
        return keys, tags, partition_id

    def buffered_key_set(self) -> set[str]:
        return {entry[0] for entry in self.entries}

    def __len__(self) -> int:
        return len(self.entries)


class RevalTrainer(PPOTrainer):
    """PPO trainer specialised for ReVal.

    Four deltas vs. :class:`verl.trainer.main_ppo_sync.PPOTrainer`:

    1. ``calculate_init_state_value=True`` is injected into the reference and
       actor forwards so the engine surfaces V(s) per response token.
    2. ``_compute_ref_log_prob`` additionally fetches the per-token V from the
       TransferQueue and writes it back under key ``ref_init_state_value``.
    3. ``fit`` runs the paper's 2-update schedule per fresh batch: 1 on-policy
       update on the fresh batch, then 1 off-policy update sampled uniformly
       from a FIFO replay buffer of past trajectories (capacity 5120 in paper).
    4. ``fit`` periodically attempts a reference-policy reset.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        buf_cap = int(getattr(self.config.algorithm, "reval_buffer_size", 5120))
        train_bsz = int(self.config.data.train_batch_size)
        rollout_n = int(self.config.actor_rollout_ref.rollout.n)
        off_size = train_bsz * rollout_n
        seed = int(self.config.actor_rollout_ref.actor.get("data_loader_seed", 42))
        self._reval_buffer = RevalReplayBuffer(capacity=buf_cap, off_policy_size=off_size, seed=seed)
        logger.info(
            f"[reval] FIFO replay buffer initialised: capacity={buf_cap}, off_policy_batch={off_size}"
        )

    def _compute_ref_log_prob(self, batch: KVBatchMeta, metrics: dict) -> KVBatchMeta:
        metadata = {
            "calculate_entropy": False,
            "compute_loss": False,
            "calculate_init_state_value": True,
            "temperature": self.config.actor_rollout_ref.rollout.temperature,
        }
        if self.ref_in_actor:
            metadata["no_lora_adapter"] = True
        batch.extra_info.update(metadata)
        if self.ref_in_actor:
            output = self.actor_rollout_wg.compute_log_prob(batch)
        else:
            output = self.ref_policy_wg.compute_ref_log_prob(batch)
        assert len(output) == len(batch)

        t_start = time.time()
        data = tq.kv_batch_get(
            keys=batch.keys,
            partition_id=batch.partition_id,
            select_fields=["log_probs", "init_state_value", "response_mask"],
        )
        t_end = time.time()
        logger.debug(f"[reval] _compute_ref_log_prob get data: {t_end - t_start:.2f}s")

        data["ref_log_prob"] = response_from_nested(data.pop("log_probs"), data["response_mask"])
        data["ref_init_state_value"] = response_from_nested(
            data.pop("init_state_value"), data["response_mask"]
        )

        t_start = time.time()
        tq.kv_batch_put(
            keys=batch.keys,
            partition_id=batch.partition_id,
            fields=data.select("ref_log_prob", "ref_init_state_value"),
        )
        t_end = time.time()
        logger.debug(f"[reval] _compute_ref_log_prob put data: {t_end - t_start:.2f}s")
        return batch

    def _update_actor(self, batch: KVBatchMeta, metrics: dict) -> KVBatchMeta:
        # Ask the engine to emit V_θ(s_1) inside the train-time forward so the
        # ``reval`` policy loss can read it from model_output.
        batch.extra_info["calculate_init_state_value"] = True
        return super()._update_actor(batch, metrics)

    def _reset_reference_policy(self) -> None:
        """Optionally sync π_ref ← π_θ. Prototype: log-only.

        Real implementations should gather the actor's FSDP-sharded state dict
        and load it into the reference engine. The cheapest faithful path is a
        round-trip through ``actor_rollout_wg.save_checkpoint`` then
        ``ref_policy_wg.load_checkpoint``; in production you would replace this
        with an in-memory broadcast to avoid the disk cost every N steps.
        """
        logger.warning(
            "[reval] reval_ref_reset_freq>0 was requested but reference-policy "
            "reset is not wired through this prototype. Set freq=0 or implement "
            "_reset_reference_policy() with an actor→ref weight sync."
        )

    def _reval_off_policy_update(self, metrics: dict, timing_raw: dict) -> None:
        """Sample a fresh batch from the FIFO buffer and run one actor update.

        Buffered keys remain live in the TransferQueue (the surrounding ``fit``
        monkey-patches ``tq.kv_clear`` to skip them), so the actor's dispatch
        can fetch all required fields by key just like for a fresh batch.
        """
        sampled = self._reval_buffer.sample()
        metrics["reval/buffer_size"] = float(len(self._reval_buffer))
        if sampled is None:
            metrics["reval/off_policy_active"] = 0.0
            return
        off_keys, off_tags, off_pid = sampled
        off_batch = KVBatchMeta(
            keys=off_keys,
            tags=off_tags,
            partition_id=off_pid,
            extra_info={"temperature": self.config.actor_rollout_ref.rollout.temperature},
        )
        off_batch = self._balance_batch(
            off_batch, metrics=metrics, logging_prefix="reval_offpolicy_seqlen"
        )
        with marked_timer("update_actor_offpolicy", timing_raw, color="magenta"):
            self._update_actor(off_batch, metrics)
        # ``_balance_batch`` may have appended synthetic pad keys to the
        # KVBatchMeta. Those are throwaway; clear them now so they don't leak.
        off_pad_keys = [k for k, t in zip(off_batch.keys, off_batch.tags) if t.get("is_padding", False)]
        if off_pad_keys:
            tq.kv_clear(keys=off_pad_keys, partition_id=off_pid)
        metrics["reval/off_policy_active"] = 1.0

    def fit(self):
        """Paper-faithful fit loop: 1 on-policy + 1 off-policy update per step.

        Wraps :meth:`PPOTrainer.fit` with two monkey-patches restored in a
        ``finally`` block:

        * ``self.step`` runs the parent step (on-policy) then samples 1024
          trajectories from the FIFO buffer (paper M=5120) and runs a second
          actor update, then pushes the fresh batch into the buffer.
        * ``tq.kv_clear`` is shadowed by a buffer-aware version that skips
          keys currently in the FIFO buffer, so fresh trajectories survive
          across iterations (until evicted by capacity).
        """
        reset_freq = int(getattr(self.config.algorithm, "reval_ref_reset_freq", 0) or 0)
        do_ref_reset = reset_freq > 0 and self.use_reference_policy

        original_step = self.step
        original_kv_clear = tq.kv_clear

        def reval_aware_kv_clear(keys, partition_id, *args, **kwargs):
            buffered = self._reval_buffer.buffered_key_set()
            to_clear = [k for k in keys if k not in buffered]
            if not to_clear:
                return None
            return original_kv_clear(keys=to_clear, partition_id=partition_id, *args, **kwargs)

        def step_with_buffer(batch_dict, metrics, timing_raw):
            # 1) On-policy update (parent runs rollout + adv + 1 actor update).
            batch = original_step(batch_dict, metrics, timing_raw)
            # 2) Off-policy update from FIFO buffer (paper K=2).
            self._reval_off_policy_update(metrics, timing_raw)
            # 3) Push fresh (non-padding) keys into buffer so the *next* step's
            #    off-policy sample includes them. Evicted keys are real tq
            #    clears (call the un-shadowed kv_clear so they actually drop).
            evicted = self._reval_buffer.push(batch.keys, batch.tags, batch.partition_id)
            if evicted:
                evicted_by_partition: dict[str, list[str]] = {}
                for k, pid in evicted:
                    evicted_by_partition.setdefault(pid, []).append(k)
                for pid, ev_keys in evicted_by_partition.items():
                    original_kv_clear(keys=ev_keys, partition_id=pid)
                    self.replay_buffer.remove(pid, ev_keys)
            if do_ref_reset and self.global_steps > 0 and self.global_steps % reset_freq == 0:
                self._reset_reference_policy()
                metrics["reval/ref_reset"] = 1
            return batch

        self.step = step_with_buffer
        tq.kv_clear = reval_aware_kv_clear
        try:
            super().fit()
        finally:
            self.step = original_step
            tq.kv_clear = original_kv_clear


def _force_reval_config(config) -> None:
    """Pin the algorithm + policy_loss to ReVal and propagate β.

    Users can still override individual fields from the CLI; this just ensures
    that omitting them falls back to the paper-faithful defaults.
    """
    algo = config.algorithm
    actor = config.actor_rollout_ref.actor

    if algo.adv_estimator != "reval":
        logger.info(f"[reval] forcing algorithm.adv_estimator: {algo.adv_estimator} -> reval")
        algo.adv_estimator = "reval"

    policy_loss = actor.get("policy_loss", None)
    if policy_loss is None or policy_loss.get("loss_mode") != "reval":
        logger.info("[reval] forcing actor_rollout_ref.actor.policy_loss.loss_mode -> reval")
        OmegaConf.set_struct(config, False)
        if policy_loss is None:
            actor.policy_loss = OmegaConf.create({})
        actor.policy_loss.loss_mode = "reval"
        OmegaConf.set_struct(config, True)

    # Surface β to the policy loss (policy_loss.reval_beta wins if explicitly set).
    if "reval_beta" not in actor.policy_loss:
        OmegaConf.set_struct(config, False)
        actor.policy_loss.reval_beta = float(algo.get("reval_beta", 0.002))
        OmegaConf.set_struct(config, True)

    # Paper's K=2 updates per fresh batch is realised by the FIFO replay buffer
    # in :class:`RevalTrainer.fit` (1 on-policy + 1 off-policy actor update per
    # iteration). Inside each actor update we run a single epoch — multiplying
    # by ppo_epochs again would over-train each minibatch.
    if actor.get("ppo_epochs", 1) != 1:
        logger.info(f"[reval] aligning actor.ppo_epochs={actor.get('ppo_epochs', 1)} -> 1 (K=2 lives in replay buffer)")
        OmegaConf.set_struct(config, False)
        actor.ppo_epochs = 1
        OmegaConf.set_struct(config, True)


@ray.remote
class RevalTaskRunner(PPOTaskRunner):
    def run(self, config):
        pprint(OmegaConf.to_container(config, resolve=True))
        OmegaConf.resolve(config)

        tq.init(config.transfer_queue)

        self.add_actor_rollout_worker(config)
        self.add_critic_worker(config)
        self.init_resource_pool_mgr(config)

        trainer = RevalTrainer(
            config=config,
            role_worker_mapping=self.role_worker_mapping,
            resource_pool_manager=self.resource_pool_manager,
        )
        trainer.init_workers()
        trainer.fit()


@hydra.main(config_path="config", config_name="ppo_trainer", version_base=None)
def main(config):
    auto_set_device(config)
    config.transfer_queue.enable = True

    _force_reval_config(config)

    validate_config(
        config=config,
        use_reference_policy=need_reference_policy(config),
        use_critic=need_critic(config),
    )

    run_ppo(config, task_runner_class=RevalTaskRunner)


if __name__ == "__main__":
    main()
