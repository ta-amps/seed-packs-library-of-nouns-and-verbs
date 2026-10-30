"""Catalog of 18 prewritten, deterministic, self-tested Python nodes seeded into NodeDatabase."""

from __future__ import annotations

from code_composition.schemas import ParamSpec, PortSpec, PrewrittenNode

# Default hash salt of validate.holdout_split. The value is kept byte for byte from the first
# release: the salt decides which records land in the holdout partition, so any other value would
# move records between partitions and change every result computed with the default. The node's
# stored source receives the same literal through the slot below, so its code_sha256 is unchanged.
HOLDOUT_SPLIT_DEFAULT_SALT = "kothar-v1"
_HOLDOUT_SPLIT_SALT_SLOT = "__HOLDOUT_SPLIT_DEFAULT_SALT__"


def build_seed_nodes() -> list[PrewrittenNode]:
    """Return the 18 prewritten verified pure-Python code nodes."""
    return [
        PrewrittenNode(
            node_id="ingest.csv_rows",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="ingest",
            summary="Parse delimiter-separated text into typed row records with numeric coercion.",
            inputs=[
                PortSpec(
                    name="raw_csv",
                    port_type="text",
                    description="Headered delimiter-separated text payload.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Parsed list of typed dictionary records.",
                ),
                PortSpec(
                    name="ingest_stats",
                    port_type="metrics",
                    description="Row and column counts parsed from CSV text.",
                ),
            ],
            params=[
                ParamSpec(
                    name="delimiter",
                    param_type="str",
                    default=",",
                    choices=[",", "\t", "|", ";"],
                    description="Field delimiter character.",
                ),
                ParamSpec(
                    name="strip_values",
                    param_type="bool",
                    default=True,
                    description="Trim whitespace around cell strings and headers.",
                ),
            ],
            function_name="node_ingest_csv_rows",
            source_code="""
def node_ingest_csv_rows(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import csv
    import io

    raw_csv = str(inputs["raw_csv"])
    delimiter = str(params.get("delimiter", ","))
    strip_values = bool(params.get("strip_values", True))

    lines = [ln for ln in raw_csv.splitlines() if ln.strip()]
    if not lines:
        return {"rows": [], "ingest_stats": {"row_count": 0, "column_count": 0}}

    reader = csv.DictReader(io.StringIO("\\n".join(lines)), delimiter=delimiter)
    fieldnames = [f.strip() if strip_values and f else (f or "") for f in (reader.fieldnames or [])]
    rows: list[dict[str, Any]] = []
    for raw_row in reader:
        record: dict[str, Any] = {}
        for raw_key, raw_val in raw_row.items():
            if raw_key is None:
                continue
            key = raw_key.strip() if strip_values else raw_key
            cell = (raw_val or "").strip() if strip_values else (raw_val or "")
            if cell == "" or cell.lower() in {"null", "none", "nan", "na"}:
                record[key] = None
            else:
                try:
                    record[key] = int(cell)
                except ValueError:
                    try:
                        record[key] = float(cell)
                    except ValueError:
                        record[key] = cell
        rows.append(record)
    return {
        "rows": rows,
        "ingest_stats": {"row_count": len(rows), "column_count": len(fieldnames)},
    }
""",
            test_cases=[
                {
                    "name": "coerces_numbers_and_nulls",
                    "inputs": {"raw_csv": "id,score,team\ne1,12.5,core\ne2,,edge\ne3,7,core\n"},
                    "params": {"delimiter": ",", "strip_values": True},
                    "expected": {
                        "rows": [
                            {"id": "e1", "score": 12.5, "team": "core"},
                            {"id": "e2", "score": None, "team": "edge"},
                            {"id": "e3", "score": 7, "team": "core"},
                        ],
                        "ingest_stats": {"row_count": 3, "column_count": 3},
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="clean.dedupe_by_key",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="clean",
            summary="Deduplicate row records by a key column while keeping the first or last occurrence.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Input row records that may contain duplicate keys.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Deduplicated row records in deterministic order.",
                ),
                PortSpec(
                    name="dedupe_stats",
                    port_type="metrics",
                    description="Input, unique, and duplicate removal counts.",
                ),
            ],
            params=[
                ParamSpec(
                    name="key_field",
                    param_type="str",
                    required=True,
                    description="Record field used as deduplication key.",
                ),
                ParamSpec(
                    name="keep",
                    param_type="str",
                    default="first",
                    choices=["first", "last"],
                    description="Keep first or last record per duplicate key.",
                ),
            ],
            function_name="node_clean_dedupe_by_key",
            source_code="""
def node_clean_dedupe_by_key(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    src_rows = list(inputs["rows"])
    key_field = str(params["key_field"])
    keep = str(params.get("keep", "first"))

    if keep == "last":
        last_index: dict[Any, int] = {}
        for idx, row in enumerate(src_rows):
            last_index[row.get(key_field)] = idx
        deduped = [dict(row) for idx, row in enumerate(src_rows) if last_index[row.get(key_field)] == idx]
    else:
        seen: set[Any] = set()
        deduped = []
        for row in src_rows:
            key = row.get(key_field)
            if key not in seen:
                seen.add(key)
                deduped.append(dict(row))

    return {
        "rows": deduped,
        "dedupe_stats": {
            "input_count": len(src_rows),
            "unique_count": len(deduped),
            "duplicates_removed": len(src_rows) - len(deduped),
        },
    }
""",
            test_cases=[
                {
                    "name": "dedupe_first_and_counts",
                    "inputs": {
                        "rows": [
                            {"id": "a", "v": 1},
                            {"id": "b", "v": 2},
                            {"id": "a", "v": 9},
                        ]
                    },
                    "params": {"key_field": "id", "keep": "first"},
                    "expected": {
                        "rows": [{"id": "a", "v": 1}, {"id": "b", "v": 2}],
                        "dedupe_stats": {
                            "input_count": 3,
                            "unique_count": 2,
                            "duplicates_removed": 1,
                        },
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="clean.impute_numeric",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="clean",
            summary="Fill missing numeric fields across records using median, mean, or constant fallback.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Input records with potential null numeric cells.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Records with missing numeric fields imputed.",
                ),
                PortSpec(
                    name="impute_stats",
                    port_type="metrics",
                    description="Imputed cell count and field count.",
                ),
            ],
            params=[
                ParamSpec(
                    name="fields",
                    param_type="str_list",
                    required=True,
                    description="List of numeric field names to impute.",
                ),
                ParamSpec(
                    name="strategy",
                    param_type="str",
                    default="median",
                    choices=["median", "mean", "constant"],
                    description="Statistic used to compute fill values.",
                ),
                ParamSpec(
                    name="fill_value",
                    param_type="float",
                    default=0.0,
                    description="Fallback constant when strategy is constant or column is all-null.",
                ),
            ],
            function_name="node_clean_impute_numeric",
            source_code="""
def node_clean_impute_numeric(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    src_rows = list(inputs["rows"])
    fields = [str(f) for f in params["fields"]]
    strategy = str(params.get("strategy", "median"))
    fallback = float(params.get("fill_value", 0.0))

    fills: dict[str, float] = {}
    for field in fields:
        observed: list[float] = []
        for row in src_rows:
            val = row.get(field)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                observed.append(float(val))
        if not observed or strategy == "constant":
            fills[field] = round(fallback, 6)
        elif strategy == "mean":
            fills[field] = round(sum(observed) / len(observed), 6)
        else:
            ordered = sorted(observed)
            mid = len(ordered) // 2
            if len(ordered) % 2 == 1:
                fills[field] = round(ordered[mid], 6)
            else:
                fills[field] = round((ordered[mid - 1] + ordered[mid]) / 2.0, 6)

    imputed_cells = 0
    out_rows: list[dict[str, Any]] = []
    for row in src_rows:
        copied = dict(row)
        for field in fields:
            val = copied.get(field)
            if val is None or not isinstance(val, (int, float)) or isinstance(val, bool):
                copied[field] = fills[field]
                imputed_cells += 1
        out_rows.append(copied)

    return {
        "rows": out_rows,
        "impute_stats": {"imputed_cells": imputed_cells, "field_count": len(fields)},
    }
""",
            test_cases=[
                {
                    "name": "median_imputation",
                    "inputs": {
                        "rows": [
                            {"x": 10.0},
                            {"x": None},
                            {"x": 30.0},
                        ]
                    },
                    "params": {"fields": ["x"], "strategy": "median", "fill_value": 0.0},
                    "expected": {
                        "rows": [{"x": 10.0}, {"x": 20.0}, {"x": 30.0}],
                        "impute_stats": {"imputed_cells": 1, "field_count": 1},
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="clean.winsorize_outliers",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="clean",
            summary="Clamp extreme numeric values in a field to empirical lower and upper quantiles.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Input records containing the numeric target field.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Records with target field clamped to quantile bounds.",
                ),
                PortSpec(
                    name="clamp_stats",
                    port_type="metrics",
                    description="Clamped cell count plus lower and upper bounds.",
                ),
            ],
            params=[
                ParamSpec(
                    name="field",
                    param_type="str",
                    required=True,
                    description="Numeric field name to winsorize.",
                ),
                ParamSpec(
                    name="lower_q",
                    param_type="float",
                    default=0.05,
                    min_value=0.0,
                    max_value=0.49,
                    description="Lower quantile in [0.0, 0.49].",
                ),
                ParamSpec(
                    name="upper_q",
                    param_type="float",
                    default=0.95,
                    min_value=0.51,
                    max_value=1.0,
                    description="Upper quantile in [0.51, 1.0].",
                ),
            ],
            function_name="node_clean_winsorize_outliers",
            source_code="""
def node_clean_winsorize_outliers(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    src_rows = list(inputs["rows"])
    field = str(params["field"])
    lower_q = float(params.get("lower_q", 0.05))
    upper_q = float(params.get("upper_q", 0.95))

    vals = sorted(
        float(r[field])
        for r in src_rows
        if isinstance(r.get(field), (int, float)) and not isinstance(r.get(field), bool)
    )
    if not vals:
        return {
            "rows": [dict(r) for r in src_rows],
            "clamp_stats": {"clamped_count": 0, "lower_bound": 0.0, "upper_bound": 0.0},
        }

    def _quantile(sorted_vals: list[float], q: float) -> float:
        if len(sorted_vals) == 1:
            return sorted_vals[0]
        pos = q * (len(sorted_vals) - 1)
        lo_idx = int(pos)
        hi_idx = min(lo_idx + 1, len(sorted_vals) - 1)
        frac = pos - lo_idx
        return sorted_vals[lo_idx] + frac * (sorted_vals[hi_idx] - sorted_vals[lo_idx])

    lo_bound = round(_quantile(vals, lower_q), 6)
    hi_bound = round(_quantile(vals, upper_q), 6)
    clamped_count = 0
    out_rows: list[dict[str, Any]] = []
    for row in src_rows:
        copied = dict(row)
        raw = copied.get(field)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            val = float(raw)
            clamped = min(max(val, lo_bound), hi_bound)
            if clamped != val:
                clamped_count += 1
            copied[field] = round(clamped, 6)
        out_rows.append(copied)

    return {
        "rows": out_rows,
        "clamp_stats": {
            "clamped_count": clamped_count,
            "lower_bound": lo_bound,
            "upper_bound": hi_bound,
        },
    }
""",
            test_cases=[
                {
                    "name": "clamps_high_spike",
                    "inputs": {"rows": [{"v": 10}, {"v": 12}, {"v": 14}, {"v": 15}, {"v": 1000}]},
                    "params": {"field": "v", "lower_q": 0.1, "upper_q": 0.75},
                    "expected": {
                        "clamp_stats": {
                            "clamped_count": 2,
                            "lower_bound": 10.8,
                            "upper_bound": 15.0,
                        }
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="feature.ratio_column",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="feature",
            summary="Compute a safe numerator-over-denominator ratio column across row records.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Input records containing numerator and denominator columns.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Records augmented with the computed ratio field.",
                ),
                PortSpec(
                    name="values",
                    port_type="series",
                    description="Ordered numeric ratio series across rows.",
                ),
            ],
            params=[
                ParamSpec(
                    name="numerator",
                    param_type="str",
                    required=True,
                    description="Numerator field name.",
                ),
                ParamSpec(
                    name="denominator",
                    param_type="str",
                    required=True,
                    description="Denominator field name.",
                ),
                ParamSpec(
                    name="output_field",
                    param_type="str",
                    default="ratio",
                    description="Destination field name written onto each record.",
                ),
                ParamSpec(
                    name="epsilon",
                    param_type="float",
                    default=1e-9,
                    min_value=1e-12,
                    max_value=1.0,
                    description="Zero-division floor applied when denominator magnitude is tiny.",
                ),
            ],
            function_name="node_feature_ratio_column",
            source_code="""
def node_feature_ratio_column(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    src_rows = list(inputs["rows"])
    num_key = str(params["numerator"])
    den_key = str(params["denominator"])
    out_key = str(params.get("output_field", "ratio"))
    eps = float(params.get("epsilon", 1e-9))

    out_rows: list[dict[str, Any]] = []
    series: list[float] = []
    for row in src_rows:
        copied = dict(row)
        num = float(copied.get(num_key) or 0.0)
        den_raw = float(copied.get(den_key) or 0.0)
        safe_den = den_raw if abs(den_raw) > eps else eps
        ratio = round(num / safe_den, 6)
        copied[out_key] = ratio
        out_rows.append(copied)
        series.append(ratio)

    return {"rows": out_rows, "values": series}
""",
            test_cases=[
                {
                    "name": "computes_error_rate",
                    "inputs": {"rows": [{"err": 5, "req": 100}, {"err": 0, "req": 50}]},
                    "params": {
                        "numerator": "err",
                        "denominator": "req",
                        "output_field": "error_rate",
                    },
                    "expected": {
                        "rows": [
                            {"err": 5, "req": 100, "error_rate": 0.05},
                            {"err": 0, "req": 50, "error_rate": 0.0},
                        ],
                        "values": [0.05, 0.0],
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="feature.rolling_zscore",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="feature",
            summary="Compute trailing-window z-scores over a numeric record field.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Ordered input records containing the numeric target field.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Records augmented with trailing z-score values.",
                ),
                PortSpec(
                    name="zscores",
                    port_type="series",
                    description="Ordered numeric z-score series.",
                ),
            ],
            params=[
                ParamSpec(
                    name="field",
                    param_type="str",
                    required=True,
                    description="Numeric field name to standardize.",
                ),
                ParamSpec(
                    name="output_field",
                    param_type="str",
                    default="zscore",
                    description="Destination z-score field name.",
                ),
                ParamSpec(
                    name="window",
                    param_type="int",
                    default=5,
                    min_value=2,
                    max_value=500,
                    description="Trailing window size (>= 2).",
                ),
            ],
            function_name="node_feature_rolling_zscore",
            source_code="""
def node_feature_rolling_zscore(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import math

    src_rows = list(inputs["rows"])
    field = str(params["field"])
    out_key = str(params.get("output_field", "zscore"))
    window = int(params.get("window", 5))

    history: list[float] = []
    out_rows: list[dict[str, Any]] = []
    zscores: list[float] = []
    for row in src_rows:
        copied = dict(row)
        val = float(copied.get(field) or 0.0)
        history.append(val)
        win = history[-window:]
        mean = sum(win) / len(win)
        var = sum((x - mean) ** 2 for x in win) / len(win)
        std = math.sqrt(var)
        z = 0.0 if std < 1e-9 else round((val - mean) / std, 6)
        copied[out_key] = z
        out_rows.append(copied)
        zscores.append(z)

    return {"rows": out_rows, "zscores": zscores}
""",
            test_cases=[
                {
                    "name": "trailing_spike_positive_zscore",
                    "inputs": {"rows": [{"ms": 10}, {"ms": 10}, {"ms": 40}]},
                    "params": {"field": "ms", "output_field": "z", "window": 3},
                    "expected": {"zscores": [0.0, 0.0, 1.414214]},
                }
            ],
        ),
        PrewrittenNode(
            node_id="text.normalize_whitespace",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="text",
            summary="Collapse horizontal whitespace, trim lines, and optionally lowercase raw text.",
            inputs=[
                PortSpec(
                    name="raw_text",
                    port_type="text",
                    description="Unstructured multi-line text document or log stream.",
                )
            ],
            outputs=[
                PortSpec(
                    name="clean_text",
                    port_type="text",
                    description="Whitespace-normalized text.",
                ),
                PortSpec(
                    name="text_stats",
                    port_type="metrics",
                    description="Character, line, and word counts after normalization.",
                ),
            ],
            params=[
                ParamSpec(
                    name="lowercase",
                    param_type="bool",
                    default=False,
                    description="Convert text to lowercase when true.",
                ),
                ParamSpec(
                    name="collapse_blank_lines",
                    param_type="bool",
                    default=True,
                    description="Drop empty lines when true.",
                ),
            ],
            function_name="node_text_normalize_whitespace",
            source_code="""
def node_text_normalize_whitespace(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import re

    raw_text = str(inputs["raw_text"]).replace("\\r\\n", "\\n").replace("\\r", "\\n")
    lowercase = bool(params.get("lowercase", False))
    collapse_blank = bool(params.get("collapse_blank_lines", True))

    cleaned_lines: list[str] = []
    for line in raw_text.split("\\n"):
        compact = re.sub(r"[ \\t]+", " ", line).strip()
        if collapse_blank and not compact:
            continue
        cleaned_lines.append(compact)

    clean_text = "\\n".join(cleaned_lines)
    if lowercase:
        clean_text = clean_text.lower()

    words = [w for w in clean_text.split() if w]
    return {
        "clean_text": clean_text,
        "text_stats": {
            "char_count": len(clean_text),
            "line_count": len(cleaned_lines) if clean_text else 0,
            "word_count": len(words),
        },
    }
""",
            test_cases=[
                {
                    "name": "collapses_tabs_and_blanks",
                    "inputs": {"raw_text": "  Alpha   beta \n\n\tGamma  delta  "},
                    "params": {"lowercase": True, "collapse_blank_lines": True},
                    "expected": {
                        "clean_text": "alpha beta\ngamma delta",
                        "text_stats": {"char_count": 22, "line_count": 2, "word_count": 4},
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="text.regex_extract",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="text",
            summary="Extract structured row records from normalized text via a regular expression.",
            inputs=[
                PortSpec(
                    name="clean_text",
                    port_type="text",
                    description="Normalized text input scanned line-by-line or multi-line.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Extracted structured records with named regex groups.",
                ),
                PortSpec(
                    name="extract_stats",
                    port_type="metrics",
                    description="Total regex matches extracted.",
                ),
            ],
            params=[
                ParamSpec(
                    name="pattern",
                    param_type="str",
                    required=True,
                    description="Regular expression with named capture groups.",
                ),
                ParamSpec(
                    name="record_prefix",
                    param_type="str",
                    default="doc",
                    description="Fallback ID prefix when pattern omits doc_id.",
                ),
            ],
            function_name="node_text_regex_extract",
            source_code="""
def node_text_regex_extract(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import re

    clean_text = str(inputs["clean_text"])
    pattern = str(params["pattern"])
    prefix = str(params.get("record_prefix", "doc"))

    compiled = re.compile(pattern, flags=re.MULTILINE)
    rows: list[dict[str, Any]] = []
    for idx, match in enumerate(compiled.finditer(clean_text)):
        named = match.groupdict()
        if named:
            record: dict[str, Any] = {}
            for key, raw_val in named.items():
                val = (raw_val or "").strip()
                try:
                    record[key] = int(val)
                except ValueError:
                    try:
                        record[key] = float(val)
                    except ValueError:
                        record[key] = val
        else:
            record = {"match": match.group(0), "groups": list(match.groups())}
        record.setdefault("doc_id", f"{prefix}_{idx + 1}")
        record["match_index"] = idx
        rows.append(record)

    return {"rows": rows, "extract_stats": {"match_count": len(rows)}}
""",
            test_cases=[
                {
                    "name": "extracts_named_incident_lines",
                    "inputs": {"clean_text": "[INC-1] api: timeout spike\n[INC-2] auth: token ok"},
                    "params": {
                        "pattern": r"^\[(?P<doc_id>[A-Z0-9-]+)\]\s+(?P<channel>[a-z_]+):\s+(?P<message>.+)$"
                    },
                    "expected": {
                        "rows": [
                            {
                                "doc_id": "INC-1",
                                "channel": "api",
                                "message": "timeout spike",
                                "match_index": 0,
                            },
                            {
                                "doc_id": "INC-2",
                                "channel": "auth",
                                "message": "token ok",
                                "match_index": 1,
                            },
                        ],
                        "extract_stats": {"match_count": 2},
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="filter.threshold_gate",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="filter",
            summary="Partition records into passing and rejected subsets using a numeric threshold rule.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Input records evaluated against the numeric threshold.",
                )
            ],
            outputs=[
                PortSpec(
                    name="passed",
                    port_type="records",
                    description="Records satisfying the comparison operator and threshold.",
                ),
                PortSpec(
                    name="rejected",
                    port_type="records",
                    description="Records failing the comparison operator and threshold.",
                ),
                PortSpec(
                    name="gate_stats",
                    port_type="metrics",
                    description="Counts and pass rate across evaluated records.",
                ),
            ],
            params=[
                ParamSpec(
                    name="field",
                    param_type="str",
                    required=True,
                    description="Numeric field compared against threshold.",
                ),
                ParamSpec(
                    name="op",
                    param_type="str",
                    default="gte",
                    choices=["gt", "gte", "lt", "lte", "eq"],
                    description="Comparison operator.",
                ),
                ParamSpec(
                    name="threshold",
                    param_type="float",
                    default=0.5,
                    description="Decision threshold value.",
                ),
            ],
            function_name="node_filter_threshold_gate",
            source_code="""
def node_filter_threshold_gate(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    src_rows = list(inputs["rows"])
    field = str(params["field"])
    op = str(params.get("op", "gte"))
    threshold = float(params.get("threshold", 0.5))

    passed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in src_rows:
        copied = dict(row)
        val = float(copied.get(field) or 0.0)
        ok = (
            (op == "gt" and val > threshold)
            or (op == "gte" and val >= threshold)
            or (op == "lt" and val < threshold)
            or (op == "lte" and val <= threshold)
            or (op == "eq" and abs(val - threshold) < 1e-9)
        )
        if ok:
            passed.append(copied)
        else:
            rejected.append(copied)

    total = len(src_rows)
    rate = round(len(passed) / total, 6) if total else 0.0
    return {
        "passed": passed,
        "rejected": rejected,
        "gate_stats": {
            "total_count": total,
            "passed_count": len(passed),
            "rejected_count": len(rejected),
            "pass_rate": rate,
        },
    }
""",
            test_cases=[
                {
                    "name": "splits_high_risk_records",
                    "inputs": {"rows": [{"id": 1, "s": 0.8}, {"id": 2, "s": 0.2}]},
                    "params": {"field": "s", "op": "gte", "threshold": 0.5},
                    "expected": {
                        "passed": [{"id": 1, "s": 0.8}],
                        "rejected": [{"id": 2, "s": 0.2}],
                        "gate_stats": {
                            "total_count": 2,
                            "passed_count": 1,
                            "rejected_count": 1,
                            "pass_rate": 0.5,
                        },
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="join.keyed_enrich",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="join",
            summary="Join primary records with lookup enrichment records on a shared key column.",
            inputs=[
                PortSpec(
                    name="left_rows",
                    port_type="records",
                    description="Primary left-hand records.",
                ),
                PortSpec(
                    name="right_rows",
                    port_type="records",
                    description="Lookup enrichment records indexed by key_field.",
                ),
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Joined and enriched records.",
                ),
                PortSpec(
                    name="join_stats",
                    port_type="metrics",
                    description="Left, matched, and output record counts.",
                ),
            ],
            params=[
                ParamSpec(
                    name="key_field",
                    param_type="str",
                    required=True,
                    description="Shared join key column.",
                ),
                ParamSpec(
                    name="how",
                    param_type="str",
                    default="left",
                    choices=["left", "inner"],
                    description="Join strategy (left keeps unmatched left records; inner drops them).",
                ),
                ParamSpec(
                    name="right_prefix",
                    param_type="str",
                    default="",
                    description="Optional prefix added to non-key right-hand columns.",
                ),
            ],
            function_name="node_join_keyed_enrich",
            source_code="""
def node_join_keyed_enrich(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    left_rows = list(inputs["left_rows"])
    right_rows = list(inputs["right_rows"])
    key_field = str(params["key_field"])
    how = str(params.get("how", "left"))
    prefix = str(params.get("right_prefix", ""))

    lookup: dict[Any, dict[str, Any]] = {}
    for r_row in right_rows:
        key = r_row.get(key_field)
        if key is not None and key not in lookup:
            lookup[key] = dict(r_row)

    matched = 0
    out_rows: list[dict[str, Any]] = []
    for l_row in left_rows:
        key = l_row.get(key_field)
        r_match = lookup.get(key)
        if r_match is None:
            if how == "left":
                out_rows.append(dict(l_row))
            continue
        matched += 1
        merged = dict(l_row)
        for r_key, r_val in r_match.items():
            if r_key == key_field:
                continue
            dst_key = f"{prefix}{r_key}" if prefix else r_key
            if dst_key not in merged or merged[dst_key] is None:
                merged[dst_key] = r_val
        out_rows.append(merged)

    return {
        "rows": out_rows,
        "join_stats": {
            "left_count": len(left_rows),
            "matched_count": matched,
            "output_count": len(out_rows),
        },
    }
""",
            test_cases=[
                {
                    "name": "left_joins_owner_metadata",
                    "inputs": {
                        "left_rows": [{"svc": "api", "err": 4}, {"svc": "worker", "err": 1}],
                        "right_rows": [{"svc": "api", "team": "platform"}],
                    },
                    "params": {"key_field": "svc", "how": "left"},
                    "expected": {
                        "rows": [
                            {"svc": "api", "err": 4, "team": "platform"},
                            {"svc": "worker", "err": 1},
                        ],
                        "join_stats": {"left_count": 2, "matched_count": 1, "output_count": 2},
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="model.linear_risk_score",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="model",
            summary="Compute a calibrated logistic risk score from weighted numeric features and bias.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Feature-engineered input records.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Records augmented with bounded [0, 1] logistic score.",
                ),
                PortSpec(
                    name="scores",
                    port_type="series",
                    description="Ordered logistic probability series.",
                ),
            ],
            params=[
                ParamSpec(
                    name="feature_fields",
                    param_type="str_list",
                    required=True,
                    description="Ordered list of numeric feature column names.",
                ),
                ParamSpec(
                    name="weights_csv",
                    param_type="str",
                    default="1.0",
                    description="Comma-separated float weights aligned to feature_fields.",
                ),
                ParamSpec(
                    name="bias",
                    param_type="float",
                    default=0.0,
                    min_value=-20.0,
                    max_value=20.0,
                    description="Additive intercept prior to logistic link.",
                ),
                ParamSpec(
                    name="output_field",
                    param_type="str",
                    default="risk_score",
                    description="Destination score column name.",
                ),
            ],
            function_name="node_model_linear_risk_score",
            source_code="""
def node_model_linear_risk_score(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import math

    src_rows = list(inputs["rows"])
    features = [str(f) for f in params["feature_fields"]]
    raw_weights = [float(w.strip()) for w in str(params.get("weights_csv", "1.0")).split(",") if w.strip()]
    if not raw_weights:
        raw_weights = [1.0]
    weights = (
        raw_weights * len(features)
        if len(raw_weights) == 1 and len(features) > 1
        else raw_weights
    )
    if len(weights) != len(features):
        raise ValueError(
            f"weights_csv length ({len(weights)}) must match feature_fields ({len(features)})."
        )
    bias = float(params.get("bias", 0.0))
    out_key = str(params.get("output_field", "risk_score"))

    out_rows: list[dict[str, Any]] = []
    scores: list[float] = []
    for row in src_rows:
        copied = dict(row)
        logit = bias + sum(
            w * float(copied.get(feat) or 0.0) for feat, w in zip(features, weights, strict=True)
        )
        clamped = min(max(logit, -30.0), 30.0)
        prob = round(1.0 / (1.0 + math.exp(-clamped)), 6)
        copied[out_key] = prob
        out_rows.append(copied)
        scores.append(prob)

    return {"rows": out_rows, "scores": scores}
""",
            test_cases=[
                {
                    "name": "zero_logit_is_half",
                    "inputs": {"rows": [{"f1": 1.0, "f2": -1.0}]},
                    "params": {
                        "feature_fields": ["f1", "f2"],
                        "weights_csv": "2.0,2.0",
                        "bias": 0.0,
                        "output_field": "risk_score",
                    },
                    "expected": {
                        "rows": [{"f1": 1.0, "f2": -1.0, "risk_score": 0.5}],
                        "scores": [0.5],
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="model.keyword_weighted_score",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="model",
            summary="Score record text fields by case-insensitive keyword occurrences normalized to [0, 1].",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Records containing a text column to scan.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Records augmented with normalized keyword score and matched terms.",
                ),
                PortSpec(
                    name="scores",
                    port_type="series",
                    description="Ordered keyword signal scores in [0.0, 1.0].",
                ),
            ],
            params=[
                ParamSpec(
                    name="text_field",
                    param_type="str",
                    default="message",
                    description="Text column name on each record.",
                ),
                ParamSpec(
                    name="keywords",
                    param_type="str_list",
                    required=True,
                    description="Case-insensitive signal terms to match.",
                ),
                ParamSpec(
                    name="scale",
                    param_type="float",
                    default=3.0,
                    min_value=0.5,
                    max_value=50.0,
                    description="Hit count denominator for saturation at 1.0.",
                ),
                ParamSpec(
                    name="output_field",
                    param_type="str",
                    default="signal_score",
                    description="Destination score column name.",
                ),
            ],
            function_name="node_model_keyword_weighted_score",
            source_code="""
def node_model_keyword_weighted_score(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    src_rows = list(inputs["rows"])
    text_field = str(params.get("text_field", "message"))
    keywords = [str(k).strip().lower() for k in params["keywords"] if str(k).strip()]
    scale = float(params.get("scale", 3.0))
    out_key = str(params.get("output_field", "signal_score"))

    out_rows: list[dict[str, Any]] = []
    scores: list[float] = []
    for row in src_rows:
        copied = dict(row)
        haystack = str(copied.get(text_field) or "").lower()
        hits = [kw for kw in keywords if kw in haystack]
        score = min(1.0, round(len(hits) / scale, 6))
        copied[out_key] = score
        copied["matched_keywords"] = hits
        out_rows.append(copied)
        scores.append(score)

    return {"rows": out_rows, "scores": scores}
""",
            test_cases=[
                {
                    "name": "scores_incident_keywords",
                    "inputs": {
                        "rows": [{"message": "Critical timeout outage"}, {"message": "Healthy"}]
                    },
                    "params": {
                        "text_field": "message",
                        "keywords": ["critical", "timeout", "outage"],
                        "scale": 2.0,
                    },
                    "expected": {"scores": [1.0, 0.0]},
                }
            ],
        ),
        PrewrittenNode(
            node_id="validate.schema_contract",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="validate",
            summary="Verify minimum row count and required column presence before downstream steps.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Input records checked against structural contract.",
                )
            ],
            outputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Validated records containing all required column keys.",
                ),
                PortSpec(
                    name="contract_report",
                    port_type="metrics",
                    description="Validation summary counts.",
                ),
            ],
            params=[
                ParamSpec(
                    name="required_fields",
                    param_type="str_list",
                    required=True,
                    description="Column keys that must exist on every record.",
                ),
                ParamSpec(
                    name="min_rows",
                    param_type="int",
                    default=1,
                    min_value=0,
                    max_value=100000,
                    description="Minimum acceptable record count.",
                ),
                ParamSpec(
                    name="strict",
                    param_type="bool",
                    default=True,
                    description="Raise ValueError when contract violations occur.",
                ),
            ],
            function_name="node_validate_schema_contract",
            source_code="""
def node_validate_schema_contract(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    src_rows = list(inputs["rows"])
    required_fields = [str(f) for f in params["required_fields"]]
    min_rows = int(params.get("min_rows", 1))
    strict = bool(params.get("strict", True))

    if len(src_rows) < min_rows:
        if strict:
            raise ValueError(f"Schema contract failed: expected >= {min_rows} rows, got {len(src_rows)}.")
        return {
            "rows": [],
            "contract_report": {"valid_rows": 0, "violation_count": 1, "passed": 0},
        }

    valid_rows: list[dict[str, Any]] = []
    violations = 0
    for row in src_rows:
        missing = [f for f in required_fields if f not in row]
        if missing:
            violations += 1
            if strict:
                raise ValueError(f"Schema contract failed: missing fields {missing}.")
        else:
            valid_rows.append(dict(row))

    return {
        "rows": valid_rows,
        "contract_report": {
            "valid_rows": len(valid_rows),
            "violation_count": violations,
            "passed": 1 if violations == 0 else 0,
        },
    }
""",
            test_cases=[
                {
                    "name": "passes_complete_schema",
                    "inputs": {"rows": [{"id": "r1", "latency": 12}]},
                    "params": {"required_fields": ["id", "latency"], "min_rows": 1, "strict": True},
                    "expected": {
                        "rows": [{"id": "r1", "latency": 12}],
                        "contract_report": {"valid_rows": 1, "violation_count": 0, "passed": 1},
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="validate.holdout_split",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="validate",
            summary="Deterministically hash-split records into calibration and holdout partitions by key.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Input records partitioned deterministically by SHA-256 hash.",
                )
            ],
            outputs=[
                PortSpec(
                    name="train_rows",
                    port_type="records",
                    description="Calibration partition records.",
                ),
                PortSpec(
                    name="holdout_rows",
                    port_type="records",
                    description="Leak-free holdout partition records.",
                ),
                PortSpec(
                    name="split_stats",
                    port_type="metrics",
                    description="Partition sizes and empirical holdout ratio.",
                ),
            ],
            params=[
                ParamSpec(
                    name="key_field",
                    param_type="str",
                    required=True,
                    description="Entity key hashed so identical keys never straddle train and holdout.",
                ),
                ParamSpec(
                    name="holdout_fraction",
                    param_type="float",
                    default=0.35,
                    min_value=0.05,
                    max_value=0.95,
                    description="Target fraction routed into holdout_rows.",
                ),
                ParamSpec(
                    name="salt",
                    param_type="str",
                    default=HOLDOUT_SPLIT_DEFAULT_SALT,
                    description="Hash salt for reproducible partition seeds.",
                ),
            ],
            function_name="node_validate_holdout_split",
            source_code="""
def node_validate_holdout_split(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    import hashlib

    src_rows = list(inputs["rows"])
    key_field = str(params["key_field"])
    holdout_fraction = float(params.get("holdout_fraction", 0.35))
    salt = str(params.get("salt", __HOLDOUT_SPLIT_DEFAULT_SALT__))
    cutoff = int(holdout_fraction * 10000)

    train_rows: list[dict[str, Any]] = []
    holdout_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(src_rows):
        copied = dict(row)
        token = f"{salt}:{copied.get(key_field, idx)}".encode("utf-8")
        bucket = int(hashlib.sha256(token).hexdigest()[:8], 16) % 10000
        if bucket < cutoff:
            holdout_rows.append(copied)
        else:
            train_rows.append(copied)

    if len(src_rows) >= 2 and not holdout_rows:
        holdout_rows.append(train_rows.pop())
    elif len(src_rows) >= 2 and not train_rows:
        train_rows.append(holdout_rows.pop())

    total = len(src_rows)
    return {
        "train_rows": train_rows,
        "holdout_rows": holdout_rows,
        "split_stats": {
            "total_count": total,
            "train_count": len(train_rows),
            "holdout_count": len(holdout_rows),
            "holdout_ratio": round(len(holdout_rows) / total, 6) if total else 0.0,
        },
    }
""".replace(_HOLDOUT_SPLIT_SALT_SLOT, f'"{HOLDOUT_SPLIT_DEFAULT_SALT}"'),
            test_cases=[
                {
                    "name": "deterministic_non_empty_partitions",
                    "inputs": {"rows": [{"id": f"k{i}"} for i in range(10)]},
                    "params": {"key_field": "id", "holdout_fraction": 0.3, "salt": "s1"},
                    "expected_ports": ["train_rows", "holdout_rows", "split_stats"],
                }
            ],
        ),
        PrewrittenNode(
            node_id="eval.binary_metrics",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="eval",
            summary="Compute precision, recall, F1, accuracy, and Brier score against binary ground-truth labels.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Scored records containing continuous predictions and binary 0/1 labels.",
                )
            ],
            outputs=[
                PortSpec(
                    name="eval_metrics",
                    port_type="metrics",
                    description="Classification and calibration metrics on the evaluated split.",
                )
            ],
            params=[
                ParamSpec(
                    name="score_field",
                    param_type="str",
                    default="risk_score",
                    description="Predicted probability field in [0, 1].",
                ),
                ParamSpec(
                    name="label_field",
                    param_type="str",
                    default="label",
                    description="Ground-truth binary label field (1 or 0).",
                ),
                ParamSpec(
                    name="threshold",
                    param_type="float",
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Classification cutoff applied to score_field.",
                ),
            ],
            function_name="node_eval_binary_metrics",
            source_code="""
def node_eval_binary_metrics(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    src_rows = list(inputs["rows"])
    score_field = str(params.get("score_field", "risk_score"))
    label_field = str(params.get("label_field", "label"))
    threshold = float(params.get("threshold", 0.5))

    if not src_rows:
        return {
            "eval_metrics": {
                "sample_count": 0,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "accuracy": 0.0,
                "brier_score": 0.0,
            }
        }

    tp = fp = tn = fn = 0
    sq_err = 0.0
    for row in src_rows:
        score = float(row.get(score_field) or 0.0)
        label = 1 if int(float(row.get(label_field) or 0)) > 0 else 0
        pred = 1 if score >= threshold else 0
        sq_err += (score - label) ** 2
        if pred == 1 and label == 1:
            tp += 1
        elif pred == 1 and label == 0:
            fp += 1
        elif pred == 0 and label == 0:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2.0 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    total = len(src_rows)
    return {
        "eval_metrics": {
            "sample_count": total,
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
            "accuracy": round((tp + tn) / total, 6),
            "brier_score": round(sq_err / total, 6),
        }
    }
""",
            test_cases=[
                {
                    "name": "perfect_binary_predictions",
                    "inputs": {
                        "rows": [
                            {"risk_score": 0.9, "label": 1},
                            {"risk_score": 0.1, "label": 0},
                        ]
                    },
                    "params": {
                        "score_field": "risk_score",
                        "label_field": "label",
                        "threshold": 0.5,
                    },
                    "expected": {
                        "eval_metrics": {
                            "sample_count": 2,
                            "precision": 1.0,
                            "recall": 1.0,
                            "f1": 1.0,
                            "accuracy": 1.0,
                            "brier_score": 0.01,
                        }
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="eval.shrinkage_select",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="eval",
            summary="Compare two candidate metric bundles using empirical-Bayes shrinkage toward a conservative prior.",
            inputs=[
                PortSpec(
                    name="candidate_a",
                    port_type="metrics",
                    description="Baseline arm evaluation metrics.",
                ),
                PortSpec(
                    name="candidate_b",
                    port_type="metrics",
                    description="Challenger arm evaluation metrics.",
                ),
            ],
            outputs=[
                PortSpec(
                    name="selection",
                    port_type="json",
                    description="Structured decision record with raw and shrunk scores.",
                ),
                PortSpec(
                    name="winner_metrics",
                    port_type="metrics",
                    description="Winning arm metrics augmented with shrunk lift.",
                ),
            ],
            params=[
                ParamSpec(
                    name="metric_key",
                    param_type="str",
                    default="f1",
                    description="Metric key maximized during arm comparison.",
                ),
                ParamSpec(
                    name="count_key",
                    param_type="str",
                    default="sample_count",
                    description="Sample count key weighting empirical observations against prior_strength.",
                ),
                ParamSpec(
                    name="prior_mean",
                    param_type="float",
                    default=0.5,
                    min_value=0.0,
                    max_value=1.0,
                    description="Conservative prior mean for small-sample shrinkage.",
                ),
                ParamSpec(
                    name="prior_strength",
                    param_type="float",
                    default=8.0,
                    min_value=0.0,
                    max_value=1000.0,
                    description="Effective pseudo-sample weight on prior_mean.",
                ),
                ParamSpec(
                    name="min_margin",
                    param_type="float",
                    default=0.01,
                    min_value=0.0,
                    max_value=0.5,
                    description="Minimum shrunk gain required for candidate_b to beat baseline candidate_a.",
                ),
            ],
            function_name="node_eval_shrinkage_select",
            source_code="""
def node_eval_shrinkage_select(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    cand_a = dict(inputs["candidate_a"])
    cand_b = dict(inputs["candidate_b"])
    metric_key = str(params.get("metric_key", "f1"))
    count_key = str(params.get("count_key", "sample_count"))
    prior_mean = float(params.get("prior_mean", 0.5))
    prior_strength = float(params.get("prior_strength", 8.0))
    min_margin = float(params.get("min_margin", 0.01))

    raw_a = float(cand_a.get(metric_key) or 0.0)
    raw_b = float(cand_b.get(metric_key) or 0.0)
    n_a = max(0.0, float(cand_a.get(count_key) or 0.0))
    n_b = max(0.0, float(cand_b.get(count_key) or 0.0))

    shrunk_a = round(
        (n_a * raw_a + prior_strength * prior_mean) / (n_a + prior_strength)
        if (n_a + prior_strength) > 0
        else prior_mean,
        6,
    )
    shrunk_b = round(
        (n_b * raw_b + prior_strength * prior_mean) / (n_b + prior_strength)
        if (n_b + prior_strength) > 0
        else prior_mean,
        6,
    )
    shrunk_gain = round(shrunk_b - shrunk_a, 6)
    promote_b = shrunk_gain >= min_margin
    winner_name = "candidate_b" if promote_b else "candidate_a"
    winner = dict(cand_b if promote_b else cand_a)
    winner["shrunk_score"] = shrunk_b if promote_b else shrunk_a
    winner["shrunk_gain_vs_a"] = shrunk_gain
    winner["promoted_challenger"] = 1 if promote_b else 0

    return {
        "selection": {
            "winner": winner_name,
            "metric_key": metric_key,
            "raw_a": raw_a,
            "raw_b": raw_b,
            "shrunk_a": shrunk_a,
            "shrunk_b": shrunk_b,
            "shrunk_gain": shrunk_gain,
            "min_margin": min_margin,
        },
        "winner_metrics": winner,
    }
""",
            test_cases=[
                {
                    "name": "promotes_challenger_above_shrunk_margin",
                    "inputs": {
                        "candidate_a": {"f1": 0.60, "sample_count": 20},
                        "candidate_b": {"f1": 0.85, "sample_count": 20},
                    },
                    "params": {
                        "metric_key": "f1",
                        "prior_mean": 0.5,
                        "prior_strength": 5.0,
                        "min_margin": 0.05,
                    },
                    "expected": {
                        "selection": {
                            "winner": "candidate_b",
                            "metric_key": "f1",
                            "raw_a": 0.6,
                            "raw_b": 0.85,
                            "shrunk_a": 0.58,
                            "shrunk_b": 0.78,
                            "shrunk_gain": 0.2,
                            "min_margin": 0.05,
                        }
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="agg.group_summary",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="agg",
            summary="Aggregate records by a categorical key into count, sum, mean, and max table rows.",
            inputs=[
                PortSpec(
                    name="rows",
                    port_type="records",
                    description="Records grouped by group_field and aggregated over value_field.",
                )
            ],
            outputs=[
                PortSpec(
                    name="summary_table",
                    port_type="table",
                    description="Tabular summary with columns and deterministically ordered rows.",
                ),
                PortSpec(
                    name="agg_stats",
                    port_type="metrics",
                    description="Group count and total aggregated records.",
                ),
            ],
            params=[
                ParamSpec(
                    name="group_field",
                    param_type="str",
                    required=True,
                    description="Categorical grouping column name.",
                ),
                ParamSpec(
                    name="value_field",
                    param_type="str",
                    required=True,
                    description="Numeric value column aggregated per group.",
                ),
            ],
            function_name="node_agg_group_summary",
            source_code="""
def node_agg_group_summary(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    src_rows = list(inputs["rows"])
    group_field = str(params["group_field"])
    value_field = str(params["value_field"])

    buckets: dict[str, list[float]] = {}
    for row in src_rows:
        grp = str(row.get(group_field) if row.get(group_field) is not None else "unassigned")
        val = float(row.get(value_field) or 0.0)
        buckets.setdefault(grp, []).append(val)

    table_rows: list[dict[str, Any]] = []
    for grp, vals in buckets.items():
        total = sum(vals)
        table_rows.append(
            {
                "group": grp,
                "count": len(vals),
                "sum": round(total, 6),
                "mean": round(total / len(vals), 6),
                "max": round(max(vals), 6),
            }
        )
    table_rows.sort(key=lambda r: (-float(r["mean"]), str(r["group"])))

    return {
        "summary_table": {
            "columns": ["group", "count", "sum", "mean", "max"],
            "rows": table_rows,
        },
        "agg_stats": {"group_count": len(table_rows), "total_rows": len(src_rows)},
    }
""",
            test_cases=[
                {
                    "name": "groups_and_sorts_by_mean_desc",
                    "inputs": {
                        "rows": [
                            {"team": "core", "risk": 0.4},
                            {"team": "edge", "risk": 0.9},
                            {"team": "core", "risk": 0.6},
                        ]
                    },
                    "params": {"group_field": "team", "value_field": "risk"},
                    "expected": {
                        "summary_table": {
                            "columns": ["group", "count", "sum", "mean", "max"],
                            "rows": [
                                {"group": "edge", "count": 1, "sum": 0.9, "mean": 0.9, "max": 0.9},
                                {"group": "core", "count": 2, "sum": 1.0, "mean": 0.5, "max": 0.6},
                            ],
                        },
                        "agg_stats": {"group_count": 2, "total_rows": 3},
                    },
                }
            ],
        ),
        PrewrittenNode(
            node_id="format.markdown_report",
            version="1.0.0",
            spdx_license="MIT",
            governance_tags=["status:verified"],
            revision=1,
            category="format",
            summary="Render a deterministic Markdown report artifact from a summary table and headline metrics.",
            inputs=[
                PortSpec(
                    name="summary_table",
                    port_type="table",
                    description="Aggregated table with columns and row dicts.",
                ),
                PortSpec(
                    name="headline_metrics",
                    port_type="metrics",
                    description="Key-value pipeline metrics rendered in the report header.",
                ),
                PortSpec(
                    name="extra_context",
                    port_type="json",
                    required=False,
                    description="Optional structured decision or provenance context.",
                ),
            ],
            outputs=[
                PortSpec(
                    name="report_md",
                    port_type="artifact",
                    description="Deterministic GitHub-Flavored Markdown report string.",
                ),
                PortSpec(
                    name="digest_line",
                    port_type="text",
                    description="Single-line summary suitable for logs or notifications.",
                ),
            ],
            params=[
                ParamSpec(
                    name="title",
                    param_type="str",
                    default="Pipeline Report",
                    description="Top-level H1 Markdown heading.",
                ),
                ParamSpec(
                    name="max_rows",
                    param_type="int",
                    default=20,
                    min_value=1,
                    max_value=200,
                    description="Maximum table rows rendered into report_md.",
                ),
            ],
            function_name="node_format_markdown_report",
            source_code="""
def node_format_markdown_report(inputs: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    table = dict(inputs["summary_table"])
    metrics = dict(inputs["headline_metrics"])
    extra = inputs.get("extra_context")
    title = str(params.get("title", "Pipeline Report"))
    max_rows = int(params.get("max_rows", 20))

    cols = [str(c) for c in table.get("columns", [])]
    rows = list(table.get("rows", []))[:max_rows]

    lines = [f"# {title}", "", "## Headline Metrics", ""]
    for key in sorted(metrics):
        lines.append(f"- **{key}**: `{metrics[key]}`")

    if isinstance(extra, dict) and extra:
        lines.extend(["", "## Decision Context", ""])
        for key in sorted(extra):
            lines.append(f"- **{key}**: `{extra[key]}`")

    lines.extend(["", "## Summary Table", ""])
    if cols:
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join("---" for _ in cols) + "|")
        for row in rows:
            lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
    else:
        lines.append("_No summary columns._")

    metric_pairs = ", ".join(f"{k}={metrics[k]}" for k in sorted(metrics))
    digest_line = f"{title}: {len(rows)} group(s) [{metric_pairs}]"
    return {"report_md": "\\n".join(lines) + "\\n", "digest_line": digest_line}
""",
            test_cases=[
                {
                    "name": "renders_markdown_artifact",
                    "inputs": {
                        "summary_table": {
                            "columns": ["group", "count"],
                            "rows": [{"group": "core", "count": 2}],
                        },
                        "headline_metrics": {"passed_count": 2},
                    },
                    "params": {"title": "Triage Summary", "max_rows": 10},
                    "expected": {"digest_line": "Triage Summary: 1 group(s) [passed_count=2]"},
                }
            ],
        ),
    ]
