"""
FinShield Operational Metrics & Telemetry Service.

Tracks in-process operational metrics for live observability:
- Total claims analyzed
- Success / failure counts & error rate
- Latency percentiles (p50, p95, avg, min, max)
- Total LLM tokens used (Gemini prompt + completion)
- Total BigQuery bytes scanned / billed
- Uptime and recent request counters
"""

import time
import threading
from typing import Dict, List, Any


class MetricsService:
    def __init__(self):
        self._mutex = threading.Lock()
        self._start_time = time.time()
        self._total_claims_analyzed: int = 0
        self._successful_analyses: int = 0
        self._failed_analyses: int = 0
        self._latencies: List[float] = []
        self._total_llm_tokens: int = 0
        self._total_bq_bytes_billed: int = 0

    def record_analysis(self, latency_seconds: float, success: bool = True, tokens: int = 0, bq_bytes: int = 0) -> None:
        try:
            tokens_val = int(tokens)
        except (TypeError, ValueError):
            tokens_val = 0
        try:
            bq_val = int(bq_bytes)
        except (TypeError, ValueError):
            bq_val = 0

        with self._mutex:
            self._total_claims_analyzed += 1
            if success:
                self._successful_analyses += 1
            else:
                self._failed_analyses += 1
            self._latencies.append(latency_seconds)
            # Keep rolling window of last 1000 latencies
            if len(self._latencies) > 1000:
                self._latencies = self._latencies[-1000:]
            if tokens_val > 0:
                self._total_llm_tokens += tokens_val
            if bq_val > 0:
                self._total_bq_bytes_billed += bq_val

    def record_llm_tokens(self, tokens: int) -> None:
        try:
            val = int(tokens)
        except (TypeError, ValueError):
            return
        with self._mutex:
            self._total_llm_tokens += val

    def record_bq_bytes(self, bq_bytes: int) -> None:
        try:
            val = int(bq_bytes)
        except (TypeError, ValueError):
            return
        with self._mutex:
            self._total_bq_bytes_billed += val

    def get_metrics(self) -> Dict[str, Any]:
        with self._mutex:
            total = self._total_claims_analyzed
            err_rate = (self._failed_analyses / total) if total > 0 else 0.0

            if self._latencies:
                sorted_lats = sorted(self._latencies)
                n = len(sorted_lats)
                p50_idx = int(0.50 * n)
                p95_idx = min(n - 1, int(0.95 * n))
                p50 = round(sorted_lats[p50_idx], 3)
                p95 = round(sorted_lats[p95_idx], 3)
                avg_lat = round(sum(sorted_lats) / n, 3)
                min_lat = round(sorted_lats[0], 3)
                max_lat = round(sorted_lats[-1], 3)
            else:
                p50 = 0.0
                p95 = 0.0
                avg_lat = 0.0
                min_lat = 0.0
                max_lat = 0.0

            uptime = round(time.time() - self._start_time, 1)

            # Query token_budget_tracker for global LLM stats
            try:
                from backend.app.services.token_budget import token_budget_tracker
                token_usage = token_budget_tracker.get_global_usage()
                tokens_reported = max(self._total_llm_tokens, token_usage.get("total_tokens", 0))
                cost_usd = token_usage.get("total_cost_usd", 0.0)
            except Exception:
                tokens_reported = self._total_llm_tokens
                cost_usd = 0.0

            return {
                "total_claims_analyzed": total,
                "successful_analyses": self._successful_analyses,
                "failed_analyses": self._failed_analyses,
                "error_rate": round(err_rate, 4),
                "latency_p50_seconds": p50,
                "latency_p95_seconds": p95,
                "latency_avg_seconds": avg_lat,
                "latency_min_seconds": min_lat,
                "latency_max_seconds": max_lat,
                "total_llm_tokens": tokens_reported,
                "total_llm_cost_usd": cost_usd,
                "total_bq_bytes_billed": self._total_bq_bytes_billed,
                "total_bq_mb_billed": round(self._total_bq_bytes_billed / (1024 * 1024), 2),
                "uptime_seconds": uptime
            }

    def clear(self) -> None:
        with self._mutex:
            self._total_claims_analyzed = 0
            self._successful_analyses = 0
            self._failed_analyses = 0
            self._latencies.clear()
            self._total_llm_tokens = 0
            self._total_bq_bytes_billed = 0


metrics_service = MetricsService()
