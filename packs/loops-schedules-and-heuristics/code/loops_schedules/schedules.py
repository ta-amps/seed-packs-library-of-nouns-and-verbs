"""Declarative Schedule/Cadence compiler, Fragility Half-Life Urgency scheduler, and AIMD Claim Pacing."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from .grid import resolve_grid_cell


class DeclarativeScheduleAndCadenceCompiler:
    """Compiles inert Schedule Nouns (auto_enqueued=False) into idempotent windows, urgency ranks, and AIMD pacing."""

    def __init__(
        self,
        grid_overrides: dict[str, Any] | None = None,
        *,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.cell, self.constants = resolve_grid_cell(grid_overrides, regime=regime, spec=spec)

    def evaluate_schedule_window(
        self,
        schedule_noun: dict[str, Any],
        *,
        now_epoch_seconds: int,
        completed_idempotency_keys: set[str] | list[str] = (),
    ) -> dict[str, Any]:
        """Compile inert schedule noun into window-keyed idempotency_key with zero storage I/O outside due window."""
        if bool(schedule_noun.get("auto_enqueued", False)):
            raise ValueError("Schedule nouns must remain inert (auto_enqueued=False); never create a competing daemon")

        schedule_id = str(schedule_noun["schedule_id"])
        base_cadence = max(1, int(schedule_noun.get("cadence_seconds", self.cell["base_cadence_seconds"])))
        max_cadence = max(base_cadence, int(schedule_noun.get("max_cadence_seconds", self.cell["max_cadence_seconds"])))
        backoff_mult = max(1, int(schedule_noun.get("backoff_multiplier", self.cell["backoff_multiplier"])))
        low_yield_streak = max(0, int(schedule_noun.get("consecutive_low_yield_windows", 0)))

        effective_cadence = min(max_cadence, base_cadence * (backoff_mult ** low_yield_streak))
        now_sec = int(now_epoch_seconds)
        window_start = (now_sec // effective_cadence) * effective_cadence
        window_iso = datetime.fromtimestamp(window_start, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        idempotency_key = f"schedule:{schedule_id}:{window_iso}"

        slice_chars = int(self.constants["digest_slice_chars"])
        radix = int(self.constants["hex_radix"])
        jitter_cap = min(
            int(schedule_noun.get("max_jitter_seconds", self.cell["max_jitter_seconds"])),
            int(float(effective_cadence) * float(self.cell["max_jitter_fraction"])),
        )
        if jitter_cap <= 0:
            jitter_seconds = 0
        else:
            seed = f"{schedule_id}:{window_iso}".encode("utf-8")
            jitter_seconds = int(hashlib.sha256(seed).hexdigest()[:slice_chars], radix) % (jitter_cap + 1)

        due_width = max(1, int(schedule_noun.get("due_window_width_seconds", self.cell["due_window_width_seconds"])))
        due_start = window_start + jitter_seconds
        due_end = min(window_start + effective_cadence, due_start + due_width)

        stop_at_epoch = schedule_noun.get("stop_at_epoch_seconds")
        if stop_at_epoch is not None and now_sec >= int(stop_at_epoch):
            return {
                "schedule_id": schedule_id,
                "auto_enqueued": False,
                "due": False,
                "reason": "past_stop_at_deadline",
                "idempotency_key": idempotency_key,
                "window_iso": window_iso,
                "effective_cadence_seconds": effective_cadence,
                "jitter_seconds": jitter_seconds,
                "storage_io_ops": 0,
            }

        if now_sec < due_start or now_sec >= due_end:
            return {
                "schedule_id": schedule_id,
                "auto_enqueued": False,
                "due": False,
                "reason": "outside_due_window",
                "idempotency_key": idempotency_key,
                "window_iso": window_iso,
                "effective_cadence_seconds": effective_cadence,
                "jitter_seconds": jitter_seconds,
                "storage_io_ops": 0,
            }

        if idempotency_key in set(completed_idempotency_keys):
            return {
                "schedule_id": schedule_id,
                "auto_enqueued": False,
                "due": False,
                "reason": "window_already_completed",
                "idempotency_key": idempotency_key,
                "window_iso": window_iso,
                "effective_cadence_seconds": effective_cadence,
                "jitter_seconds": jitter_seconds,
                "storage_io_ops": 1,
            }

        return {
            "schedule_id": schedule_id,
            "auto_enqueued": False,
            "due": True,
            "reason": "within_active_due_window",
            "idempotency_key": idempotency_key,
            "window_iso": window_iso,
            "effective_cadence_seconds": effective_cadence,
            "jitter_seconds": jitter_seconds,
            "storage_io_ops": 1,
        }

    def render_systemd_user_units(self, schedule_noun: dict[str, Any]) -> dict[str, str]:
        """Render inert systemd --user .service and .timer text templates for owner-authorized local use."""
        unit_slug = str(schedule_noun["schedule_id"])
        cadence_sec = max(1, int(schedule_noun.get("cadence_seconds", self.cell["base_cadence_seconds"])))
        jitter_sec = max(0, int(schedule_noun.get("max_jitter_seconds", self.cell["max_jitter_seconds"])))
        exec_cmd = str(schedule_noun.get("exec_command", "/usr/bin/env python3 -m loops_schedules --check-due"))

        service_text = "\n".join(
            [
                "[Unit]",
                f"Description=Owner-authorized local worker check for {unit_slug}",
                "",
                "[Service]",
                "Type=oneshot",
                f"ExecStart={exec_cmd}",
                "",
            ]
        )
        timer_text = "\n".join(
            [
                "[Unit]",
                f"Description=Cadence timer for {unit_slug}",
                "",
                "[Timer]",
                f"OnUnitActiveSec={cadence_sec}s",
                f"RandomizedDelaySec={jitter_sec}s",
                "Persistent=true",
                "",
                "[Install]",
                "WantedBy=timers.target",
                "",
            ]
        )
        return {
            "service_name": f"{unit_slug}.service",
            "timer_name": f"{unit_slug}.timer",
            "service_unit": service_text,
            "timer_unit": timer_text,
        }

    def rank_fragility_urgency(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rank items by urgency = importance * (1 - 0.5 ** (age_hours / half_life_hours))."""
        round_d = int(self.constants["round_digits"])
        decay_base = float(self.constants["decay_base"])
        scored: list[dict[str, Any]] = []
        for item in items:
            age_h = max(0.0, float(item.get("age_hours", 0.0)))
            half_life_h = max(1.0, float(item.get("half_life_hours", 1.0)))
            importance = max(0.0, float(item.get("importance", 1.0)))
            freshness = decay_base ** (age_h / half_life_h)
            urgency = importance * (1.0 - freshness)
            scored.append(
                {
                    "item_id": str(item["item_id"]),
                    "freshness": round(freshness, round_d),
                    "urgency": round(urgency, round_d),
                }
            )
        scored.sort(key=lambda row: (-float(row["urgency"]), str(row["item_id"])))
        return scored

    def step_aimd_claim_pacing(
        self,
        *,
        current_concurrency: int,
        prev_ewma_latency_ms: float,
        observed_latency_ms: float,
        total_pool_slots: int,
        active_peer_workers: int,
        had_throttle_error: bool = False,
    ) -> dict[str, Any]:
        """AIMD claim concurrency controller with EWMA latency tracking and fair-share slot yield."""
        round_d = int(self.constants["round_digits"])
        alpha = float(self.cell["aimd_ewma_alpha"])
        target_ms = float(self.cell["aimd_target_latency_ms"])
        add_step = int(self.cell["aimd_add_step"])
        mult_factor = float(self.cell["aimd_mult_factor"])
        max_conc = int(self.cell["aimd_max_concurrency"])

        cur_conc = max(1, int(current_concurrency))
        ewma_ms = alpha * float(observed_latency_ms) + (1.0 - alpha) * float(prev_ewma_latency_ms)
        fair_share_cap = max(1, int(total_pool_slots) // max(1, int(active_peer_workers)))

        if had_throttle_error or ewma_ms > target_ms:
            raw_next = max(1, int(float(cur_conc) * mult_factor))
            action = "multiplicative_decrease"
        elif ewma_ms < target_ms:
            raw_next = min(max_conc, cur_conc + add_step)
            action = "additive_increase"
        else:
            raw_next = cur_conc
            action = "hold_steady"

        next_conc = min(raw_next, fair_share_cap, max_conc)
        fair_share_yielded = raw_next > fair_share_cap
        return {
            "next_concurrency": next_conc,
            "ewma_latency_ms": round(ewma_ms, round_d),
            "fair_share_cap": fair_share_cap,
            "fair_share_yielded": fair_share_yielded,
            "pacing_action": action,
        }
