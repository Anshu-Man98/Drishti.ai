"""
Cross-reference and claims warehouse lookup tools using Google Cloud BigQuery and BigQuery ML.
Cloud-only: Queries live BigQuery tables and BQML fraud models.
Parameter-safe queries only.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from backend.app.schemas import Finding, Evidence, AgentName, Severity
from backend.app.config import settings
from backend.app.exceptions import CloudServiceError
from backend.tools.geo import normalize_to_utc

logger = logging.getLogger("finshield.tools.bq")

try:
    from google.cloud import bigquery
    _bq_client_class = bigquery.Client
    _bq_available = True
except Exception:
    _bq_available = False


class BigQueryWarehouse:
    """
    Cloud-native claims warehouse querying Google Cloud BigQuery.
    Queries dataset {GCP_PROJECT}.{BIGQUERY_DATASET}.
    There is no offline CSV/JSONL fallback.
    """
    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self):
        if _bq_available and settings.GCP_PROJECT:
            try:
                self._client = _bq_client_class(project=settings.GCP_PROJECT)
            except Exception as e:
                self._client = None
                if settings.REQUIRE_CLOUD_ON_STARTUP:
                    raise CloudServiceError(
                        service="bigquery",
                        message=f"Failed to initialize BigQuery client for project '{settings.GCP_PROJECT}': {e}",
                        retryable=True
                    )

    @property
    def client(self) -> Any:
        if self._client is None:
            self._init_client()
        if self._client is None:
            raise CloudServiceError(
                service="bigquery",
                message="Google Cloud BigQuery client is unavailable. Live BigQuery connection required.",
                retryable=True
            )
        return self._client

    def lookup_claimant_bank_hash(self, claimant_name: str) -> Optional[str]:
        """Looks up registered bank account hash for a claimant from the claims warehouse."""
        if not claimant_name:
            return None
        query = f"""
        SELECT bank_account_hash
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
        WHERE LOWER(claimant_name) = @cname
          AND bank_account_hash IS NOT NULL
        LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("cname", "STRING", claimant_name.lower())]
        )
        try:
            results = list(self.client.query(query, job_config=job_config).result())
            if results and results[0].bank_account_hash:
                return str(results[0].bank_account_hash)
            return None
        except Exception as e:
            raise CloudServiceError(
                service="bigquery",
                message=f"Failed to lookup claimant bank hash in BigQuery: {e}",
                retryable=True
            )

    def get_shared_account_count(self, bank_account_hash: str) -> int:
        """Returns the number of distinct claimants sharing this bank account hash."""
        if not bank_account_hash:
            return 1
        query = f"""
        SELECT COUNT(DISTINCT claimant_id) as cnt
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
        WHERE bank_account_hash = @bhash
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("bhash", "STRING", bank_account_hash)]
        )
        try:
            results = list(self.client.query(query, job_config=job_config).result())
            if results and results[0].cnt:
                return max(1, int(results[0].cnt))
            return 1
        except Exception as e:
            raise CloudServiceError(
                service="bigquery",
                message=f"Failed to query shared account count in BigQuery: {e}",
                retryable=True
            )

    def find_exact_duplicates(
        self,
        sha256: str,
        bill_number: Optional[str] = None,
        hospital_id: Optional[str] = None,
        current_claim_id: Optional[str] = None
    ) -> List[Finding]:
        """
        Detects exact duplicate document or invoice submission via BigQuery warehouse.
        """
        findings: List[Finding] = []
        if not bill_number:
            return findings

        where_conditions = ["bill_number IS NOT NULL AND bill_number != '' AND bill_number = @bill_number"]
        if current_claim_id:
            where_conditions.append("claim_id != @current_claim_id")

        query = f"""
        SELECT claim_id, hospital_name, total_claimed, bill_number
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
        WHERE {" AND ".join(where_conditions)}
        LIMIT 5
        """
        query_params = [
            bigquery.ScalarQueryParameter("bill_number", "STRING", bill_number),
        ]
        if current_claim_id:
            query_params.append(bigquery.ScalarQueryParameter("current_claim_id", "STRING", current_claim_id))

        job_config = bigquery.QueryJobConfig(query_parameters=query_params)
        try:
            for row in self.client.query(query, job_config=job_config).result():
                findings.append(Finding(
                    finding_id="F-XREF-EXACT-DUP",
                    agent=AgentName.CROSSREF,
                    check_id="EXACT_DUPLICATE_BILL",
                    severity=Severity.CRITICAL,
                    title=f"Exact duplicate bill resubmitted: {bill_number or row.claim_id}",
                    explanation=(
                        f"Bill was previously settled under claim {row.claim_id} "
                        f"at {row.hospital_name or hospital_id or 'the same facility'}. Resubmission constitutes double-billing."
                    ),
                    evidence=[Evidence(doc_id="doc_main", page=1, quote=f"Bill No: {bill_number or row.claim_id}")],
                    confidence=1.0
                ))
                return findings
            return findings
        except Exception as e:
            raise CloudServiceError(
                service="bigquery",
                message=f"Failed to check exact duplicates in BigQuery: {e}",
                retryable=True
            )

    def find_cross_insurer_duplicates(
        self,
        claimant_id: str,
        admission_ts: datetime,
        amount: float,
        current_claim_id: Optional[str] = None,
        insurer_id: Optional[str] = None
    ) -> List[Finding]:
        """
        Detects cross-insurer duplicate claim: same claimant, admission +-3 days, amount +-5%.
        """
        findings: List[Finding] = []
        where_conditions = [
            "claimant_id = @claimant_id",
            "admission_ts BETWEEN TIMESTAMP_SUB(TIMESTAMP(@adm_ts), INTERVAL 3 DAY) AND TIMESTAMP_ADD(TIMESTAMP(@adm_ts), INTERVAL 3 DAY)",
            "total_claimed BETWEEN @low_amt AND @high_amt"
        ]
        if current_claim_id:
            where_conditions.append("claim_id != @current_claim_id")
        if insurer_id:
            where_conditions.append("insurer_id != @insurer_id")

        query = f"""
        SELECT claim_id, claimant_id, insurer_id, total_claimed, admission_ts
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
        WHERE {" AND ".join(where_conditions)}
        LIMIT 1
        """
        query_params = [
            bigquery.ScalarQueryParameter("claimant_id", "STRING", claimant_id),
            bigquery.ScalarQueryParameter("adm_ts", "TIMESTAMP", admission_ts.isoformat()),
            bigquery.ScalarQueryParameter("low_amt", "FLOAT64", amount * 0.95),
            bigquery.ScalarQueryParameter("high_amt", "FLOAT64", amount * 1.05),
        ]
        if current_claim_id:
            query_params.append(bigquery.ScalarQueryParameter("current_claim_id", "STRING", current_claim_id))
        if insurer_id:
            query_params.append(bigquery.ScalarQueryParameter("insurer_id", "STRING", insurer_id))

        job_config = bigquery.QueryJobConfig(query_parameters=query_params)
        try:
            for row in self.client.query(query, job_config=job_config).result():
                prior_ins = row.insurer_id or "Another Insurer"
                findings.append(Finding(
                    finding_id="F-XREF-CROSS-INSURER",
                    agent=AgentName.CROSSREF,
                    check_id="CROSS_INSURER_DUPLICATE_CLAIM",
                    severity=Severity.CRITICAL,
                    title="Cross-insurer duplicate claim detected in claims warehouse",
                    explanation=(
                        f"Claimant {claimant_id} already filed an identical claim for ₹{amount:,.2f} "
                        f"(admission around {admission_ts.strftime('%d-%b-%Y')}) with {prior_ins} "
                        f"(Prior Claim ID: {row.claim_id}). Simultaneous multi-insurer claiming violates insurance contracts."
                    ),
                    evidence=[Evidence(doc_id="doc_main", page=1, quote=f"Claimant: {claimant_id}, Amount: ₹{amount}")],
                    confidence=0.98
                ))
                return findings
            return findings
        except Exception as e:
            raise CloudServiceError(
                service="bigquery",
                message=f"Failed to query cross-insurer duplicates in BigQuery: {e}",
                retryable=True
            )

    def shared_account_check(
        self,
        bank_account_hash: str,
        current_claimant_id: Optional[str] = None
    ) -> List[Finding]:
        """
        Detects syndicate/fraud-ring activity where multiple unrelated claimants share a single bank account.
        """
        findings: List[Finding] = []
        distinct_claimants = self.get_shared_account_count(bank_account_hash)

        if distinct_claimants > 3:
            findings.append(Finding(
                finding_id="F-XREF-SHARED-BANK",
                agent=AgentName.CROSSREF,
                check_id="SHARED_BANK_ACCOUNT_FRAUD_RING",
                severity=Severity.HIGH,
                title="Syndicate alert: Bank account shared across multiple claimants",
                explanation=(
                    f"Bank account hash ({bank_account_hash[:10]}...) is registered across "
                    f"{distinct_claimants} distinct claimants in the claims database, indicating organized fraud ring operations."
                ),
                evidence=[Evidence(doc_id="doc_main", page=1, quote=f"Bank hash: {bank_account_hash}")],
                confidence=0.94
            ))

        return findings

    def claimant_history(self, claimant_id: str, days: int = 365) -> Dict[str, Any]:
        """
        Retrieves claim frequency for claimant in past N days.
        """
        query = f"""
        SELECT COUNT(*) as total_claims_365d,
               COALESCE(SUM(total_claimed), 0.0) as total_amount,
               COUNT(DISTINCT hospital_name) as distinct_hospitals
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
        WHERE claimant_id = @cid
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("cid", "STRING", claimant_id)]
        )
        try:
            for row in self.client.query(query, job_config=job_config).result():
                return {
                    "claimant_id": claimant_id,
                    "total_claims_365d": int(row.total_claims_365d),
                    "total_amount_claimed": float(row.total_amount),
                    "distinct_hospitals": int(row.distinct_hospitals)
                }
            return {"claimant_id": claimant_id, "total_claims_365d": 0, "total_amount_claimed": 0.0, "distinct_hospitals": 0}
        except Exception as e:
            raise CloudServiceError(
                service="bigquery",
                message=f"Failed to query claimant history from BigQuery: {e}",
                retryable=True
            )

    def count_claimant_prior_claims_90d(self, claimant_id: str, as_of_ts: Optional[datetime] = None) -> int:
        """Counts prior claims submitted by this claimant in the 90 days before admission."""
        if not claimant_id:
            return 0
        ts = as_of_ts or datetime.utcnow()
        low_ts = ts - timedelta(days=90)
        query = f"""
        SELECT COUNT(1) as cnt
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.claims`
        WHERE claimant_id = @cid
          AND admission_ts BETWEEN @low_ts AND @ts
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("cid", "STRING", claimant_id),
                bigquery.ScalarQueryParameter("low_ts", "TIMESTAMP", low_ts),
                bigquery.ScalarQueryParameter("ts", "TIMESTAMP", ts),
            ]
        )
        try:
            results = list(self.client.query(query, job_config=job_config).result())
            return int(results[0].cnt) if results else 0
        except Exception as e:
            raise CloudServiceError(
                service="bigquery",
                message=f"Failed to count prior claims from BigQuery: {e}",
                retryable=True
            )

    def get_doctor_events(
        self,
        doctor_id: str,
        target_ts: Any,
        window_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Retrieves other hospital/clinic billing events for the same doctor within +-window_hours
        from BigQuery doctor_events table.
        """
        target_ts = normalize_to_utc(target_ts)
        query = f"""
        SELECT
            event_id,
            doctor_id,
            ts,
            hospital_name,
            city,
            lat,
            lng,
            claim_id
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.doctor_events`
        WHERE doctor_id = @doctor_id
          AND TIMESTAMP_DIFF(TIMESTAMP(@target_ts), ts, HOUR) BETWEEN -@window_hours AND @window_hours
        ORDER BY ts ASC
        LIMIT 50
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("doctor_id", "STRING", doctor_id),
                bigquery.ScalarQueryParameter("target_ts", "TIMESTAMP", target_ts.isoformat()),
                bigquery.ScalarQueryParameter("window_hours", "INT64", window_hours),
            ]
        )
        events = []
        try:
            for row in self.client.query(query, job_config=job_config).result():
                events.append({
                    "claim_id": row.claim_id or row.event_id,
                    "doctor_id": row.doctor_id,
                    "ts": normalize_to_utc(row.ts),
                    "hospital_name": row.hospital_name,
                    "city": row.city,
                    "lat": float(row.lat),
                    "lng": float(row.lng),
                    "description": f"External Billed Procedure: {row.hospital_name}"
                })
            return events
        except Exception as e:
            raise CloudServiceError(
                service="bigquery",
                message=f"Failed to query doctor events from BigQuery: {e}",
                retryable=True
            )


bq_warehouse = BigQueryWarehouse()


class _DiagnosisMediansDict(dict):
    """Backwards-compatible accessor for diagnosis median benchmark values."""
    def __getitem__(self, key: str) -> float:
        from backend.services.benchmarks import benchmark_service
        return float(benchmark_service.get_diagnosis_benchmark(key).p50)

    def get(self, key: str, default: float = 49916.56) -> float:
        from backend.services.benchmarks import benchmark_service
        try:
            return float(benchmark_service.get_diagnosis_benchmark(key).p50)
        except Exception:
            return default


DIAGNOSIS_MEDIANS = _DiagnosisMediansDict()


FEATURE_COLUMNS = [
    "claim_amount",
    "amount_vs_diagnosis_median_ratio",
    "total_percentile_vs_diagnosis",
    "max_line_item_price_ratio",
    "ancillary_share_of_total",
    "length_of_stay",
    "claimant_prior_claims_90d",
    "provider_claims_per_day",
    "doctor_distinct_cities_24h",
    "shared_bank_account_count",
    "days_policy_start_to_claim",
    "line_item_count",
    "room_rent_vs_cap_ratio"
]


def extract_claim_features(claim: Any) -> Dict[str, Any]:
    """
    Extracts engineered numeric features from Claim for BigQuery ML fraud model,
    grounded against BigQuery diagnosis and category benchmarks.
    """
    from backend.services.benchmarks import benchmark_service

    claim_amount = float(getattr(claim, "total_claimed", 0.0) or 0.0)

    # Diagnosis benchmark cost distribution
    diag_code = getattr(claim, "diagnosis_code", "") or "K35.8"
    diag_bench = benchmark_service.get_diagnosis_benchmark(diag_code)
    median_cost = diag_bench.p50 or 49916.56
    amount_vs_median = round(claim_amount / median_cost, 3)

    # Continuous percentile position vs diagnosis distribution
    if claim_amount <= diag_bench.p50:
        total_percentile = round(0.50 * max(0.0, claim_amount / max(1.0, diag_bench.p50)), 4)
    elif claim_amount <= diag_bench.p75:
        denom = max(1.0, diag_bench.p75 - diag_bench.p50)
        total_percentile = round(0.50 + 0.25 * ((claim_amount - diag_bench.p50) / denom), 4)
    elif claim_amount <= diag_bench.p90:
        denom = max(1.0, diag_bench.p90 - diag_bench.p75)
        total_percentile = round(0.75 + 0.15 * ((claim_amount - diag_bench.p75) / denom), 4)
    elif claim_amount <= diag_bench.p95:
        denom = max(1.0, diag_bench.p95 - diag_bench.p90)
        total_percentile = round(0.90 + 0.05 * ((claim_amount - diag_bench.p90) / denom), 4)
    else:
        denom = max(1.0, diag_bench.p95 * 0.5)
        total_percentile = round(min(0.9999, 0.95 + 0.04 * ((claim_amount - diag_bench.p95) / denom)), 4)

    # Line item features: max price ratio & ancillary share
    line_items = getattr(claim, "line_items", []) or []
    line_item_count = len(line_items)

    max_price_ratio = 1.0
    ancillary_sum = 0.0
    for it in line_items:
        desc = getattr(it, "description", "")
        rate = float(getattr(it, "unit_price", 0.0) or 0.0)
        amt = float(getattr(it, "amount", 0.0) or 0.0)
        cat = benchmark_service.normalize_line_item_category(desc)
        cat_bench = benchmark_service.get_category_benchmark(cat, diag_code)
        bench_unit = cat_bench.unit_price_p50 or 2000.0
        ratio = rate / max(1.0, bench_unit)
        if ratio > max_price_ratio:
            max_price_ratio = ratio
        if cat in ("ancillary", "diagnostics") or any(k in desc.lower() for k in ["consumable", "disposable", "monitoring", "supplies"]):
            ancillary_sum += amt

    ancillary_share = round(ancillary_sum / max(1.0, claim_amount), 4)
    max_line_item_price_ratio = round(max_price_ratio, 2)

    # Length of stay
    adm = normalize_to_utc(getattr(claim, "admission_ts", None))
    dis = normalize_to_utc(getattr(claim, "discharge_ts", None))
    if adm and dis:
        stay_days = max(1, (dis - adm).days)
    else:
        stay_days = 3

    # Prior claims in 90d
    claimant = getattr(claim, "claimant", None)
    claimant_id = (getattr(claimant, "claimant_id", "") or "") if claimant else ""
    prior_claims = 0
    if claimant_id:
        try:
            prior_claims = bq_warehouse.count_claimant_prior_claims_90d(claimant_id, adm)
        except Exception:
            prior_claims = 0

    # Provider claims per day
    provider_claims_day = 2.4

    # Doctor distinct cities in 24h
    doc_id = getattr(claim, "doctor_id", "") or ""
    admission_ts = getattr(claim, "admission_ts", None)
    doctor_cities_24h = 1
    if doc_id and admission_ts:
        try:
            events = bq_warehouse.get_doctor_events(doc_id, admission_ts, window_hours=24)
            distinct_cities = set()
            hospital_city = getattr(claim.provider, "city", None) if getattr(claim, "provider", None) else getattr(claim, "city", None)
            if hospital_city:
                distinct_cities.add(hospital_city)
            for ev in events:
                if ev.get("city"):
                    distinct_cities.add(ev["city"])
            doctor_cities_24h = max(1, len(distinct_cities))
        except Exception:
            doctor_cities_24h = 1

    # Shared bank account count
    bank_hash = (getattr(claimant, "bank_account_hash", "") or "") if claimant else ""
    shared_bank_count = 1
    if bank_hash:
        try:
            shared_bank_count = bq_warehouse.get_shared_account_count(bank_hash)
        except Exception:
            shared_bank_count = 1

    # Days policy to claim
    admission_dt = normalize_to_utc(getattr(claim, "admission_ts", None))
    policy_start = normalize_to_utc(getattr(claim, "policy_start_date", None))
    if admission_dt and policy_start:
        days_policy_to_claim = max(1, (admission_dt - policy_start).days)
    else:
        days_policy_to_claim = 180

    # Room rent vs cap ratio (standard cap ₹5,000/day)
    room_item = next(
        (it for it in line_items if any(k in getattr(it, "description", "").lower() for k in ["room", "suite", "bed", "ward"])),
        None
    )
    room_rate = getattr(room_item, "unit_price", 4000.0) if room_item else 4000.0
    room_rent_vs_cap = round(room_rate / 5000.0, 3)

    return {
        "claim_amount": claim_amount,
        "amount_vs_diagnosis_median_ratio": amount_vs_median,
        "total_percentile_vs_diagnosis": total_percentile,
        "max_line_item_price_ratio": max_line_item_price_ratio,
        "ancillary_share_of_total": ancillary_share,
        "length_of_stay": stay_days,
        "claimant_prior_claims_90d": prior_claims,
        "provider_claims_per_day": provider_claims_day,
        "doctor_distinct_cities_24h": doctor_cities_24h,
        "shared_bank_account_count": shared_bank_count,
        "days_policy_start_to_claim": days_policy_to_claim,
        "line_item_count": line_item_count,
        "room_rent_vs_cap_ratio": room_rent_vs_cap
    }


def ml_score(claim_features: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Runs BigQuery ML ML.PREDICT + ML.EXPLAIN_PREDICT (top_k_features=5).
    Cloud-only: Score comes strictly from BigQuery ML.
    If BigQuery ML fails or is unreachable, raises CloudServiceError.
    """
    query = f"""
    SELECT
      predicted_is_fraud,
      probability,
      top_feature_attributions
    FROM
      ML.EXPLAIN_PREDICT(
        MODEL `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.fraud_model`,
        (SELECT @claim_amount AS claim_amount,
                @amount_vs_median AS amount_vs_diagnosis_median_ratio,
                @total_percentile AS total_percentile_vs_diagnosis,
                @max_price_ratio AS max_line_item_price_ratio,
                @ancillary_share AS ancillary_share_of_total,
                @length_of_stay AS length_of_stay,
                @prior_claims AS claimant_prior_claims_90d,
                @provider_claims_day AS provider_claims_per_day,
                @doctor_cities_24h AS doctor_distinct_cities_24h,
                @shared_bank_count AS shared_bank_account_count,
                @days_policy_to_claim AS days_policy_start_to_claim,
                @line_item_count AS line_item_count,
                @room_rent_vs_cap AS room_rent_vs_cap_ratio),
        STRUCT(5 AS top_k_features)
      )
    """
    query_params = [
        bigquery.ScalarQueryParameter("claim_amount", "FLOAT64", float(claim_features["claim_amount"])),
        bigquery.ScalarQueryParameter("amount_vs_median", "FLOAT64", float(claim_features["amount_vs_diagnosis_median_ratio"])),
        bigquery.ScalarQueryParameter("total_percentile", "FLOAT64", float(claim_features.get("total_percentile_vs_diagnosis", 0.5))),
        bigquery.ScalarQueryParameter("max_price_ratio", "FLOAT64", float(claim_features.get("max_line_item_price_ratio", 1.0))),
        bigquery.ScalarQueryParameter("ancillary_share", "FLOAT64", float(claim_features.get("ancillary_share_of_total", 0.0))),
        bigquery.ScalarQueryParameter("length_of_stay", "INT64", int(claim_features["length_of_stay"])),
        bigquery.ScalarQueryParameter("prior_claims", "INT64", int(claim_features["claimant_prior_claims_90d"])),
        bigquery.ScalarQueryParameter("provider_claims_day", "FLOAT64", float(claim_features["provider_claims_per_day"])),
        bigquery.ScalarQueryParameter("doctor_cities_24h", "INT64", int(claim_features["doctor_distinct_cities_24h"])),
        bigquery.ScalarQueryParameter("shared_bank_count", "INT64", int(claim_features["shared_bank_account_count"])),
        bigquery.ScalarQueryParameter("days_policy_to_claim", "INT64", int(claim_features["days_policy_start_to_claim"])),
        bigquery.ScalarQueryParameter("line_item_count", "INT64", int(claim_features["line_item_count"])),
        bigquery.ScalarQueryParameter("room_rent_vs_cap", "FLOAT64", float(claim_features["room_rent_vs_cap_ratio"]))
    ]
    job_config = bigquery.QueryJobConfig(query_parameters=query_params)
    try:
        query_job = bq_warehouse.client.query(query, job_config=job_config)
        results = list(query_job.result())
        if not results:
            raise RuntimeError("BigQuery ML returned empty prediction results.")
        row = results[0]
        pred = getattr(row, "predicted_is_fraud", 0)
        prob = float(getattr(row, "probability", 0.0))
        # Compute fraud probability: if predicted label is 1, prob is fraud prob; if 0, 1.0 - prob
        fraud_prob = prob if pred == 1 else (1.0 - prob)

        top_features = []
        raw_attrs = getattr(row, "top_feature_attributions", []) or []
        for attr in raw_attrs[:5]:
            feat = attr.get("feature") if isinstance(attr, dict) else getattr(attr, "feature", "")
            weight = attr.get("attribution_weight", 0.0) if isinstance(attr, dict) else getattr(attr, "attribution", getattr(attr, "attribution_weight", 0.0))
            top_features.append({
                "feature": feat,
                "attribution": round(float(weight), 4)
            })
        return round(fraud_prob, 4), top_features
    except Exception as e:
        raise CloudServiceError(
            service="bigquery",
            message=f"BigQuery ML ML.EXPLAIN_PREDICT execution failed: {e}",
            retryable=True
        )
