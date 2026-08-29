"""Sealed holdout registry for the Shadow Validation Gate.

A holdout is a frozen feature/label set registered at discovery/preregistration time.
The registry stores:
  - holdout_dataset_id (caller-chosen, unique)
  - content_hash (sha256 of serialized X + y)
  - serialized features and labels (JSON for small/tabular data)
  - expected benchmark metric and minimum detectable effect size

The ShadowGate loads the holdout at evaluation time, executes the preregistered model
function against the stored features, and computes the realized metric from the stored
labels.  This prevents a caller from submitting favorable numbers directly.
"""

import hashlib
import json
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import numpy as np

from scripts.trading_brain.db.connection import get_db_connection
from scripts.utils.market_calendar import now_iso_utc


class HoldoutHashMismatchError(Exception):
    """Raised when a sealed holdout's content hash does not match the preregistered hash."""
    pass


@dataclass
class SealedHoldout:
    holdout_dataset_id: str
    content_hash: str
    features: Any  # JSON-serializable (list of lists/dicts)
    labels: Sequence[float]
    benchmark_metric: float
    expected_effect_size_d: float
    registered_at_utc: str


class HoldoutRegistry:
    """Stores and retrieves sealed holdout datasets in the canonical SQLite ledger."""

    @classmethod
    def register_holdout(
        cls,
        holdout_dataset_id: str,
        features: Any,
        labels: Sequence[float],
        benchmark_metric: float,
        expected_effect_size_d: float,
        db_path: Optional[Union[str, Path]] = None,
    ) -> str:
        payload = json.dumps({"features": features, "labels": list(labels)}, sort_keys=True, default=str)
        content_hash = f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:32]}"
        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO sealed_holdouts (
                    holdout_dataset_id, content_hash, features_json, labels_json,
                    benchmark_metric, expected_effect_size_d, registered_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(holdout_dataset_id) DO NOTHING;
                """,
                (
                    holdout_dataset_id, content_hash, json.dumps(features, default=str),
                    json.dumps(list(labels), default=str), benchmark_metric,
                    expected_effect_size_d, now_iso_utc()
                )
            )
        return content_hash

    @classmethod
    def load_holdout(
        cls,
        holdout_dataset_id: str,
        expected_hash: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None,
    ) -> SealedHoldout:
        with get_db_connection(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sealed_holdouts WHERE holdout_dataset_id = ?;",
                (holdout_dataset_id,)
            ).fetchone()
        if not row:
            raise ValueError(f"Sealed holdout '{holdout_dataset_id}' not found.  It must be registered before shadow evaluation.")
        if expected_hash and row["content_hash"] != expected_hash:
            raise HoldoutHashMismatchError(
                f"Holdout hash mismatch for '{holdout_dataset_id}': expected {expected_hash}, got {row['content_hash']}"
            )
        return SealedHoldout(
            holdout_dataset_id=row["holdout_dataset_id"],
            content_hash=row["content_hash"],
            features=json.loads(row["features_json"]),
            labels=json.loads(row["labels_json"]),
            benchmark_metric=float(row["benchmark_metric"]),
            expected_effect_size_d=float(row["expected_effect_size_d"]),
            registered_at_utc=row["registered_at_utc"],
        )


def compute_binary_accuracy(predictions: Sequence[float], labels: Sequence[float]) -> float:
    """Accuracy for binary {0,1} predictions and labels."""
    if len(predictions) != len(labels):
        raise ValueError("Predictions and labels length mismatch.")
    if not predictions:
        return 0.0
    pred_bin = [1 if float(p) >= 0.5 else 0 for p in predictions]
    label_bin = [int(l) for l in labels]
    correct = sum(1 for p, l in zip(pred_bin, label_bin) if p == l)
    return correct / len(pred_bin)


def compute_directional_accuracy(predicted_direction: Sequence[str], actual_direction: Sequence[str]) -> float:
    """Accuracy for directional strings ('LONG'/'SHORT'/'NEUTRAL')."""
    if len(predicted_direction) != len(actual_direction):
        raise ValueError("Prediction/label length mismatch.")
    if not predicted_direction:
        return 0.0
    correct = sum(1 for p, l in zip(predicted_direction, actual_direction) if p.upper() == l.upper())
    return correct / len(predicted_direction)