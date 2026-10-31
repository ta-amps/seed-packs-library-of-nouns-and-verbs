"""Purged and embargoed expanding-window walk-forward and blocked CV split generators."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def generate_purged_walk_forward_splits(
    n_bars: int,
    *,
    min_train_bars: int,
    test_bars: int,
    step_bars: int | None = None,
    label_horizon_bars: int = 1,
    embargo_bars: int = 0,
) -> list[dict[str, Any]]:
    """Generate expanding-window walk-forward splits with label-horizon purging and inter-fold embargo.

    For fold `k` with test window `[test_start, test_end)`:
    - Raw causal candidates are `[0, test_start)`.
    - Observations whose forward target spans `[t, t + label_horizon_bars)` overlapping `test_start`
      (`t + label_horizon_bars > test_start`) are purged so no test-period realization leaks into training.
    - When `embargo_bars > 0` and `k > 0`, observations inside `[prev_test_end, prev_test_end + embargo_bars)`
      following a prior validation fold are marked in `embargoed_after_test` and the next test fold
      advances by at least `step_bars` (defaulting to `test_bars + embargo_bars`).
    """
    if n_bars <= 0 or min_train_bars <= 0 or test_bars <= 0:
        raise ValueError("n_bars, min_train_bars and test_bars must be positive")
    if label_horizon_bars < 1 or embargo_bars < 0:
        raise ValueError("label_horizon_bars >= 1 and embargo_bars >= 0 required")

    effective_step = step_bars if step_bars is not None else (test_bars + embargo_bars)
    if effective_step <= 0:
        raise ValueError("step_bars must be positive")

    splits: list[dict[str, Any]] = []
    test_start = min_train_bars + (label_horizon_bars - 1)
    fold_idx = 0
    while test_start + test_bars <= n_bars:
        test_end = test_start + test_bars
        purge_cutoff = max(0, test_start - label_horizon_bars + 1)
        train_indices = list(range(0, purge_cutoff))
        purged_indices = list(range(purge_cutoff, test_start))
        test_indices = list(range(test_start, test_end))
        embargo_end = min(n_bars, test_end + embargo_bars)
        embargo_indices = list(range(test_end, embargo_end))

        if len(train_indices) >= min_train_bars:
            splits.append(
                {
                    "fold": fold_idx,
                    "train_indices": train_indices,
                    "purged_indices": purged_indices,
                    "test_indices": test_indices,
                    "embargo_indices": embargo_indices,
                }
            )
            fold_idx += 1
        test_start += effective_step
    return splits


def generate_purged_kfold_splits(
    n_bars: int,
    *,
    n_splits: int = 4,
    label_horizon_bars: int = 1,
    embargo_bars: int = 1,
) -> list[dict[str, Any]]:
    """Generate contiguous blocked K-fold splits with pre-test purging and post-test embargo."""
    if n_splits < 2 or n_bars < n_splits * 2:
        raise ValueError("Invalid n_splits or n_bars")

    fold_size = n_bars // n_splits
    splits: list[dict[str, Any]] = []
    for k in range(n_splits):
        test_start = k * fold_size
        test_end = n_bars if k == n_splits - 1 else (k + 1) * fold_size
        purge_start = max(0, test_start - label_horizon_bars + 1)
        embargo_end = min(n_bars, test_end + embargo_bars)

        train_indices = [
            t
            for t in range(n_bars)
            if t < purge_start or t >= embargo_end
        ]
        purged_indices = list(range(purge_start, test_start))
        test_indices = list(range(test_start, test_end))
        embargo_indices = list(range(test_end, embargo_end))
        splits.append(
            {
                "fold": k,
                "train_indices": train_indices,
                "purged_indices": purged_indices,
                "test_indices": test_indices,
                "embargo_indices": embargo_indices,
            }
        )
    return splits


def verify_split_hygiene(
    splits: Sequence[Mapping[str, Any]],
    *,
    label_horizon_bars: int,
    embargo_bars: int,
    require_causal_walk_forward: bool = True,
) -> dict[str, Any]:
    """Audit splits for train-test overlap, forward-label horizon leakage, and embargo violations."""
    violations: list[str] = []
    for sp in splits:
        fold = sp.get("fold", "?")
        train = list(sp["train_indices"])
        test = list(sp["test_indices"])
        if not train or not test:
            violations.append(f"fold_{fold}:empty_train_or_test")
            continue

        train_set = set(train)
        test_set = set(test)
        if train_set & test_set:
            violations.append(f"fold_{fold}:direct_index_overlap")

        test_start = min(test)
        test_end = max(test) + 1
        if require_causal_walk_forward and max(train) >= test_start:
            violations.append(f"fold_{fold}:future_train_index_in_walk_forward")

        for t in train:
            # Horizon [t, t + label_horizon_bars - 1] must not intersect [test_start, test_end - 1]
            t_horizon_end = t + label_horizon_bars
            if t < test_start and t_horizon_end > test_start:
                violations.append(f"fold_{fold}:pre_test_label_horizon_leak_at_{t}")
                break
            if t >= test_end and t < test_end + embargo_bars:
                violations.append(f"fold_{fold}:post_test_embargo_violation_at_{t}")
                break

    return {
        "leakage_free": len(violations) == 0,
        "num_folds": len(splits),
        "violations": violations,
    }
