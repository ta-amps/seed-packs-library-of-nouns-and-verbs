"""Deterministic model and license tier firewall routing payloads across privacy/training tiers."""

from __future__ import annotations

from typing import Any

from .grid import resolve_grid_cell


class ModelLicenseTierFirewall:
    """Routes payloads across contributor_training_allowed, standard_zero_retention and local_open_weights."""

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
        self.tiers: list[str] = list(self.constants["license_tiers"])
        self.permissive_licenses: set[str] = set(self.constants["permissive_training_licenses"])
        self.zero_ret_licenses: set[str] = set(self.constants["zero_retention_allowed_licenses"])
        self.local_only_licenses: set[str] = set(self.constants["local_only_licenses"])
        self.sensitivities: set[str] = set(self.constants["sensitivity_levels"])
        self.allow_vaulted_conf: bool = bool(self.cell["allow_vaulted_confidential_zero_retention"])
        self.firewall_mode: str = str(self.cell["firewall_mode"])

    def route_payload(self, descriptor: dict[str, Any]) -> dict[str, Any]:
        """Classify permitted tiers and evaluate optional requested_tier."""
        sensitivity = str(descriptor.get("sensitivity", "unknown")).strip()
        license_tag = str(descriptor.get("license_tag", "unknown")).strip()
        synthetic_provenance = bool(descriptor.get("synthetic_provenance", False))
        placeholder_vaulted = bool(descriptor.get("placeholder_vaulted", False))
        has_raw_sensitive = bool(descriptor.get("contains_unredacted_entities", False))
        requested_tier = descriptor.get("requested_tier")

        reasons: list[str] = []
        if sensitivity not in self.sensitivities:
            reasons.append(f"unknown_sensitivity:{sensitivity}")
            return {
                "decision": "refuse",
                "recommended_tier": "local_open_weights",
                "permitted_tiers": [],
                "reasons": reasons,
            }

        if license_tag in self.local_only_licenses:
            reasons.append(f"license_requires_local_weights:{license_tag}")
            permitted = ["local_open_weights"]
        elif sensitivity == "secret" or has_raw_sensitive:
            if sensitivity == "secret":
                reasons.append("secret_sensitivity_requires_local_weights")
            if has_raw_sensitive:
                reasons.append("unredacted_entities_require_local_or_vaulting")
            permitted = ["local_open_weights"]
        elif sensitivity == "confidential":
            if placeholder_vaulted and self.allow_vaulted_conf and license_tag in self.zero_ret_licenses:
                reasons.append("vaulted_confidential_eligible_for_zero_retention")
                permitted = ["standard_zero_retention", "local_open_weights"]
            else:
                reasons.append("confidential_payload_restricted_to_local_weights")
                permitted = ["local_open_weights"]
        elif sensitivity == "internal":
            if license_tag in self.zero_ret_licenses:
                reasons.append("internal_payload_requires_zero_retention_or_local")
                permitted = ["standard_zero_retention", "local_open_weights"]
            else:
                reasons.append(f"unrecognized_license_defaults_local:{license_tag}")
                permitted = ["local_open_weights"]
        else:
            # public sensitivity
            if license_tag in self.permissive_licenses and (
                synthetic_provenance or bool(descriptor.get("public_redistribution_cleared", True))
            ):
                reasons.append("public_permissive_eligible_for_contributor_training")
                permitted = [
                    "contributor_training_allowed",
                    "standard_zero_retention",
                    "local_open_weights",
                ]
            elif license_tag in self.zero_ret_licenses:
                reasons.append("public_attribution_license_blocks_training_allows_zero_retention")
                permitted = ["standard_zero_retention", "local_open_weights"]
            else:
                reasons.append(f"restrictive_or_unknown_license_routes_local:{license_tag}")
                permitted = ["local_open_weights"]

        recommended = permitted[0]
        if requested_tier is None:
            return {
                "decision": "allow",
                "recommended_tier": recommended,
                "permitted_tiers": permitted,
                "reasons": reasons,
            }

        req_str = str(requested_tier)
        if req_str in permitted:
            return {
                "decision": "allow",
                "recommended_tier": req_str,
                "permitted_tiers": permitted,
                "reasons": reasons,
            }

        reasons.append(f"requested_tier_not_permitted:{req_str}")
        if self.firewall_mode == "reroute_to_safe_tier":
            return {
                "decision": "reroute",
                "recommended_tier": recommended,
                "permitted_tiers": permitted,
                "reasons": reasons,
            }
        return {
            "decision": "refuse",
            "recommended_tier": recommended,
            "permitted_tiers": permitted,
            "reasons": reasons,
        }
