"""Typed RFC 9457 error hierarchy for recipe validation, DAG compilation, and execution."""

from __future__ import annotations


class CodeCompositionError(Exception):
    """Base error mapped deterministically to an HTTP status and machine-readable code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        title: str,
        detail: str,
        diagnostics: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.title = title
        self.detail = detail
        self.diagnostics: list[dict[str, object]] = list(diagnostics or [])

    def to_problem(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "type": "about:blank",
            "title": self.title,
            "status": self.status_code,
            "detail": self.detail,
            "code": self.code,
        }
        if self.diagnostics:
            payload["diagnostics"] = self.diagnostics
        return payload


class NodeNotFoundError(CodeCompositionError):
    """Raised when a recipe references a node_id absent from the verified NodeDatabase."""

    def __init__(self, node_id: str, suggestion: str | None = None) -> None:
        hint = f" Did you mean node {suggestion!r}?" if suggestion else ""
        diag: list[dict[str, object]] = [{"node_id": node_id, "suggestion": suggestion}]
        super().__init__(
            404,
            "node_not_found",
            "Prewritten Node Not Found",
            f"Node {node_id!r} does not exist in the verified node database.{hint}",
            diagnostics=diag,
        )


class NodeVerificationError(CodeCompositionError):
    """Raised when a prewritten node fails SHA-256 integrity or self-test verification."""

    def __init__(self, node_id: str, reason: str) -> None:
        super().__init__(
            422,
            "node_verification_failed",
            "Prewritten Node Verification Failed",
            f"Prewritten node {node_id!r} failed verification: {reason}",
            diagnostics=[{"node_id": node_id, "reason": reason}],
        )


class NodeRevisionConflictError(CodeCompositionError):
    """Raised when an atomic CAS node registration or update fails expected_revision."""

    def __init__(
        self,
        node_id: str,
        *,
        expected_revision: int | None,
        actual_revision: int | None = None,
    ) -> None:
        super().__init__(
            409,
            "node_revision_conflict",
            "Prewritten Node Revision Conflict",
            (
                f"Atomic CAS revision conflict on node {node_id!r}: "
                f"expected revision {expected_revision!r}, actual revision {actual_revision!r}."
            ),
            diagnostics=[
                {
                    "node_id": node_id,
                    "expected_revision": expected_revision,
                    "actual_revision": actual_revision,
                }
            ],
        )


class NodeGovernanceError(CodeCompositionError):
    """Raised when the Layer-1 Governance Lens refuses an unverified, quarantined, or unlicensed node."""

    def __init__(
        self,
        node_id: str,
        reason: str,
        *,
        step_id: str | None = None,
        diagnostics: list[dict[str, object]] | None = None,
    ) -> None:
        diag = diagnostics or [
            {"node_id": node_id, "step_id": step_id, "reason": reason}
            if step_id is not None
            else {"node_id": node_id, "reason": reason}
        ]
        super().__init__(
            422,
            "node_governance_failed",
            "Layer-1 Node Governance Refused",
            f"Layer-1 Governance Lens refused node {node_id!r}: {reason}",
            diagnostics=diag,
        )


class RecipeValidationError(CodeCompositionError):
    """Raised when a declarative RecipeSpec violates structural or contract invariants."""

    def __init__(
        self,
        detail: str,
        *,
        code: str = "recipe_validation_failed",
        title: str = "Recipe Validation Failed",
        diagnostics: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(422, code, title, detail, diagnostics=diagnostics)


class PortNotFoundError(RecipeValidationError):
    """Raised when an edge references an unknown source or destination port."""

    def __init__(
        self,
        *,
        step_id: str,
        node_id: str,
        direction: str,
        port_name: str,
        available_ports: list[str],
        suggestion: str | None = None,
    ) -> None:
        hint = f" Did you mean port {suggestion!r}?" if suggestion else ""
        avail = ", ".join(repr(p) for p in available_ports) or "none"
        super().__init__(
            f"Step {step_id!r} ({node_id}) has no {direction} port {port_name!r} "
            f"(available {direction} ports: {avail}).{hint}",
            code="port_not_found",
            title="Recipe Port Not Found",
            diagnostics=[
                {
                    "step_id": step_id,
                    "node_id": node_id,
                    "direction": direction,
                    "port": port_name,
                    "available_ports": available_ports,
                    "suggestion": suggestion,
                }
            ],
        )


class PortTypeMismatchError(RecipeValidationError):
    """Raised when an edge connects incompatible static port types."""

    def __init__(
        self,
        *,
        src_step: str,
        src_port: str,
        src_type: str,
        dst_step: str,
        dst_port: str,
        dst_type: str,
    ) -> None:
        super().__init__(
            f"Static port type mismatch on edge {src_step}.{src_port} -> {dst_step}.{dst_port}: "
            f"output type {src_type!r} is incompatible with required input type {dst_type!r}.",
            code="port_type_mismatch",
            title="Static Port Type Mismatch",
            diagnostics=[
                {
                    "src_step": src_step,
                    "src_port": src_port,
                    "src_type": src_type,
                    "dst_step": dst_step,
                    "dst_port": dst_port,
                    "dst_type": dst_type,
                }
            ],
        )


class CycleDetectedError(RecipeValidationError):
    """Raised when recipe edges form a directed cycle instead of a valid DAG."""

    def __init__(self, cycle_path: list[str]) -> None:
        self.cycle_path = list(cycle_path)
        formatted = " -> ".join(cycle_path)
        super().__init__(
            f"Recipe graph contains a cycle and is not a DAG: {formatted}",
            code="cycle_detected",
            title="Cycle Detected in Recipe Graph",
            diagnostics=[{"cycle_path": self.cycle_path}],
        )


class ParameterConstraintError(RecipeValidationError):
    """Raised when a step parameter violates declared type, range, or choice bounds."""

    def __init__(
        self,
        *,
        step_id: str,
        node_id: str,
        param_name: str,
        reason: str,
        suggestion: str | None = None,
    ) -> None:
        hint = f" Did you mean parameter {suggestion!r}?" if suggestion else ""
        super().__init__(
            f"Invalid parameter {param_name!r} on step {step_id!r} ({node_id}): {reason}.{hint}",
            code="parameter_constraint_failed",
            title="Parameter Constraint Failed",
            diagnostics=[
                {
                    "step_id": step_id,
                    "node_id": node_id,
                    "param": param_name,
                    "reason": reason,
                    "suggestion": suggestion,
                }
            ],
        )


class ContributorTierRefusedError(CodeCompositionError):
    """Raised when an LLM composer call targets a '-contributor' training-tier model."""

    def __init__(self, model: str) -> None:
        super().__init__(
            403,
            "contributor_tier_refused",
            "Contributor-Tier Model Refused",
            f"Recipe composition runs in Standard mode only and refuses contributor-tier model {model!r}.",
            diagnostics=[{"model": model}],
        )


class ExecutionInputError(CodeCompositionError):
    """Raised when runtime entry inputs do not satisfy the compiled DAG entry contract."""

    def __init__(self, detail: str, *, diagnostics: list[dict[str, object]] | None = None) -> None:
        super().__init__(
            422,
            "execution_input_invalid",
            "DAG Execution Input Invalid",
            detail,
            diagnostics=diagnostics,
        )


class ComposerError(CodeCompositionError):
    """Raised when natural-language recipe composition fails or returns invalid JSON."""

    def __init__(
        self,
        detail: str,
        *,
        status_code: int = 422,
        diagnostics: list[dict[str, object]] | None = None,
    ) -> None:
        super().__init__(
            status_code,
            "composer_failed",
            "Recipe Composition Failed",
            detail,
            diagnostics=diagnostics,
        )


class RecipeCatalogError(CodeCompositionError):
    """Raised when the authored recipe catalog is missing or empty instead of substituting one."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            500,
            "recipe_catalog_unavailable",
            "Recipe Catalog Unavailable",
            detail,
        )


class NodeDatabaseAccessError(CodeCompositionError):
    """Raised when an existing node database cannot be opened without creating or changing it."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            409,
            "node_database_unavailable",
            "Node Database Unavailable",
            detail,
        )


class SeedPackError(CodeCompositionError, ValueError):
    """Raised when a seed pack cannot be exported with complete, checked contents."""

    def __init__(self, detail: str, *, code: str = "seed_pack_refused") -> None:
        super().__init__(422, code, "Seed Pack Export Refused", detail)


class SeedVerificationError(CodeCompositionError):
    """Raised by a worker when pinned seed inputs differ from the local verified installation."""

    def __init__(self, detail: str, *, code: str = "seed_verification_failed") -> None:
        super().__init__(409, code, "Seed Verification Failed", detail)


def ensure_standard_model(model: str) -> str:
    """Refuse contributor-tier ('*-contributor') model identifiers deterministically."""
    cleaned = model.strip()
    lowered = cleaned.lower()
    if lowered.endswith("-contributor") or "-contributor-" in lowered or lowered == "contributor":
        raise ContributorTierRefusedError(cleaned)
    return cleaned
