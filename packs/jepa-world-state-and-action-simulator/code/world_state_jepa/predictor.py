"""Factored world-state representation and action-conditioned latent state predictor (JEPA)."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any

from .grid import load_default_grid_spec


@dataclass(frozen=True)
class FactoredWorldState:
    """Compact factored latent representation of environment state."""

    leases: dict[str, dict[str, Any]]
    resource_quotas: dict[str, float]
    record_digests: dict[str, dict[str, Any]]
    capability_taints: tuple[str, ...]
    invariant_predicates: dict[str, bool]
    latent_vector: tuple[float, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "leases": copy.deepcopy(self.leases),
            "resource_quotas": dict(self.resource_quotas),
            "record_digests": copy.deepcopy(self.record_digests),
            "capability_taints": list(self.capability_taints),
            "invariant_predicates": dict(self.invariant_predicates),
            "latent_vector": list(self.latent_vector),
        }

    def all_invariants_hold(self) -> bool:
        return all(bool(val) for val in self.invariant_predicates.values())


class ActionConditionedStatePredictor:
    """Encodes raw observations into factored latent space and predicts s_hat_{t+1} = transition(s_t, a_t)."""

    def __init__(self, *, spec: dict[str, Any] | None = None) -> None:
        cfg = copy.deepcopy(spec if spec is not None else load_default_grid_spec())
        num = cfg["numerics"]
        pred = cfg["predictor"]

        self._eps = float(num["epsilon"])
        self._round_digits = int(num["round_digits"])
        self._digest_chars = int(num["digest_chars"])
        self._latent_dim = int(num["latent_dim"])
        self._hash_mod = int(num["hash_modulus"])

        self._forbidden_taints = frozenset(str(t) for t in pred["forbidden_write_taints"])
        self._lease_scale_cap = float(pred["lease_scale_cap"])
        self._taint_scale_cap = float(pred["taint_scale_cap"])
        self._step_quota_weight = float(pred["step_quota_pressure_weight"])
        self._step_taint_weight = float(pred["step_taint_risk_weight"])
        self._irreversible_exposure = float(pred["irreversible_step_exposure"])
        self._invariant_penalty = float(pred["invariant_breach_penalty"])
        self._low_quota_floor = float(pred["low_quota_warning_floor"])

    def _compute_latent_vector(
        self,
        leases: dict[str, dict[str, Any]],
        quotas: dict[str, float],
        digests: dict[str, dict[str, Any]],
        taints: tuple[str, ...],
        invariants: dict[str, bool],
    ) -> tuple[float, ...]:
        """Project structured world-state factors into a normalized R^D latent embedding."""
        q_vals = [float(v) for _, v in sorted(quotas.items())]
        mean_q = sum(q_vals) / float(len(q_vals)) if q_vals else 1.0
        min_q = min(q_vals) if q_vals else 1.0
        lease_ratio = min(1.0, float(len(leases)) / max(1.0, self._lease_scale_cap))
        taint_ratio = min(1.0, float(len(taints)) / max(1.0, self._taint_scale_cap))
        inv_vals = [1.0 if bool(v) else 0.0 for _, v in sorted(invariants.items())]
        inv_ratio = sum(inv_vals) / float(len(inv_vals)) if inv_vals else 1.0

        base_coords = [mean_q, min_q, lease_ratio, taint_ratio, inv_ratio]
        state_summary = json.dumps(
            {"leases": leases, "digests": digests, "taints": list(taints)},
            sort_keys=True,
            separators=(",", ":"),
        )
        coords: list[float] = []
        for idx in range(self._latent_dim):
            if idx < len(base_coords):
                coords.append(base_coords[idx])
            else:
                h_bytes = hashlib.sha256(f"lat:{idx}:{state_summary}".encode("utf-8")).digest()
                raw_int = int.from_bytes(h_bytes, "big") % self._hash_mod
                coords.append(float(raw_int) / float(self._hash_mod - 1))

        sq_norm = sum(c * c for c in coords)
        norm = math.sqrt(max(sq_norm, self._eps))
        return tuple(round(c / norm, self._round_digits) for c in coords)

    def encode_observation(self, raw_obs: dict[str, Any]) -> FactoredWorldState:
        """Encode environment observation into factored representation, discarding surface nuisance fields."""
        leases: dict[str, dict[str, Any]] = {}
        for res_key, info in sorted(dict(raw_obs.get("leases", {})).items()):
            leases[str(res_key)] = {
                "holder": str(info["holder"]),
                "epoch": int(info.get("epoch", 1)),
            }

        quotas: dict[str, float] = {
            str(k): round(float(v), self._round_digits)
            for k, v in sorted(dict(raw_obs.get("resource_quotas", {})).items())
        }

        digests: dict[str, dict[str, Any]] = {}
        for rec_key, rec_info in sorted(dict(raw_obs.get("record_digests", {})).items()):
            if "digest" in rec_info:
                dig_str = str(rec_info["digest"])[: self._digest_chars]
            else:
                # Normalize semantic content and discard surface formatting / timestamps
                semantic = str(rec_info.get("semantic_payload", "")).strip()
                dig_str = hashlib.sha256(semantic.encode("utf-8")).hexdigest()[: self._digest_chars]
            digests[str(rec_key)] = {
                "version": int(rec_info.get("version", 0)),
                "digest": dig_str,
                "staged_digest": str(rec_info.get("staged_digest", dig_str))[: self._digest_chars],
            }

        taints = tuple(sorted({str(t) for t in raw_obs.get("capability_taints", [])}))
        explicit_inv = dict(raw_obs.get("invariant_predicates", {}))
        invariants = {
            "lease_fenced": bool(explicit_inv.get("lease_fenced", True)),
            "quota_non_negative": bool(
                explicit_inv.get("quota_non_negative", all(v >= 0.0 for v in quotas.values()))
            ),
            "taint_isolated": bool(explicit_inv.get("taint_isolated", True)),
            "cas_version_monotonic": bool(explicit_inv.get("cas_version_monotonic", True)),
        }
        latent = self._compute_latent_vector(leases, quotas, digests, taints, invariants)
        return FactoredWorldState(
            leases=leases,
            resource_quotas=quotas,
            record_digests=digests,
            capability_taints=taints,
            invariant_predicates=invariants,
            latent_vector=latent,
        )

    def predict_transition(
        self,
        state: FactoredWorldState,
        action: dict[str, Any],
    ) -> dict[str, Any]:
        """Predict post-action latent state s_hat_{t+1} = transition(s_t, a_t) and pre-execution risk energy."""
        op = str(action["op"])
        actor_id = str(action.get("actor_id", "worker-default"))
        target_key = str(action.get("target_key", ""))
        action_id = str(action.get("action_id", op))
        irreversible = bool(action.get("irreversible", op == "irreversible_effect"))

        next_leases = copy.deepcopy(state.leases)
        next_quotas = dict(state.resource_quotas)
        next_digests = copy.deepcopy(state.record_digests)
        taint_set = set(state.capability_taints)
        next_invariants = dict(state.invariant_predicates)

        # 1. Quota transition
        for q_name, delta in dict(action.get("quota_deltas", {})).items():
            cur_q = next_quotas.get(str(q_name), 1.0)
            next_quotas[str(q_name)] = round(cur_q + float(delta), self._round_digits)
        if any(val < 0.0 for val in next_quotas.values()):
            next_invariants["quota_non_negative"] = False

        # 2. Taint transition
        for added in action.get("adds_taints", []):
            taint_set.add(str(added))
        for cleared in action.get("clears_taints", []):
            taint_set.discard(str(cleared))
        if op == "sanitize_taints" and not action.get("clears_taints"):
            taint_set -= set(self._forbidden_taints)

        # 3. Lease & record state transitions
        if op == "acquire_lease":
            existing = next_leases.get(target_key)
            if existing is not None and existing["holder"] != actor_id:
                next_invariants["lease_fenced"] = False
            else:
                prev_epoch = int(existing["epoch"]) if existing is not None else 0
                next_leases[target_key] = {"holder": actor_id, "epoch": prev_epoch + 1}

        elif op == "release_lease":
            existing = next_leases.get(target_key)
            if existing is None or existing["holder"] != actor_id:
                next_invariants["lease_fenced"] = False
            else:
                next_leases.pop(target_key, None)

        elif op == "transform_record":
            rec = next_digests.get(
                target_key,
                {"version": 0, "digest": "0" * self._digest_chars, "staged_digest": "0" * self._digest_chars},
            )
            base_dig = str(rec.get("staged_digest", rec["digest"]))
            new_staged = hashlib.sha256(
                f"stage:{base_dig}:{action_id}".encode("utf-8")
            ).hexdigest()[: self._digest_chars]
            next_digests[target_key] = {
                "version": int(rec["version"]),
                "digest": str(rec["digest"]),
                "staged_digest": new_staged,
            }

        elif op in ("commit_cas_write", "irreversible_effect"):
            lease_info = next_leases.get(target_key)
            if lease_info is None or lease_info["holder"] != actor_id:
                next_invariants["lease_fenced"] = False

            if taint_set & self._forbidden_taints:
                next_invariants["taint_isolated"] = False

            rec = next_digests.get(
                target_key,
                {"version": 0, "digest": "0" * self._digest_chars, "staged_digest": "0" * self._digest_chars},
            )
            if "expected_version" in action and int(action["expected_version"]) != int(rec["version"]):
                next_invariants["cas_version_monotonic"] = False

            if all(next_invariants.values()):
                committed_dig = hashlib.sha256(
                    f"commit:{rec.get('staged_digest', rec['digest'])}:{action_id}".encode("utf-8")
                ).hexdigest()[: self._digest_chars]
                next_digests[target_key] = {
                    "version": int(rec["version"]) + 1,
                    "digest": committed_dig,
                    "staged_digest": committed_dig,
                }

        next_taints = tuple(sorted(taint_set))
        next_latent = self._compute_latent_vector(
            next_leases, next_quotas, next_digests, next_taints, next_invariants
        )
        predicted = FactoredWorldState(
            leases=next_leases,
            resource_quotas=next_quotas,
            record_digests=next_digests,
            capability_taints=next_taints,
            invariant_predicates=next_invariants,
            latent_vector=next_latent,
        )

        # Compute single-step risk energy
        low_quota_shortfall = sum(
            max(0.0, self._low_quota_floor - val) for val in next_quotas.values()
        )
        quota_consumed = sum(
            max(0.0, state.resource_quotas.get(k, 1.0) - v) for k, v in next_quotas.items()
        )
        broken_count = sum(1 for ok in next_invariants.values() if not ok)
        step_risk = (
            self._step_quota_weight * (quota_consumed + low_quota_shortfall)
            + self._step_taint_weight * float(len(next_taints))
            + (self._irreversible_exposure if irreversible else 0.0)
            + self._invariant_penalty * float(broken_count)
        )

        return {
            "predicted_state": predicted,
            "invariants_hold": predicted.all_invariants_hold(),
            "step_risk_energy": round(step_risk, self._round_digits),
        }
