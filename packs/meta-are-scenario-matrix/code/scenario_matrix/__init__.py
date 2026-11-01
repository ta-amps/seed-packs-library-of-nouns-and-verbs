"""1,000-Environment x 1,000-Method x 1,000-Persona x 1,000-Stakeholder scenario matrix."""

from .environments import (
    CONNECTIVITY_SENSITIVITY_REGIMES,
    DOMAINS_25,
    OPERATIONAL_CONSTRAINTS_10,
    generate_environment,
    generate_environments_1000,
)
from .matrix_runner import (
    ADDRESSABLE_TUPLES,
    expand_combinatorial_slice,
    resolve_tuple,
    resolve_tuple_by_global_index,
    run_latin_hypercube_sweep_1000,
    run_worked_example,
)
from .methods import (
    COMPUTE_TIERS_6,
    PRIVACY_BOUNDARIES_5,
    TOPOLOGIES_5,
    VERIFICATION_GATES_8,
    generate_method,
    generate_methods_1000,
)
from .personas import (
    COMMUNICATION_STYLES_5,
    HARNESSES_5,
    RISK_ACCESSIBILITY_PROFILES_8,
    SKILL_LEVELS_5,
    generate_persona,
    generate_personas_1000,
)
from .stakeholders import (
    STAKEHOLDER_POSITIONS_10,
    evaluate_and_digest_episode,
    generate_stakeholder,
    generate_stakeholders_1000,
)

__all__ = [
    "ADDRESSABLE_TUPLES",
    "COMMUNICATION_STYLES_5",
    "COMPUTE_TIERS_6",
    "CONNECTIVITY_SENSITIVITY_REGIMES",
    "DOMAINS_25",
    "HARNESSES_5",
    "OPERATIONAL_CONSTRAINTS_10",
    "PRIVACY_BOUNDARIES_5",
    "RISK_ACCESSIBILITY_PROFILES_8",
    "SKILL_LEVELS_5",
    "STAKEHOLDER_POSITIONS_10",
    "TOPOLOGIES_5",
    "VERIFICATION_GATES_8",
    "evaluate_and_digest_episode",
    "expand_combinatorial_slice",
    "generate_environment",
    "generate_environments_1000",
    "generate_method",
    "generate_methods_1000",
    "generate_persona",
    "generate_personas_1000",
    "generate_stakeholder",
    "generate_stakeholders_1000",
    "resolve_tuple",
    "resolve_tuple_by_global_index",
    "run_latin_hypercube_sweep_1000",
    "run_worked_example",
]
