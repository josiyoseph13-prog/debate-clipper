from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .core.io import atomic_write_json


def _features(row: dict[str, Any]) -> dict[str, float]:
    import math
    components = row.get("components", {})
    if isinstance(components, str):
        try:
            components = json.loads(components)
        except json.JSONDecodeError:
            components = {}
    if not components:
        components = {key: row[key] for key in ("narrative", "conflict", "hook", "clarity", "rebuttal", "ending", "context", "acoustic", "crowd") if key in row}
    try:
        result = {key: float(value) for key, value in components.items()}
        return result if result and all(math.isfinite(value) for value in result.values()) else {}
    except (TypeError, ValueError):
        return {}


def _matrix(rows):
    import numpy as np
    features = [_features(row) for row in rows]
    keys = sorted(set.intersection(*(set(row) for row in features))) if features else []
    if not keys:
        raise ValueError("Component vectors are required for every row")
    return np.array([[1.0, *[row[key] for key in keys]] for row in features]), ["intercept", *keys]


def _auc(y, prediction):
    import numpy as np
    positives, negatives = prediction[y == 1], prediction[y == 0]
    if not len(positives) or not len(negatives):
        return None
    pairs = positives[:, None] - negatives[None, :]
    return float(np.mean((pairs > 0).astype(float) + .5 * (pairs == 0)))


def _logistic(x, y, regularization=1.0):
    import numpy as np
    weights = np.zeros(x.shape[1])
    penalty = np.eye(x.shape[1]) * regularization
    penalty[0, 0] = 0
    for _ in range(60):
        probability = 1 / (1 + np.exp(-np.clip(x @ weights, -35, 35)))
        curvature = np.maximum(probability * (1 - probability), 1e-8)
        step = np.linalg.solve(x.T @ (curvature[:, None] * x) + penalty + np.eye(x.shape[1]) * 1e-8, x.T @ (probability - y) + penalty @ weights)
        weights -= step
        if np.max(np.abs(step)) < 1e-7:
            break
    return weights


def import_analytics(csv_path: Path, output_dir: Path, target: str = "avg_percent_watched") -> dict[str, Any]:
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    report = {"schema_version": 5, "rows": len(rows), "status": "proposal_only", "message": "Correlation on your channel, not a virality prediction."}
    if len(rows) < 60:
        report["status"] = "insufficient_data"
        report["message"] = "At least 60 clips are required before ridge/leave-one-out analysis."
    else:
        try:
            import numpy as np
            if len({row.get("clip_id") for row in rows}) != len(rows) or not all(row.get("clip_id") for row in rows):
                raise ValueError("At least 60 distinct clip_id rows are required; aggregate variants per clip")
            x, keys = _matrix(rows)
            y = np.array([float(row[target]) for row in rows])
            if not np.isfinite(y).all():
                raise ValueError("Outcome must be finite")
            penalty = np.eye(x.shape[1])
            penalty[0, 0] = 0
            inverse = np.linalg.pinv(x.T @ x + penalty)
            weights = inverse @ x.T @ y
            fitted = x @ weights
            leverage = np.sum((x @ inverse) * x, axis=1)
            predicted = y - (y - fitted) / np.maximum(1e-9, 1 - leverage)
            cv_mse = float(np.mean((y - predicted) ** 2))
            mean_predictions = (y.sum() - y) / (len(y) - 1)
            baseline_mse = float(np.mean((y - mean_predictions) ** 2))
            rng = np.random.default_rng(7)
            bootstrap = []
            for _ in range(200):
                indices = rng.integers(0, len(rows), len(rows))
                bx, by = x[indices], y[indices]
                bootstrap.append(np.linalg.pinv(bx.T @ bx + penalty) @ bx.T @ by)
            intervals = np.percentile(bootstrap, [2.5, 97.5], axis=0)
            report.update({"target": target, "model": "ridge", "alpha": 1.0, "cv": "leave_one_out", "cv_mse": cv_mse, "mean_baseline_mse": baseline_mse, "eligible": cv_mse < baseline_mse, "coefficients": dict(zip(keys, map(float, weights))), "coefficient_ci95": {key: [float(intervals[0, i]), float(intervals[1, i])] for i, key in enumerate(keys)}, "bootstrap_samples": 200, "applied": False})
            if not report["eligible"]:
                report["status"] = "no_measured_gain"
        except (ValueError, KeyError, TypeError) as exc:
            report.update({"status": "invalid_data", "reason": str(exc)})
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "analytics_proposal.json", report)
    return report


def propose_taste_update(labels: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    # One final vote per candidate; repeated clicks cannot satisfy the gate.
    unique = {}
    for row in labels:
        if row.get("action") in {"approve", "reject"} and row.get("candidate_id") and _features(row):
            unique[(row.get("job_id"), row["candidate_id"])] = row
    rows = list(unique.values())
    result = {"schema_version": 5, "labels": len(rows), "status": "insufficient_data", "enabled": False, "reason": "Need 150 distinct candidate decisions and CV AUC >=0.70; user approval is required.", "applied": False}
    if len(rows) >= 150:
        import numpy as np
        x, keys = _matrix(rows)
        y = np.array([int(row["action"] == "approve") for row in rows])
        if min(int(y.sum()), len(y) - int(y.sum())) < 5:
            result["reason"] = "At least five observations of each outcome are needed for 5-fold CV"
        else:
            rng = np.random.default_rng(7)
            folds = [[] for _ in range(5)]
            for outcome in (0, 1):
                indices = np.flatnonzero(y == outcome)
                rng.shuffle(indices)
                for i, index in enumerate(indices):
                    folds[i % 5].append(index)
            predictions = np.zeros(len(y))
            for fold in folds:
                heldout = np.array(fold)
                train = np.ones(len(y), dtype=bool)
                train[heldout] = False
                weights = _logistic(x[train], y[train])
                predictions[heldout] = 1 / (1 + np.exp(-np.clip(x[heldout] @ weights, -35, 35)))
            auc = _auc(y, predictions)
            weights = _logistic(x, y)
            result.update({"status": "proposal_only" if auc >= .70 else "gate_failed", "cv_auc": auc, "cv": "stratified_5_fold", "eligible": auc >= .70, "coefficients": dict(zip(keys, map(float, weights))), "regularization": 1.0, "max_blend": .30, "reason": "CV measured; proposal is not applied to ranking"})
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "taste_proposal.json", result)
    return result


def propose_boundary_bias(labels:list[dict],output_dir:Path)->dict:
    import statistics
    unique={}
    for row in labels:
        if row.get("edits") and "proposed_start" in row:
            unique[(row.get("job_id"),row.get("candidate_id"))]=row
    rows=list(unique.values())
    biases={}
    for key in ("start","end"):
        deltas=[float(row["edits"][key])-float(row["proposed_"+key]) for row in rows if key in row["edits"] and row.get("proposed_"+key) is not None]
        median=statistics.median(deltas) if deltas else None
        biases[key]={"edits":len(deltas),"median_seconds":median,"propose":len(deltas)>=30 and abs(median)>=.08}
    result={"schema_version":5,"biases":biases,"applied":False}
    output_dir.mkdir(parents=True,exist_ok=True)
    atomic_write_json(output_dir/"boundary_bias_proposal.json",result)
    return result
