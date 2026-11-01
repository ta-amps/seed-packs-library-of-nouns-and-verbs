"""Mechanical AST conformance gate rejecting hardcoded magic numeric literals in operational code."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

ALLOWED_INT_IDENTITIES: frozenset[int] = frozenset({-1, 0, 1})
ALLOWED_FLOAT_IDENTITIES: frozenset[float] = frozenset({-1.0, 0.0, 1.0})


class _MagicLiteralVisitor(ast.NodeVisitor):
    """Visits operational FunctionDef / AsyncFunctionDef / ClassDef bodies for non-identity numbers."""

    def __init__(self, source_name: str) -> None:
        self.source_name = source_name
        self.scope_depth = 0
        self.in_annotation = 0
        self.violations: list[dict[str, Any]] = []

    def _is_identity_number(self, val: int | float) -> bool:
        if isinstance(val, bool):
            return True
        if isinstance(val, int):
            return val in ALLOWED_INT_IDENTITIES
        if isinstance(val, float):
            return val in ALLOWED_FLOAT_IDENTITIES
        return False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.scope_depth += 1
        for idx, stmt in enumerate(node.body):
            if (
                idx == 0
                and isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                continue
            self.visit(stmt)
        self.scope_depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_callable(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_callable(node)

    def _visit_callable(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.in_annotation += 1
        for arg in (
            list(node.args.posonlyargs)
            + list(node.args.args)
            + list(node.args.kwonlyargs)
            + ([node.args.vararg] if node.args.vararg else [])
            + ([node.args.kwarg] if node.args.kwarg else [])
        ):
            if arg.annotation:
                self.visit(arg.annotation)
        if node.returns:
            self.visit(node.returns)
        self.in_annotation -= 1

        self.scope_depth += 1
        for default_expr in list(node.args.defaults) + [d for d in node.args.kw_defaults if d is not None]:
            self.visit(default_expr)
        for idx, stmt in enumerate(node.body):
            if (
                idx == 0
                and isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str)
            ):
                continue
            self.visit(stmt)
        self.scope_depth -= 1

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.in_annotation += 1
        self.visit(node.annotation)
        self.in_annotation -= 1
        if node.value is not None:
            self.visit(node.value)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        if (
            self.scope_depth > 0
            and self.in_annotation == 0
            and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))
            and not isinstance(node.operand.value, bool)
        ):
            neg_val = -node.operand.value
            if not self._is_identity_number(neg_val):
                self.violations.append(
                    {
                        "source": self.source_name,
                        "line": node.lineno,
                        "col": node.col_offset,
                        "literal": neg_val,
                    }
                )
            return
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if self.scope_depth > 0 and self.in_annotation == 0:
            val = node.value
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                if not self._is_identity_number(val):
                    self.violations.append(
                        {
                            "source": self.source_name,
                            "line": node.lineno,
                            "col": node.col_offset,
                            "literal": val,
                        }
                    )


class ZeroHardcodedValuesAstGate:
    """AST scanner enforcing zero magic numeric literals in grid-governed operational Python code."""

    @staticmethod
    def scan_source(source_code: str, *, source_name: str = "<memory>") -> dict[str, Any]:
        tree = ast.parse(source_code, filename=source_name)
        visitor = _MagicLiteralVisitor(source_name)
        visitor.visit(tree)
        return {
            "passed": len(visitor.violations) == 0,
            "violation_count": len(visitor.violations),
            "violations": visitor.violations,
        }

    @classmethod
    def scan_paths(cls, paths: list[Path]) -> dict[str, Any]:
        all_violations: list[dict[str, Any]] = []
        scanned = 0
        for p in sorted(paths):
            files = sorted(p.rglob("*.py")) if p.is_dir() else [p]
            for py_file in files:
                scanned += 1
                res = cls.scan_source(py_file.read_text(encoding="utf-8"), source_name=py_file.name)
                all_violations.extend(res["violations"])
        return {
            "passed": len(all_violations) == 0,
            "files_scanned": scanned,
            "violation_count": len(all_violations),
            "violations": all_violations,
        }
