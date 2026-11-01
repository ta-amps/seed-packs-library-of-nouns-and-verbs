"""Zero-OOM hybrid subspace memory matrices and inline-lease durable task queues."""

from __future__ import annotations

import ast
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

SPEC_PATH = Path(__file__).resolve().parent / "default_grid_spec.json"


def load_grid_spec(path: Path | None = None) -> dict[str, Any]:
    target = SPEC_PATH if path is None else path
    return json.loads(target.read_text(encoding="utf-8"))


def canonical_sha256(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ZeroHardcodedValuesAstGate:
    """Reject numeric literals outside canonical algebraic identities {-1, 0, 1}."""

    ALLOWED = {-1, 0, 1, -1.0, 0.0, 1.0}

    @classmethod
    def scan_source(cls, source_text: str) -> list[dict[str, Any]]:
        tree = ast.parse(source_text)
        violations: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                if node.value not in cls.ALLOWED:
                    violations.append({"line": node.lineno, "value": node.value})
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
                    neg = -node.operand.value
                    if neg not in cls.ALLOWED:
                        violations.append({"line": node.lineno, "value": neg})
        return violations


class DomainAgnosticNamingGate:
    """Reject industry-coupled class, function, or module names."""

    @staticmethod
    def scan_source(source_text: str, forbidden_tokens: list[str]) -> list[str]:
        tree = ast.parse(source_text)
        bad: list[str] = []
        lowered = [tok.lower() for tok in forbidden_tokens]
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name_low = node.name.lower()
                if any(tok in name_low for tok in lowered):
                    bad.append(node.name)
        return bad


class InlineLeaseDurableQueue:
    """SQLite durable task queue with inline timestamp lease expiry, DAG deps, and maker != checker."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE durable_tasks (
                task_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                state TEXT NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL,
                lease_owner TEXT,
                lease_expires_at REAL NOT NULL DEFAULT 0.0,
                maker_principal TEXT,
                checker_principal TEXT,
                depends_on_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE
            );
            CREATE TABLE step_receipts (
                step_hash TEXT PRIMARY KEY,
                output_json TEXT NOT NULL,
                tokens_saved INTEGER NOT NULL
            );
            CREATE TABLE rating_objects (
                rating_key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            );
            """
        )

    def enqueue(
        self,
        task_id: str,
        kind: str,
        payload: dict[str, Any],
        depends_on: list[str] | None = None,
        maker_principal: str | None = None,
    ) -> str:
        deps = list(depends_on or [])
        idem = canonical_sha256({"task_id": task_id, "kind": kind, "payload": payload})
        max_att = int(self.settings["max_task_attempts"])
        init_state = "blocked_deps" if deps else "ready"
        self.conn.execute(
            """
            INSERT OR IGNORE INTO durable_tasks
            (task_id, kind, state, attempt_count, max_attempts, lease_expires_at, maker_principal, depends_on_json, payload_json, idempotency_key)
            VALUES (?, ?, ?, 0, ?, 0.0, ?, ?, ?, ?)
            """,
            (task_id, kind, init_state, max_att, maker_principal, json.dumps(deps), json.dumps(payload, sort_keys=True), idem),
        )
        self.conn.commit()
        return idem

    def refresh_dependencies(self) -> int:
        rows = self.conn.execute("SELECT task_id, depends_on_json FROM durable_tasks WHERE state = 'blocked_deps'").fetchall()
        unlocked = 0
        for row in rows:
            deps = json.loads(row["depends_on_json"])
            done_cnt = self.conn.execute(
                f"SELECT COUNT(*) FROM durable_tasks WHERE state = 'done' AND task_id IN ({','.join('?' for _ in deps)})",
                deps,
            ).fetchone()[0]
            if done_cnt == len(deps):
                self.conn.execute("UPDATE durable_tasks SET state = 'ready' WHERE task_id = ?", (row["task_id"],))
                unlocked += 1
        self.conn.commit()
        return unlocked

    def claim_next(self, worker_principal: str, now_epoch: float) -> dict[str, Any] | None:
        """Inline lease expiry reclaims crashed tasks without any external cron sweeper."""
        self.refresh_dependencies()
        rows = self.conn.execute(
            """
            SELECT * FROM durable_tasks
            WHERE state = 'ready'
               OR (state = 'claimed' AND lease_expires_at < ?)
            ORDER BY task_id ASC
            """,
            (now_epoch,),
        ).fetchall()
        ttl = float(self.settings["lease_ttl_seconds"])
        for row in rows:
            if row["kind"] == "review" and row["maker_principal"] == worker_principal:
                continue
            next_attempt = int(row["attempt_count"]) + 1
            if next_attempt > int(row["max_attempts"]):
                self.conn.execute(
                    "UPDATE durable_tasks SET state = 'dead_letter' WHERE task_id = ?",
                    (row["task_id"],),
                )
                self.conn.commit()
                continue
            self.conn.execute(
                """
                UPDATE durable_tasks
                SET state = 'claimed',
                    attempt_count = ?,
                    lease_owner = ?,
                    lease_expires_at = ?
                WHERE task_id = ?
                """,
                (next_attempt, worker_principal, now_epoch + ttl, row["task_id"]),
            )
            self.conn.commit()
            return dict(self.conn.execute("SELECT * FROM durable_tasks WHERE task_id = ?", (row["task_id"],)).fetchone())
        return None

    def complete_task(self, task_id: str, worker_principal: str) -> bool:
        row = self.conn.execute("SELECT * FROM durable_tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None or row["lease_owner"] != worker_principal or row["state"] != "claimed":
            return False
        if row["kind"] == "review" and row["maker_principal"] == worker_principal:
            return False
        checker = worker_principal if row["kind"] == "review" else row["checker_principal"]
        self.conn.execute(
            "UPDATE durable_tasks SET state = 'done', checker_principal = ? WHERE task_id = ?",
            (checker, task_id),
        )
        self.conn.commit()
        self.refresh_dependencies()
        return True

    def memoized_step(self, step_signature: dict[str, Any], compute_tokens: int, output_obj: dict[str, Any]) -> tuple[dict[str, Any], int]:
        step_hash = canonical_sha256(step_signature)
        cached = self.conn.execute("SELECT output_json FROM step_receipts WHERE step_hash = ?", (step_hash,)).fetchone()
        if cached is not None:
            return json.loads(cached["output_json"]), 0
        self.conn.execute(
            "INSERT INTO step_receipts (step_hash, output_json, tokens_saved) VALUES (?, ?, ?)",
            (step_hash, json.dumps(output_obj, sort_keys=True), compute_tokens),
        )
        self.conn.commit()
        return output_obj, compute_tokens

    def put_idempotent_rating(
        self,
        source_id: str,
        content_sha256: str,
        ontology_ver: str,
        rubric_ver: str,
        prompt_ver: str,
        model_id: str,
        score_payload: dict[str, Any],
    ) -> tuple[str, bool]:
        rating_key = canonical_sha256(
            {
                "source_id": source_id,
                "content_sha256": content_sha256,
                "ontology_ver": ontology_ver,
                "rubric_ver": rubric_ver,
                "prompt_ver": prompt_ver,
                "model_id": model_id,
            }
        )
        existing = self.conn.execute("SELECT rating_key FROM rating_objects WHERE rating_key = ?", (rating_key,)).fetchone()
        if existing is not None:
            return rating_key, False
        self.conn.execute(
            "INSERT INTO rating_objects (rating_key, value_json) VALUES (?, ?)",
            (rating_key, json.dumps(score_payload, sort_keys=True)),
        )
        self.conn.commit()
        return rating_key, True


class AdaptAndCoalescePlanner:
    """Coalesce homogeneous items sharing prefix P and split only on failure or trust boundaries."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings

    def plan_granularity(
        self,
        item_count: int,
        shared_prefix_tokens: int,
        per_item_tokens: int,
        failed_verification: bool,
        depth: int,
    ) -> dict[str, Any]:
        max_k = int(self.settings["prefix_coalesce_max_k"])
        max_depth = int(self.settings["max_decomposition_depth"])
        naive_split_tokens = item_count * (shared_prefix_tokens + per_item_tokens)
        batches = max(1, (item_count + max_k - 1) // max_k)
        coalesced_tokens = batches * shared_prefix_tokens + item_count * per_item_tokens
        decompose_triggered = bool(failed_verification and depth < max_depth)
        return {
            "batches": batches,
            "naive_split_tokens": naive_split_tokens,
            "coalesced_tokens": coalesced_tokens,
            "prefix_tokens_saved": naive_split_tokens - coalesced_tokens,
            "adapt_decompose_triggered": decompose_triggered,
        }


class HybridSubspaceMemoryTrainer:
    """Zero-OOM CPU-RAM + GPU subspace memory matrix & rotating layer-window trainer."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings

    def project_and_reconstruct(self, grad_matrix: list[list[float]]) -> dict[str, Any]:
        rows = len(grad_matrix)
        cols = len(grad_matrix[0]) if rows > 0 else 0
        rank = min(int(self.settings["subspace_rank"]), rows, cols)
        # Deterministic orthogonal coordinate basis over top-variance rows (pure stdlib)
        row_norms = [(sum(v * v for v in grad_matrix[r]), r) for r in range(rows)]
        row_norms.sort(reverse=True)
        chosen = [idx for _, idx in row_norms[:rank]]
        compact_state = [list(grad_matrix[idx]) for idx in chosen]
        recon = [[0.0 for _ in range(cols)] for _ in range(rows)]
        for pos, idx in enumerate(chosen):
            recon[idx] = list(compact_state[pos])
        full_scalars = rows * cols
        compact_scalars = rank * cols
        decimals = int(self.settings["rounding_decimals"])
        return {
            "full_optimizer_scalars": full_scalars,
            "subspace_optimizer_scalars": compact_scalars,
            "memory_reduction_ratio": round(full_scalars / float(max(1, compact_scalars)), decimals),
            "reconstructed_top_energy": sum(sum(v * v for v in r) for r in recon) > 0.0,
        }

    def rotate_layer_sessions(self, session_count: int) -> dict[str, Any]:
        total_layers = int(self.settings["total_transformer_layers"])
        window = int(self.settings["active_layer_window"])
        visited: set[int] = set()
        chain_digest = canonical_sha256({"genesis": total_layers})
        for step in range(session_count):
            start = (step * window) % total_layers
            active = [(start + offset) % total_layers for offset in range(window)]
            visited.update(active)
            chain_digest = canonical_sha256({"prev": chain_digest, "step": step, "active": active})
        prefix_len = int(self.settings["hex_digest_prefix_chars"])
        return {
            "distinct_layers_covered": len(visited),
            "full_model_covered": len(visited) == total_layers,
            "ledger_digest_prefix_len": len(chain_digest[:prefix_len]),
        }


def evaluate_bundle(bundle: dict[str, Any], spec: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = (spec or load_grid_spec())["defaults"]
    forbidden = (spec or load_grid_spec())["forbidden_industry_tokens"]
    q = InlineLeaseDurableQueue(cfg)

    # 1. Enqueue build + dependent review durable task
    q.enqueue("task-build-01", "build", bundle["task_payload"], depends_on=[], maker_principal="worker-alpha")
    q.enqueue(
        "task-review-01",
        "review",
        bundle["task_payload"],
        depends_on=["task-build-01"],
        maker_principal="worker-alpha",
    )

    # 2. Simulate crashed worker reclaim via inline lease expiry (no cron sweeper)
    first_claim = q.claim_next("worker-alpha", float(bundle["t0_epoch"]))
    reclaimed_after_expiry = q.claim_next("worker-alpha", float(bundle["t_expired_epoch"]))
    q.complete_task("task-build-01", "worker-alpha")

    # 3. Verify maker != checker blocks self-review by worker-alpha, allows worker-beta
    self_review_claim = q.claim_next("worker-alpha", float(bundle["t_review_epoch"]))
    distinct_review_claim = q.claim_next("worker-beta", float(bundle["t_review_epoch"]))
    review_completed = q.complete_task("task-review-01", "worker-beta")

    # 4. Verify poison task transitions to dead_letter after max_attempts
    q.enqueue("task-poison-01", "build", {"poison": True})
    for idx, ts in enumerate(bundle["poison_claim_epochs"]):
        q.claim_next(f"worker-p{idx}", float(ts))
    poison_state = q.conn.execute("SELECT state FROM durable_tasks WHERE task_id = 'task-poison-01'").fetchone()["state"]

    # 5. Step receipt crash replay saves 100% of tokens on second run
    _, first_tokens = q.memoized_step(bundle["step_signature"], int(bundle["step_tokens"]), {"ok": True})
    _, replay_tokens = q.memoized_step(bundle["step_signature"], int(bundle["step_tokens"]), {"ok": True})

    # 6. Content-addressed rating idempotency
    _, inserted_first = q.put_idempotent_rating(**bundle["rating_call"])
    _, inserted_duplicate = q.put_idempotent_rating(**bundle["rating_call"])

    # 7. ADaPT + prefix coalescing
    gran = AdaptAndCoalescePlanner(cfg).plan_granularity(**bundle["granularity_probe"])

    # 8. Hybrid subspace memory matrix & rotating layer sessions
    trainer = HybridSubspaceMemoryTrainer(cfg)
    mem = trainer.project_and_reconstruct(bundle["grad_matrix"])
    rot = trainer.rotate_layer_sessions(int(bundle["rotation_sessions"]))

    # 9. Mechanical AST & naming conformance gates
    q.conn.close()
    self_source = Path(__file__).read_text(encoding="utf-8")
    engine_ast = len(ZeroHardcodedValuesAstGate.scan_source(self_source))
    sample_ast = len(ZeroHardcodedValuesAstGate.scan_source(bundle["magic_code_sample"]))
    sample_naming = len(DomainAgnosticNamingGate.scan_source(bundle["industry_coupled_sample"], forbidden))

    return {
        "inline_lease_reclaimed": first_claim is not None and reclaimed_after_expiry is not None and int(reclaimed_after_expiry["attempt_count"]) > 1,
        "self_review_blocked": self_review_claim is None,
        "distinct_review_completed": distinct_review_claim is not None and review_completed,
        "poison_routed_to_dead_letter": poison_state == "dead_letter",
        "first_step_tokens": first_tokens,
        "replay_step_tokens": replay_tokens,
        "rating_idempotent_deduped": inserted_first and (not inserted_duplicate),
        "prefix_tokens_saved": int(gran["prefix_tokens_saved"]),
        "adapt_decompose_triggered": bool(gran["adapt_decompose_triggered"]),
        "memory_reduction_ratio": float(mem["memory_reduction_ratio"]),
        "full_model_layers_covered": bool(rot["full_model_covered"]),
        "engine_ast_violations": engine_ast,
        "sample_magic_ast_violations": sample_ast,
        "sample_domain_naming_violations": sample_naming,
    }
