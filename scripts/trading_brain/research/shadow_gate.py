"""Preregistered Shadow Validation Gate & Access Custody Protocol (Milestone 3.3).

Enforces:
1. Mandatory Preregistration with Sealed Holdout: Findings MUST be preregistered with
   holdout_dataset_id, holdout_dataset_hash, benchmark_metric, and MDE before shadow evaluation.
2. Sealed Holdout Custody: the holdout features and labels are stored in the canonical ledger
   at preregistration time.  At evaluation, the gate loads the sealed holdout, executes the
   preregistered model function on the stored features, and computes the realized metric
   from the stored labels.  Callers cannot submit favorable realized_metric/fdr values.
3. Duplicate Preregistration Protection: Re-registering existing finding_id raises
   PreregistrationConflictError.
4. 1-Time Sealed Evaluation: Terminal states (PROMOTED, REJECTED, INVALID_TEST) cannot be
   re-evaluated.
5. Model ID Binding: Evaluated model must match preregistered model.
6. Minimum Statistical Power >= 0.80 and FDR q <= 0.05 with improvement over benchmark.
"""

import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import numpy as np

from scripts.trading_brain.db.connection import get_db_connection
from scripts.trading_brain.research.sealed_holdout import (
    HoldoutHashMismatchError,
    HoldoutRegistry,
    SealedHoldout,
    compute_binary_accuracy,
    compute_directional_accuracy,
)
from scripts.utils.market_calendar import now_iso_utc


class PreregistrationRequiredError(Exception):
    """Raised when shadow evaluation is attempted without prior preregistration."""
    pass


class PreregistrationConflictError(Exception):
    """Raised when attempting to preregister an existing finding_id."""
    pass


class ShadowGateLockedError(Exception):
    """Raised when an already-evaluated candidate finding in terminal state is re-evaluated."""
    pass


class ModelBindingMismatchError(Exception):
    """Raised when the supplied prediction function does not match the one bound at preregistration.

    The gate executes ONLY the predictor bound at preregistration time (identified by
    module, qualified name, and source hash). Any other callable - including one that
    trivially returns the sealed labels - is refused: an oracle callback would receive
    perfect accuracy regardless of what the registered model artifact actually predicts.
    """
    pass


def _predictor_binding(fn: Callable[[Any], Sequence[Any]]) -> Dict[str, str]:
    """Produces a stable identity binding for a prediction function.

    Identity = module + qualified name + sha256 of source. Callables with the same
    identity execute the same code; an oracle-style replacement fails the hash.
    """
    import inspect
    module = getattr(fn, "__module__", None) or "<unknown>"
    qualname = getattr(fn, "__qualname__", None) or repr(fn)
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        src = ""
    src_hash = hashlib.sha256(src.encode("utf-8")).hexdigest()[:32]
    return {"module": module, "qualname": qualname, "source_hash": f"sha256:{src_hash}"}


def _bindings_match(a: Dict[str, str], b: Dict[str, str]) -> bool:
    """A binding matches when module+qualname+source hash agree (declared, not guessed)."""
    return (
        a.get("module") == b.get("module")
        and a.get("qualname") == b.get("qualname")
        and a.get("source_hash") == b.get("source_hash")
    )


@dataclass
class ShadowEvaluationResult:
    finding_event_id: str
    finding_id: str
    model_version_id: str
    pipeline_stage: str                        # 'PROMOTED', 'INCONCLUSIVE_WAITING', 'REJECTED', 'INVALID_TEST'
    statistical_power: float
    fdr_q_value: float
    realized_metric: float
    benchmark_metric: float
    holdout_dataset_id: str
    holdout_hash: str
    notes: str


class ShadowGate:
    """Evaluates candidate models against sealed shadow data with power and custody enforcement."""

    @staticmethod
    def calculate_statistical_power(
        sample_size: int,
        effect_size_d: float,
        alpha: float = 0.05
    ) -> float:
        """Power for a one-sided z-test at the given standardized effect size.

        `effect_size_d` is interpreted on the metric's own standardized scale. For
        accuracy-like metrics (proportions), callers should pass Cohen's h (arcsine
        effect): h = 2*asin(sqrt(p1)) - 2*asin(sqrt(p0)). Derived from holdout data,
        NOT from the preregistered expectation, so the power statement reflects the
        actually-observed effect.
        """
        if sample_size <= 0 or effect_size_d <= 0:
            return 0.0
        z_alpha = 1.645
        z_score = effect_size_d * math.sqrt(sample_size) - z_alpha
        power = 0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0)))
        return max(0.0, min(1.0, power))

    @staticmethod
    def _cohens_h_from_props(p1: float, p2: float) -> float:
        """Cohen's h: arcsine-transformed difference between two proportions."""
        h = 2.0 * math.asin(math.sqrt(min(max(p1, 0.0), 1.0))) - 2.0 * math.asin(math.sqrt(min(max(p2, 0.0), 1.0)))
        return abs(h)

    @staticmethod
    def _min_improvement_for_effect(benchmark: float, expected_effect_h: float) -> float:
        """Inverts Cohen's h at the preregistered benchmark to the minimum practical
        improvement on the raw metric scale: find p1 > p2=benchmark such that
        h(p1, benchmark) >= expected_effect_h. Binary-search on the raw scale."""
        target = max(expected_effect_h, 0.0)
        if target == 0.0:
            return 0.0
        a2 = math.asin(math.sqrt(min(max(benchmark, 0.0), 1.0)))
        target_phase = a2 + target / 2.0
        if target_phase >= math.pi / 2.0:
            # Effect unattainable below p=1: require the largest attainable improvement.
            p1 = 1.0
        else:
            p1 = math.sin(target_phase) ** 2
        min_p1 = min(max(p1, 0.0), 1.0)
        improvement = min_p1 - benchmark
        return max(improvement, 0.0)

    @staticmethod
    def _compute_fdr_q_value(p_value: float, total_comparisons: int = 1) -> float:
        """Conservative Benjamini-Hochberg for a single family: q = min(1, p * m / rank)."""
        if total_comparisons <= 0:
            total_comparisons = 1
        return min(1.0, p_value * total_comparisons)

    @staticmethod
    def _one_sided_p_value(observed_metric: float, benchmark: float, sample_size: int) -> float:
        """One-sided z-test p-value that the observed proportion exceeds the benchmark.

        Valid for accuracy-like metrics (proportions in [0,1]): SE is computed from the
        OBSERVED proportion under the null (sqrt(p0*(1-p0)/n)), not from a preregistered
        effect size. This is the metric-appropriate test.
        """
        if sample_size <= 0:
            return 1.0
        p0 = min(max(benchmark, 0.0), 1.0)
        se = math.sqrt(p0 * (1.0 - p0) / sample_size)
        if se <= 0:
            # Degenerate benchmark at 0 or 1: any observed excess is decisive.
            return 0.0 if observed_metric > benchmark else 1.0
        z = (observed_metric - benchmark) / se
        p = 1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
        return min(max(p, 0.0), 1.0)

    @classmethod
    def preregister_candidate_finding(
        cls,
        finding_id: str,
        model_version_id: str,
        benchmark_metric: float,
        expected_effect_size_d: float,
        feature_manifest: Dict[str, Any],
        holdout_dataset_id: str,
        holdout_dataset_hash: str,
        metric_kind: str = "DIRECTIONAL_ACCURACY",
        actor: str = "RESEARCH_AGENT",
        db_path: Optional[Union[str, Path]] = None,
        model_predict_fn: Optional[Callable[[Any], Sequence[Any]]] = None,
    ) -> str:
        """Preregisters a candidate finding at discovery time, binding holdout dataset and effect size.

        Predictor binding (anti-oracle): `model_predict_fn` MUST be supplied here; it is
        bound by identity (module, qualified name, source hash) and stored in the
        preregistration payload. Evaluation later refuses any callable that does not
        match this binding, so a caller cannot swap in a callback that returns the
        sealed labels.
        """
        if model_predict_fn is None:
            raise ValueError(
                "preregister_candidate_finding requires model_predict_fn: the predictor "
                "executed at evaluation is bound NOW, not chosen later."
            )
        with get_db_connection(db_path) as conn:
            cur = conn.execute("SELECT finding_id FROM candidate_finding_events WHERE finding_id = ?;", (finding_id,))
            if cur.fetchone():
                raise PreregistrationConflictError(f"Candidate finding '{finding_id}' has already been preregistered.")

            # Sealed-holdout authority check (fail-closed): the caller's benchmark and
            # expected effect MUST equal the values sealed in the holdout registry when
            # the holdout pre-exists. A weak caller benchmark cannot silently replace a
            # stricter sealed one.
            held = HoldoutRegistry.load_holdout(
                holdout_dataset_id=holdout_dataset_id,
                expected_hash=holdout_dataset_hash,
                db_path=db_path,
            )
            if abs(held.benchmark_metric - benchmark_metric) > 1e-9:
                raise ValueError(
                    f"benchmark_metric {benchmark_metric} does not match the sealed holdout "
                    f"registry value {held.benchmark_metric} for '{holdout_dataset_id}'. "
                    "Preregistration must cite the sealed benchmark."
                )
            if abs(held.expected_effect_size_d - expected_effect_size_d) > 1e-9:
                raise ValueError(
                    f"expected_effect_size_d {expected_effect_size_d} does not match the sealed "
                    f"registry value {held.expected_effect_size_d} for '{holdout_dataset_id}'. "
                    "Preregistration must cite the sealed MDE."
                )

            event_id = str(uuid.uuid4())
            eval_json = json.dumps({
                "stage": "PREREGISTERED",
                "model_version_id": model_version_id,
                "benchmark_metric": benchmark_metric,
                "expected_effect_size_d": expected_effect_size_d,
                "metric_kind": metric_kind,
                "holdout_dataset_id": holdout_dataset_id,
                "holdout_dataset_hash": holdout_dataset_hash,
                "feature_manifest": feature_manifest,
                "bound_predictor": _predictor_binding(model_predict_fn),
                "preregistered_at_utc": now_iso_utc()
            })

            conn.execute(
                """
                INSERT INTO candidate_finding_events (
                    finding_event_id, finding_id, model_version_id,
                    pipeline_stage, evaluation_result_json,
                    statistical_power, fdr_q_value, actor, event_timestamp_utc
                ) VALUES (?, ?, ?, 'DISCOVERY', ?, 0.0, 1.0, ?, ?);
                """,
                (event_id, finding_id, model_version_id, eval_json, actor, now_iso_utc())
            )
        return event_id

    @classmethod
    def evaluate_candidate_finding(
        cls,
        finding_id: str,
        model_version_id: str,
        model_predict_fn: Callable[[Any], Sequence[float]],
        sample_size: Optional[int] = None,
        actor: str = "RESEARCH_AGENT",
        db_path: Optional[Union[str, Path]] = None
    ) -> ShadowEvaluationResult:
        """Evaluates a candidate finding on sealed shadow data and transitions candidate_finding_events.

        The realized metric is computed by the gate from the sealed holdout labels and the
        predictions produced by model_predict_fn applied to the sealed holdout features.
        Callers cannot pass in favorable numbers directly.
        """
        with get_db_connection(db_path) as conn:
            cur = conn.execute(
                """
                SELECT * FROM candidate_finding_events
                WHERE finding_id = ?
                ORDER BY event_timestamp_utc DESC, created_at_utc DESC, rowid DESC LIMIT 1;
                """,
                (finding_id,)
            )
            row = cur.fetchone()

            if not row:
                raise PreregistrationRequiredError(
                    f"Candidate finding '{finding_id}' must be preregistered via preregister_candidate_finding() "
                    "before evaluation on sealed shadow data."
                )

            prev_stage = row["pipeline_stage"]
            if prev_stage in ("PROMOTED", "REJECTED", "INVALID_TEST"):
                raise ShadowGateLockedError(
                    f"Candidate finding '{finding_id}' has already been evaluated to terminal stage "
                    f"'{prev_stage}' and cannot be re-evaluated."
                )

            prev_json = json.loads(row["evaluation_result_json"]) if row["evaluation_result_json"] else {}
            prereg_model = prev_json.get("model_version_id", row["model_version_id"])
            if prereg_model != model_version_id:
                raise ValueError(
                    f"Requested model '{model_version_id}' does not match preregistered model '{prereg_model}' "
                    f"for finding '{finding_id}'."
                )

            # Anti-oracle: the executed predictor must be the one bound at
            # preregistration. A different callable (e.g. one returning the sealed
            # labels) is refused outright. Resume contract (F15): an INCONCLUSIVE_WAITING
            # event's payload re-derives its metrics from the holdout registry and does
            # not carry the binding, so on resume fall back to the ORIGINAL
            # preregistration (DISCOVERY) event's bound predictor.
            bound = prev_json.get("bound_predictor")
            if not bound:
                disc = conn.execute(
                    """
                    SELECT evaluation_result_json FROM candidate_finding_events
                    WHERE finding_id = ? AND pipeline_stage = 'DISCOVERY'
                    ORDER BY event_timestamp_utc DESC, rowid ASC LIMIT 1;
                    """,
                    (finding_id,)
                ).fetchone()
                disc_json = json.loads(disc["evaluation_result_json"]) if disc and disc["evaluation_result_json"] else {}
                bound = disc_json.get("bound_predictor")
            if not bound:
                raise ModelBindingMismatchError(
                    f"Candidate finding '{finding_id}' has no bound predictor in any "
                    "preregistration event; re-preregister a binding (anti-oracle custody) "
                    "before evaluation."
                )
            if not _bindings_match(bound, _predictor_binding(model_predict_fn)):
                raise ModelBindingMismatchError(
                    f"Supplied model_predict_fn does not match the predictor bound at "
                    f"preregistration for finding '{finding_id}' "
                    f"(bound={bound.get('module')}.{''.join(bound.get('qualname', ''))}). "
                    "The gate executes ONLY the registered model's bound predictor."
                )

            metric_kind = prev_json.get("metric_kind", "DIRECTIONAL_ACCURACY")
            holdout_dataset_id = prev_json["holdout_dataset_id"]
            preregistered_hash = prev_json.get("holdout_dataset_hash")
            prereg_benchmark = prev_json.get("benchmark_metric")
            if not holdout_dataset_id:
                raise PreregistrationRequiredError(
                    f"Candidate finding '{finding_id}' was preregistered without a sealed holdout_dataset_id."
                )

        # Load sealed holdout outside the candidate row lock.  The registry enforces the hash,
        # and the SEALED REGISTRY values are the authority for benchmark and MDE (F14/F15):
        # evaluation never re-reads them from the preceding event payload, which both stale
        # resume payloads could lack and which a manipulated prereg payload could weaken.
        holdout = HoldoutRegistry.load_holdout(
            holdout_dataset_id=holdout_dataset_id,
            expected_hash=preregistered_hash,
            db_path=db_path,
        )
        sealed_benchmark = holdout.benchmark_metric
        sealed_effect_d = holdout.expected_effect_size_d
        if prereg_benchmark is not None and abs(prereg_benchmark - sealed_benchmark) > 1e-9:
            raise ValueError(
                f"Preregistered benchmark {prereg_benchmark} disagrees with the sealed holdout "
                f"registry value {sealed_benchmark} for '{holdout_dataset_id}'."
            )

        labels = list(holdout.labels)
        n = sample_size if sample_size is not None else len(labels)
        if n > len(labels):
            raise ValueError(f"Requested sample_size {n} exceeds holdout size {len(labels)}.")
        if n <= 0:
            raise ValueError("sample_size must be positive.")

        features_subset = holdout.features[:n] if isinstance(holdout.features, list) else holdout.features
        predictions = list(model_predict_fn(features_subset))
        labels_subset = labels[:n]

        if metric_kind == "DIRECTIONAL_ACCURACY":
            realized_metric = compute_directional_accuracy(predictions, labels_subset)
        elif metric_kind == "BINARY_ACCURACY":
            realized_metric = compute_binary_accuracy(predictions, labels_subset)
        else:
            raise ValueError(f"Unsupported metric_kind: {metric_kind}")

        # Prospective (design) power is FROZEN from the PREREGISTERED effect before any
        # holdout access could influence it (F12): power computed from the observed
        # effect would let an extreme realized result manufacture its own power=1.0.
        # The observed effect is reported as a diagnostic and enforced through the MDE
        # gate below, never through design power.
        design_power = cls.calculate_statistical_power(n, sealed_effect_d)
        observed_h = cls._cohens_h_from_props(realized_metric, sealed_benchmark)
        observed_power = cls.calculate_statistical_power(n, observed_h)
        p_value = cls._one_sided_p_value(realized_metric, sealed_benchmark, n)
        fdr_q_value = cls._compute_fdr_q_value(p_value)
        improvement = realized_metric - sealed_benchmark
        # Preregistered MDE on the raw metric scale: promotion requires the observed
        # improvement to at least meet the preregistered expected effect expressed via
        # Cohen's h inverted back to the accuracy scale (F13).
        min_practical_improvement = cls._min_improvement_for_effect(sealed_benchmark, sealed_effect_d)
        meets_mde = improvement >= min_practical_improvement

        if design_power < 0.80:
            stage = "INCONCLUSIVE_WAITING"
            notes = (
                f"Insufficient PREREGISTERED design power ({design_power:.2f} < 0.80) at N={n} "
                f"frozen before holdout access; observed effect (h={observed_h:.2f}) does not "
                "retroactively power the design. Awaiting unobserved samples."
            )
        elif fdr_q_value <= 0.05 and improvement > 0 and meets_mde:
            stage = "PROMOTED"
            notes = (
                f"Validated on sealed shadow data (DesignPower={design_power:.2f}, FDR q={fdr_q_value:.4f}, "
                f"Metric={realized_metric:.4f} > {sealed_benchmark:.4f}, "
                f"Improvement={improvement:.4f} >= MDE={min_practical_improvement:.4f})."
            )
        else:
            stage = "REJECTED"
            notes = (
                f"Failed criteria on sealed shadow data (FDR q={fdr_q_value:.4f}, "
                f"Metric={realized_metric:.4f}, Improvement={improvement:.4f} vs required MDE="
                f"{min_practical_improvement:.4f})."
            )

        event_id = str(uuid.uuid4())
        eval_json = json.dumps({
            "sample_size": n,
            "realized_metric": realized_metric,
            "benchmark_metric": sealed_benchmark,
            "effect_size_d_preregistered": sealed_effect_d,
            "effect_size_d_observed": observed_h,
            "design_power": design_power,
            "observed_power": observed_power,
            "min_practical_improvement": round(min_practical_improvement, 6),
            "meets_mde": meets_mde,
            "statistical_power": design_power,
            "fdr_q_value": fdr_q_value,
            "holdout_dataset_id": holdout_dataset_id,
            "holdout_hash": holdout.content_hash,
            "metric_kind": metric_kind,
            "decision_notes": notes
        })

        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO candidate_finding_events (
                    finding_event_id, finding_id, model_version_id,
                    pipeline_stage, evaluation_result_json,
                    statistical_power, fdr_q_value, actor, event_timestamp_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (event_id, finding_id, model_version_id, stage, eval_json, design_power, fdr_q_value, actor, now_iso_utc())
            )

        return ShadowEvaluationResult(
            finding_event_id=event_id,
            finding_id=finding_id,
            model_version_id=model_version_id,
            pipeline_stage=stage,
            statistical_power=round(design_power, 4),
            fdr_q_value=round(fdr_q_value, 4),
            realized_metric=realized_metric,
            benchmark_metric=sealed_benchmark,
            holdout_dataset_id=holdout_dataset_id,
            holdout_hash=holdout.content_hash,
            notes=notes
        )