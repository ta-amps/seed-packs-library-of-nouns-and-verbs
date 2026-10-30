"""SQLite-backed prewritten node database, self-test verifier, and sub-DAG memoization cache."""

from __future__ import annotations

import copy
import difflib
import json
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from code_composition.errors import (
    NodeDatabaseAccessError,
    NodeNotFoundError,
    NodeRevisionConflictError,
    NodeVerificationError,
)
from code_composition.schemas import (
    ExecutionReceipt,
    PortSpec,
    PrewrittenNode,
    canonical_json,
    compute_code_sha256,
    port_value_matches,
    sha256_hex,
)
from code_composition.seed_nodes import build_seed_nodes

NodeCallable = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
_NODE_COLUMNS = frozenset(
    {"node_id", "code_sha256", "spdx_license", "governance_tags_json", "revision", "body_json"}
)


def load_node_callable(node: PrewrittenNode) -> NodeCallable:
    """Verify source integrity and load trusted code in-process, not in a security sandbox."""
    actual_sha = compute_code_sha256(node.source_code)
    if actual_sha != node.code_sha256:
        raise NodeVerificationError(
            node.node_id,
            f"code_sha256 mismatch: stored {node.code_sha256}, computed {actual_sha}.",
        )
    namespace: dict[str, Any] = {"Any": Any}
    try:
        compiled = compile(node.source_code, f"<node:{node.node_id}>", "exec")
        exec(compiled, namespace)
    except Exception as exc:
        raise NodeVerificationError(node.node_id, f"Syntax or load failure: {exc}") from exc

    fn = namespace.get(node.function_name)
    if not callable(fn):
        raise NodeVerificationError(
            node.node_id,
            f"Function {node.function_name!r} was not defined by source_code.",
        )
    typed_fn: NodeCallable = fn
    return typed_fn


def verify_node_outputs(node_id: str, ports: list[PortSpec], values: Any, *, context: str) -> None:
    """Require every declared output and its value type before trusting a result."""
    if not isinstance(values, dict):
        raise NodeVerificationError(node_id, f"{context}: expected output object.")
    for port in ports:
        if port.name not in values:
            raise NodeVerificationError(
                node_id, f"{context}: omitted declared output {port.name!r}."
            )
        if not port_value_matches(port.port_type, values[port.name]):
            raise NodeVerificationError(
                node_id, f"{context}.{port.name}: expected PortType {port.port_type!r}."
            )


def run_node_self_test_case(
    node: PrewrittenNode, fn: NodeCallable, index: int, case: dict[str, Any]
) -> Any:
    """Run one built-in test case with fresh copies of its inputs and merged default params."""
    case_name = str(case.get("name", f"case_{index}"))
    default_params = {p.name: p.default for p in node.params if p.default is not None}
    raw_inputs = copy.deepcopy(dict(case.get("inputs", {})))
    merged_params = {**default_params, **copy.deepcopy(dict(case.get("params", {})))}
    try:
        return fn(raw_inputs, merged_params)
    except Exception as exc:
        raise NodeVerificationError(
            node.node_id, f"Self-test {case_name!r} raised {type(exc).__name__}: {exc}"
        ) from exc


def verify_node_self_tests(node: PrewrittenNode) -> int:
    """Execute a prewritten node's built-in test_cases and check declared port contracts."""
    if not node.test_cases:
        raise NodeVerificationError(
            node.node_id, "At least one deterministic test_case is required to register a node."
        )
    fn = load_node_callable(node)

    passed = 0
    for index, case in enumerate(node.test_cases):
        case_name = str(case.get("name", f"case_{index}"))
        result = run_node_self_test_case(node, fn, index, case)

        verify_node_outputs(node.node_id, node.outputs, result, context=f"Self-test {case_name!r}")
        for req_port in case.get("expected_ports", []):
            if req_port not in result:
                raise NodeVerificationError(
                    node.node_id,
                    f"Self-test {case_name!r} missing expected port {req_port!r}.",
                )
        expected = case.get("expected")
        if isinstance(expected, dict):
            for key, exp_val in expected.items():
                if result.get(key) != exp_val:
                    raise NodeVerificationError(
                        node.node_id,
                        f"Self-test {case_name!r} port {key!r} mismatch: "
                        f"expected {exp_val!r}, got {result.get(key)!r}.",
                    )
        passed += 1
    return passed


class NodeDatabase:
    """SQLite registry of verified prewritten Python nodes and Merkle sub-DAG cache."""

    def __init__(self, db_path: str | Path = ":memory:", *, auto_seed: bool = True) -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        if auto_seed:
            self.seed_defaults()

    @classmethod
    def open_existing_read_only(cls, db_path: str | Path) -> NodeDatabase:
        """Open an existing node database for reads only.

        Never creates folders or files, migrates the schema, seeds defaults or executes stored
        code. SQLite's `immutable` mode also avoids creating `-wal`/`-shm` side files, so a
        database with uncheckpointed writes is refused instead of read partially.
        """
        path = Path(db_path).expanduser()
        if not path.is_file():
            raise NodeDatabaseAccessError(
                f"No node database exists at {str(db_path)!r}; nothing was created. "
                "Create one explicitly with `code-composition init --db PATH`."
            )
        for suffix in ("-wal", "-journal"):
            side = path.with_name(path.name + suffix)
            if side.exists() and side.stat().st_size > 0:
                raise NodeDatabaseAccessError(
                    f"{path.name} has uncheckpointed writes ({side.name}); stop the process "
                    "using it and retry. Nothing was read or changed."
                )
        conn = sqlite3.connect(
            path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True, check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        try:
            columns = {str(r["name"]) for r in conn.execute("PRAGMA table_info(nodes)")}
        except sqlite3.DatabaseError as exc:
            conn.close()
            raise NodeDatabaseAccessError(
                f"{path.name} is not a readable node database: {exc}"
            ) from exc
        missing = sorted(_NODE_COLUMNS - columns)
        if missing:
            conn.close()
            raise NodeDatabaseAccessError(
                f"{path.name} lacks node columns {missing}; migrate it explicitly with "
                "`code-composition init --db PATH` before exporting."
            )
        db = cls.__new__(cls)
        db.db_path = str(path)
        db._conn = conn
        return db

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                category TEXT NOT NULL,
                code_sha256 TEXT NOT NULL,
                spdx_license TEXT NOT NULL DEFAULT 'MIT',
                governance_tags_json TEXT NOT NULL DEFAULT '["status:verified"]',
                revision INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
                verified INTEGER NOT NULL CHECK (verified = 1),
                body_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS subgraph_cache (
                subgraph_fingerprint TEXT NOT NULL,
                input_sha256 TEXT NOT NULL,
                node_id TEXT NOT NULL,
                output_sha256 TEXT NOT NULL,
                outputs_json TEXT NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                PRIMARY KEY (subgraph_fingerprint, input_sha256)
            );

            CREATE TABLE IF NOT EXISTS execution_receipts (
                receipt_id TEXT PRIMARY KEY,
                recipe_id TEXT NOT NULL,
                receipt_sha256 TEXT NOT NULL,
                body_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        col_rows = self._conn.execute("PRAGMA table_info(nodes)").fetchall()
        existing_cols = {str(r["name"]) for r in col_rows}
        if "spdx_license" not in existing_cols:
            self._conn.execute(
                "ALTER TABLE nodes ADD COLUMN spdx_license TEXT NOT NULL DEFAULT 'MIT'"
            )
        if "governance_tags_json" not in existing_cols:
            self._conn.execute(
                """ALTER TABLE nodes ADD COLUMN governance_tags_json TEXT NOT NULL DEFAULT '["status:verified"]'"""
            )
        if "revision" not in existing_cols:
            self._conn.execute("ALTER TABLE nodes ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def register_node(
        self,
        node: PrewrittenNode,
        *,
        expected_revision: int | None = None,
    ) -> PrewrittenNode:
        """Verify SHA-256 and self-tests, then atomically register or CAS-update a prewritten node."""
        if expected_revision is not None and expected_revision < 0:
            raise NodeRevisionConflictError(
                node.node_id,
                expected_revision=expected_revision,
                actual_revision=None,
            )
        verify_node_self_tests(node)
        now = time.time()
        tags_json = canonical_json(list(node.governance_tags))

        if expected_revision is None or expected_revision == 0:
            stored_node = node.model_copy(update={"revision": 1})
            body_json = canonical_json(stored_node.model_dump(mode="json"))
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO nodes (
                    node_id, version, category, code_sha256, spdx_license,
                    governance_tags_json, revision, verified, body_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
                """,
                (
                    stored_node.node_id,
                    stored_node.version,
                    stored_node.category,
                    stored_node.code_sha256,
                    stored_node.spdx_license,
                    tags_json,
                    body_json,
                    now,
                ),
            )
            if cur.rowcount == 1:
                self._conn.commit()
                return stored_node

            existing_row = self._conn.execute(
                """
                SELECT code_sha256, spdx_license, governance_tags_json, revision
                FROM nodes
                WHERE node_id = ?
                """,
                (node.node_id,),
            ).fetchone()
            actual_rev = int(existing_row["revision"]) if existing_row is not None else None
            if (
                expected_revision is None
                and existing_row is not None
                and str(existing_row["code_sha256"]) == node.code_sha256
                and str(existing_row["spdx_license"]) == node.spdx_license
                and str(existing_row["governance_tags_json"]) == tags_json
            ):
                self._conn.rollback()
                return self.get_node(node.node_id)
            self._conn.rollback()
            raise NodeRevisionConflictError(
                node.node_id,
                expected_revision=expected_revision if expected_revision is not None else 0,
                actual_revision=actual_rev,
            )

        next_revision = expected_revision + 1
        stored_node = node.model_copy(update={"revision": next_revision})
        body_json = canonical_json(stored_node.model_dump(mode="json"))
        cur = self._conn.execute(
            """
            UPDATE nodes
            SET version = ?,
                category = ?,
                code_sha256 = ?,
                spdx_license = ?,
                governance_tags_json = ?,
                revision = revision + 1,
                verified = 1,
                body_json = ?,
                updated_at = ?
            WHERE node_id = ? AND revision = ?
            """,
            (
                stored_node.version,
                stored_node.category,
                stored_node.code_sha256,
                stored_node.spdx_license,
                tags_json,
                body_json,
                now,
                stored_node.node_id,
                expected_revision,
            ),
        )
        if cur.rowcount != 1:
            existing_row = self._conn.execute(
                "SELECT revision FROM nodes WHERE node_id = ?",
                (node.node_id,),
            ).fetchone()
            actual_rev = int(existing_row["revision"]) if existing_row is not None else None
            self._conn.rollback()
            raise NodeRevisionConflictError(
                node.node_id,
                expected_revision=expected_revision,
                actual_revision=actual_rev,
            )
        self._conn.commit()
        return stored_node

    def seed_defaults(self) -> int:
        """Ensure all 18 default prewritten verified nodes exist in SQLite."""
        existing_rows = self._conn.execute("SELECT node_id, code_sha256 FROM nodes").fetchall()
        existing = {str(r["node_id"]): str(r["code_sha256"]) for r in existing_rows}
        for node in build_seed_nodes():
            if node.node_id not in existing or existing.get(node.node_id) == node.code_sha256:
                self.register_node(node, expected_revision=None)
        row = self._conn.execute("SELECT COUNT(*) AS n FROM nodes").fetchone()
        return int(row["n"]) if row is not None else 0

    def list_node_ids(self) -> list[str]:
        """Return sorted node IDs registered in the database."""
        rows = self._conn.execute("SELECT node_id FROM nodes ORDER BY node_id ASC").fetchall()
        return [str(r["node_id"]) for r in rows]

    @staticmethod
    def _hydrate_node_row(node_id: str, row: sqlite3.Row) -> PrewrittenNode:
        try:
            payload = json.loads(str(row["body_json"]))
            if not isinstance(payload, dict):
                raise ValueError("Stored node body_json must decode to an object.")
            payload["spdx_license"] = str(row["spdx_license"])
            raw_tags = json.loads(str(row["governance_tags_json"]))
            if isinstance(raw_tags, list):
                payload["governance_tags"] = [str(t) for t in raw_tags]
            payload["revision"] = int(row["revision"])
            node = PrewrittenNode.model_validate(payload)
        except ValueError as exc:
            raise NodeVerificationError(node_id, str(exc)) from exc
        if node.code_sha256 != str(row["code_sha256"]):
            raise NodeVerificationError(
                node_id,
                f"Stored row digest {row['code_sha256']} disagrees with verified body digest {node.code_sha256}.",
            )
        return node

    def get_node(self, node_id: str) -> PrewrittenNode:
        """Fetch one verified PrewrittenNode or raise NodeNotFoundError with suggestion."""
        row = self._conn.execute(
            """
            SELECT code_sha256, spdx_license, governance_tags_json, revision, body_json
            FROM nodes
            WHERE node_id = ?
            """,
            (node_id,),
        ).fetchone()
        if row is None:
            candidates = self.list_node_ids()
            matches = difflib.get_close_matches(node_id, candidates, n=1, cutoff=0.45)
            raise NodeNotFoundError(node_id, suggestion=matches[0] if matches else None)
        return self._hydrate_node_row(node_id, row)

    def list_nodes(self, category: str | None = None) -> list[PrewrittenNode]:
        """Return all verified nodes sorted deterministically by node_id."""
        if category:
            rows = self._conn.execute(
                """
                SELECT node_id, code_sha256, spdx_license, governance_tags_json, revision, body_json
                FROM nodes
                WHERE category = ?
                ORDER BY node_id ASC
                """,
                (category,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT node_id, code_sha256, spdx_license, governance_tags_json, revision, body_json
                FROM nodes
                ORDER BY node_id ASC
                """
            ).fetchall()
        return [self._hydrate_node_row(str(r["node_id"]), r) for r in rows]

    def verify_all(self) -> dict[str, dict[str, Any]]:
        """Re-run SHA-256 checks and test_cases across every node in SQLite."""
        report: dict[str, dict[str, Any]] = {}
        for node in self.list_nodes():
            passed = verify_node_self_tests(node)
            report[node.node_id] = {
                "version": node.version,
                "code_sha256": node.code_sha256,
                "tests_passed": passed,
            }
        return report

    def catalog_signature_prompt(self, category: str | None = None) -> str:
        """Render the compact typed node signature catalog exposed to an LLM composer."""
        nodes = self.list_nodes(category=category)
        lines = [
            "# Verified Node Signatures (emit RecipeSpec JSON; never emit raw Python code)",
            "# PortTypes: records | table | series | text | json | metrics | artifact",
            "",
        ]
        for node in nodes:
            lines.append(f"- {node.signature_line()}")
        return "\n".join(lines)

    def catalog_token_stats(self) -> dict[str, int]:
        """Estimate token footprint of compact signatures vs. raw verified Python source."""
        nodes = self.list_nodes()
        sig_chars = len(self.catalog_signature_prompt())
        code_chars = sum(len(n.source_code) for n in nodes)
        return {
            "node_count": len(nodes),
            "signature_chars": sig_chars,
            "signature_tokens_est": max(1, round(sig_chars / 4)),
            "raw_code_chars": code_chars,
            "raw_code_tokens_est": max(1, round(code_chars / 4)),
        }

    def get_cached_subgraph(
        self, subgraph_fingerprint: str, input_sha256: str
    ) -> dict[str, Any] | None:
        """Look up memoized step outputs by (subgraph_fingerprint, input_sha256)."""
        row = self._conn.execute(
            """
            SELECT outputs_json, output_sha256
            FROM subgraph_cache
            WHERE subgraph_fingerprint = ? AND input_sha256 = ?
            """,
            (subgraph_fingerprint, input_sha256),
        ).fetchone()
        if row is None:
            return None
        outputs_json = str(row["outputs_json"])
        if sha256_hex(outputs_json) != str(row["output_sha256"]):
            return None
        self._conn.execute(
            """
            UPDATE subgraph_cache
            SET hit_count = hit_count + 1
            WHERE subgraph_fingerprint = ? AND input_sha256 = ?
            """,
            (subgraph_fingerprint, input_sha256),
        )
        self._conn.commit()
        loaded: dict[str, Any] = json.loads(outputs_json)
        return loaded

    def put_cached_subgraph(
        self,
        subgraph_fingerprint: str,
        input_sha256: str,
        node_id: str,
        outputs: dict[str, Any],
    ) -> str:
        """Persist deterministic step outputs under (subgraph_fingerprint, input_sha256)."""
        node = self.get_node(node_id)
        verify_node_outputs(node_id, node.outputs, outputs, context="Cache write")
        outputs_json = canonical_json(outputs)
        output_sha = sha256_hex(outputs_json)
        self._conn.execute(
            """
            INSERT INTO subgraph_cache (
                subgraph_fingerprint, input_sha256, node_id, output_sha256, outputs_json, hit_count, created_at
            )
            VALUES (?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(subgraph_fingerprint, input_sha256) DO NOTHING
            """,
            (subgraph_fingerprint, input_sha256, node_id, output_sha, outputs_json, time.time()),
        )
        self._conn.commit()
        return output_sha

    def cache_stats(self) -> dict[str, int]:
        """Return total cached sub-DAG entries and cumulative warm hits."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS entries, COALESCE(SUM(hit_count), 0) AS hits FROM subgraph_cache"
        ).fetchone()
        if row is None:
            return {"entries": 0, "hits": 0}
        return {"entries": int(row["entries"]), "hits": int(row["hits"])}

    def record_receipt(self, receipt: ExecutionReceipt) -> None:
        """Store a canonical SHA-256 ExecutionReceipt idempotently without destructive replace."""
        body_json = canonical_json(receipt.model_dump(mode="json"))
        self._conn.execute(
            """
            INSERT OR IGNORE INTO execution_receipts (
                receipt_id, recipe_id, receipt_sha256, body_json, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (receipt.receipt_id, receipt.recipe_id, receipt.receipt_sha256, body_json, time.time()),
        )
        self._conn.commit()

    def list_receipts(self, limit: int = 50) -> list[ExecutionReceipt]:
        """Return stored ExecutionReceipts ordered newest first."""
        rows = self._conn.execute(
            "SELECT body_json FROM execution_receipts ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [ExecutionReceipt.model_validate(json.loads(str(r["body_json"]))) for r in rows]
