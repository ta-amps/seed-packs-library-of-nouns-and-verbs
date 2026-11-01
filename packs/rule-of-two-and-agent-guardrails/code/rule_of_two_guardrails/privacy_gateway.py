"""Bidirectional deterministic privacy placeholder vault and round-trip evaluation harness."""

from __future__ import annotations

import re
from typing import Any

from .grid import resolve_grid_cell

PLACEHOLDER_TOKEN_RE = re.compile(r"<([A-Z][A-Z0-9_]+)_(\d+)>")
HEX_DIGEST_RE = re.compile(r"^[0-9a-fA-F]+$")


class BidirectionalPrivacyPlaceholderGateway:
    """Vaults sensitive entities into <ENTITY_TYPE_001> outbound and re-hydrates inbound losslessly."""

    def __init__(
        self,
        *,
        overrides: dict[str, Any] | None = None,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> None:
        self.grid, self.cell, self.constants = resolve_grid_cell(
            overrides, regime=regime, spec=spec
        )
        self.pad_width: int = int(self.cell["placeholder_index_width"])
        self.hex_min_chars: int = int(self.constants["hex_digest_min_chars"])
        self.hex_max_chars: int = int(self.constants["hex_digest_max_chars"])
        self.round_digits: int = int(self.constants["round_digits"])
        self.compiled_rules: list[tuple[str, re.Pattern[str]]] = [
            (str(entry["entity_type"]), re.compile(str(entry["pattern"])))
            for entry in self.constants["entity_patterns"]
        ]
        self._raw_to_placeholder: dict[tuple[str, str], str] = {}
        self._placeholder_to_raw: dict[str, str] = {}
        self._type_counters: dict[str, int] = {}

    @property
    def vault_size(self) -> int:
        return len(self._placeholder_to_raw)

    def _is_preserved_hex_digest(self, candidate: str) -> bool:
        return (
            self.hex_min_chars <= len(candidate) <= self.hex_max_chars
            and HEX_DIGEST_RE.fullmatch(candidate) is not None
        )

    def register_entity(self, entity_type: str, raw_value: str) -> str:
        clean_type = re.sub(r"[^A-Z0-9_]", "_", entity_type.strip().upper())
        key = (clean_type, raw_value)
        if key in self._raw_to_placeholder:
            return self._raw_to_placeholder[key]
        next_idx = self._type_counters.get(clean_type, 0) + 1
        self._type_counters[clean_type] = next_idx
        placeholder = f"<{clean_type}_{next_idx:0{self.pad_width}d}>"
        self._raw_to_placeholder[key] = placeholder
        self._placeholder_to_raw[placeholder] = raw_value
        return placeholder

    def scrub_text(
        self,
        text: str,
        *,
        explicit_entities: dict[str, list[str]] | None = None,
    ) -> str:
        out = text
        if explicit_entities:
            for etype in sorted(explicit_entities):
                for raw_val in sorted(explicit_entities[etype], key=len, reverse=True):
                    if raw_val and not self._is_preserved_hex_digest(raw_val) and raw_val in out:
                        token = self.register_entity(etype, raw_val)
                        out = out.replace(raw_val, token)
        for etype, pattern in self.compiled_rules:
            def _repl(match: re.Match[str], bound_type: str = etype) -> str:
                matched = match.group(0)
                if self._is_preserved_hex_digest(matched):
                    return matched
                return self.register_entity(bound_type, matched)

            out = pattern.sub(_repl, out)
        return out

    def scrub_payload(
        self,
        payload: Any,
        *,
        explicit_entities: dict[str, list[str]] | None = None,
    ) -> Any:
        if isinstance(payload, str):
            return self.scrub_text(payload, explicit_entities=explicit_entities)
        if isinstance(payload, list):
            return [self.scrub_payload(item, explicit_entities=explicit_entities) for item in payload]
        if isinstance(payload, dict):
            return {
                k: self.scrub_payload(v, explicit_entities=explicit_entities)
                for k, v in payload.items()
            }
        return payload

    def rehydrate_text(self, text: str) -> tuple[str, list[str]]:
        unresolved: list[str] = []

        def _restore(match: re.Match[str]) -> str:
            token = match.group(0)
            if token in self._placeholder_to_raw:
                return self._placeholder_to_raw[token]
            unresolved.append(token)
            return token

        restored = PLACEHOLDER_TOKEN_RE.sub(_restore, text)
        return restored, unresolved

    def rehydrate_payload(self, payload: Any) -> tuple[Any, list[str]]:
        if isinstance(payload, str):
            return self.rehydrate_text(payload)
        if isinstance(payload, list):
            items: list[Any] = []
            missing: list[str] = []
            for item in payload:
                restored_item, unresolved_item = self.rehydrate_payload(item)
                items.append(restored_item)
                missing.extend(unresolved_item)
            return items, missing
        if isinstance(payload, dict):
            out_dict: dict[str, Any] = {}
            missing_all: list[str] = []
            for key, val in payload.items():
                restored_val, unresolved_val = self.rehydrate_payload(val)
                out_dict[key] = restored_val
                missing_all.extend(unresolved_val)
            return out_dict, missing_all
        return payload, []

    @classmethod
    def evaluate_bidirectional(
        cls,
        cases: list[dict[str, Any]],
        *,
        overrides: dict[str, Any] | None = None,
        regime: str | None = None,
        spec: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Measure outbound zero-leak recall and inbound exact round-trip fidelity across test cases."""
        total_entities = 0
        scrubbed_entities = 0
        residual_leaks = 0
        exact_round_trips = 0
        coreference_preserved = 0
        coreference_cases = 0

        for case in cases:
            gateway = cls(overrides=overrides, regime=regime, spec=spec)
            raw_text = str(case["text"])
            explicit = case.get("explicit_entities")
            sensitive_values = [str(s) for s in case.get("ground_truth_sensitive", [])]

            scrubbed = gateway.scrub_text(raw_text, explicit_entities=explicit)
            for secret_val in sensitive_values:
                total_entities += 1
                if secret_val not in scrubbed:
                    scrubbed_entities += 1
                else:
                    residual_leaks += 1

            if case.get("expect_coreference_symbol"):
                coreference_cases += 1
                target_val = str(case["expect_coreference_symbol"])
                occurrences_raw = raw_text.count(target_val)
                assigned = [
                    tok for (_, rval), tok in gateway._raw_to_placeholder.items() if rval == target_val
                ]
                if assigned and scrubbed.count(assigned[0]) == occurrences_raw:
                    coreference_preserved += 1

            rehydrated, unresolved = gateway.rehydrate_text(scrubbed)
            if rehydrated == raw_text and not unresolved:
                exact_round_trips += 1

        sample_count = len(cases)
        digits = int(cls(overrides=overrides, regime=regime, spec=spec).round_digits)
        outbound_recall = (
            round(scrubbed_entities / total_entities, digits) if total_entities > 0 else 1.0
        )
        inbound_fidelity = (
            round(exact_round_trips / sample_count, digits) if sample_count > 0 else 1.0
        )
        coref_rate = (
            round(coreference_preserved / coreference_cases, digits) if coreference_cases > 0 else 1.0
        )
        return {
            "case_count": sample_count,
            "total_sensitive_entities": total_entities,
            "residual_leak_count": residual_leaks,
            "outbound_zero_leak_recall": outbound_recall,
            "inbound_round_trip_fidelity": inbound_fidelity,
            "coreference_preserved_rate": coref_rate,
        }
