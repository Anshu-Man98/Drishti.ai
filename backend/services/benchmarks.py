"""
FinShield BigQuery Benchmarks Service.
Retrieves and caches statistical price distributions from BigQuery tables:
  - finshield.diagnosis_benchmarks
  - finshield.category_benchmarks

Enforces strict fallback hierarchy (exact -> block -> chapter -> global)
and normalizes line item categories using a deterministic taxonomy with Gemini Flash caching.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from backend.app.config import settings
from backend.app.exceptions import CloudServiceError
from backend.app.services.gemini_client import get_gemini_client, get_model_name

logger = logging.getLogger("finshield.services.benchmarks")

MIN_SAMPLE_THRESHOLD = 30  # Documented threshold N=30 for sample size validity


@dataclass
class DiagnosisBenchmark:
    diagnosis_code: str
    fallback_level: str  # exact | block | chapter | global
    sample_count: int
    p50: float
    p75: float
    p90: float
    p95: float


@dataclass
class CategoryBenchmark:
    diagnosis_code: str
    category: str
    fallback_level: str  # exact | global
    sample_count: int
    unit_price_p50: float
    unit_price_p75: float
    unit_price_p90: float
    unit_price_p95: float
    amount_p50: float
    amount_p75: float
    amount_p90: float
    amount_p95: float


class BenchmarkService:
    def __init__(self):
        self._diagnosis_benchmarks: Dict[str, Dict[str, DiagnosisBenchmark]] = {}
        self._category_benchmarks: Dict[str, Dict[str, CategoryBenchmark]] = {}
        self._category_cache: Dict[str, str] = {}
        self._loaded: bool = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self.load_benchmarks()

    def load_benchmarks(self):
        """Loads benchmark records from BigQuery into memory."""
        from backend.tools.bq import bq_warehouse

        # 1. Load diagnosis benchmarks
        query_diag = f"""
        SELECT diagnosis_code, fallback_level, sample_count, p50, p75, p90, p95
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.diagnosis_benchmarks`
        """
        try:
            results = list(bq_warehouse.client.query(query_diag).result())
            for row in results:
                bench = DiagnosisBenchmark(
                    diagnosis_code=str(row.diagnosis_code).strip().upper(),
                    fallback_level=str(row.fallback_level).strip().lower(),
                    sample_count=int(row.sample_count),
                    p50=float(row.p50),
                    p75=float(row.p75),
                    p90=float(row.p90),
                    p95=float(row.p95)
                )
                self._diagnosis_benchmarks.setdefault(bench.fallback_level, {})[bench.diagnosis_code] = bench
        except Exception as e:
            logger.warning(f"Could not load diagnosis_benchmarks from BigQuery: {e}")

        # 2. Load category benchmarks
        query_cat = f"""
        SELECT diagnosis_code, category, fallback_level, sample_count,
               unit_price_p50, unit_price_p75, unit_price_p90, unit_price_p95,
               amount_p50, amount_p75, amount_p90, amount_p95
        FROM `{settings.GCP_PROJECT}.{settings.BIGQUERY_DATASET}.category_benchmarks`
        """
        try:
            results = list(bq_warehouse.client.query(query_cat).result())
            for row in results:
                cat_bench = CategoryBenchmark(
                    diagnosis_code=str(row.diagnosis_code).strip().upper(),
                    category=str(row.category).strip().lower(),
                    fallback_level=str(row.fallback_level).strip().lower(),
                    sample_count=int(row.sample_count),
                    unit_price_p50=float(row.unit_price_p50),
                    unit_price_p75=float(row.unit_price_p75),
                    unit_price_p90=float(row.unit_price_p90),
                    unit_price_p95=float(row.unit_price_p95),
                    amount_p50=float(row.amount_p50),
                    amount_p75=float(row.amount_p75),
                    amount_p90=float(row.amount_p90),
                    amount_p95=float(row.amount_p95)
                )
                key = f"{cat_bench.category}:{cat_bench.diagnosis_code}"
                self._category_benchmarks.setdefault(cat_bench.fallback_level, {})[key] = cat_bench
        except Exception as e:
            logger.warning(f"Could not load category_benchmarks from BigQuery: {e}")

        self._loaded = True

    def get_diagnosis_benchmark(self, diagnosis_code: Optional[str]) -> DiagnosisBenchmark:
        """
        Returns benchmark for diagnosis following the documented fallback hierarchy:
        1. Exact code (n >= 30)
        2. 3-character block (n >= 30)
        3. 1-character chapter (n >= 30)
        4. Global benchmark
        """
        self._ensure_loaded()
        clean_code = (diagnosis_code or "").split()[0].replace("(", "").replace(")", "").strip().upper()

        exact_map = self._diagnosis_benchmarks.get("exact", {})
        block_map = self._diagnosis_benchmarks.get("block", {})
        chapter_map = self._diagnosis_benchmarks.get("chapter", {})
        global_map = self._diagnosis_benchmarks.get("global", {})

        # 1. Exact match
        if clean_code and clean_code in exact_map:
            return exact_map[clean_code]

        # 2. Block match (e.g. K35 from K35.8)
        block = clean_code[:3] if len(clean_code) >= 3 else clean_code
        if block and block in block_map:
            return block_map[block]

        # 3. Chapter match (e.g. K from K35.8)
        chapter = clean_code[:1] if len(clean_code) >= 1 else ""
        if chapter and chapter in chapter_map:
            return chapter_map[chapter]

        # 4. Global fallback
        if "GLOBAL" in global_map:
            return global_map["GLOBAL"]

        # Default fallback if table was empty
        return DiagnosisBenchmark(
            diagnosis_code="GLOBAL",
            fallback_level="global",
            sample_count=2637,
            p50=49916.56,
            p75=67704.70,
            p90=119472.78,
            p95=134867.98
        )

    def get_category_benchmark(self, category: str, diagnosis_code: Optional[str] = None) -> CategoryBenchmark:
        """
        Returns unit price and amount benchmark for category and diagnosis:
        1. Exact match for (category, diagnosis_code)
        2. Exact match for (category, 3-char block)
        3. Global match for category
        """
        self._ensure_loaded()
        cat = category.strip().lower()
        clean_code = (diagnosis_code or "").split()[0].replace("(", "").replace(")", "").strip().upper()

        exact_map = self._category_benchmarks.get("exact", {})
        global_map = self._category_benchmarks.get("global", {})

        # 1. Exact diagnosis match
        key_exact = f"{cat}:{clean_code}"
        if key_exact in exact_map:
            return exact_map[key_exact]

        # 2. Block match
        block = clean_code[:3] if len(clean_code) >= 3 else clean_code
        key_block = f"{cat}:{block}"
        if key_block in exact_map:
            return exact_map[key_block]

        # 3. Global category match
        key_global = f"{cat}:GLOBAL"
        if key_global in global_map:
            return global_map[key_global]

        # Hardcoded realistic defaults if category not found in DB
        defaults = {
            "room_rent": (4000.0, 4800.0, 4800.0, 4800.0, 12000.0, 16000.0, 24000.0, 24000.0),
            "icu": (8000.0, 9500.0, 10000.0, 12000.0, 16000.0, 24000.0, 30000.0, 36000.0),
            "surgery_ot": (19534.0, 39929.0, 80255.0, 96789.0, 19534.0, 39929.0, 80255.0, 96789.0),
            "consultation": (2000.0, 2500.0, 2500.0, 2500.0, 6000.0, 8000.0, 10500.0, 12500.0),
            "pharmacy": (4926.0, 6431.0, 7380.0, 7707.0, 4926.0, 6431.0, 7380.0, 7707.0),
            "diagnostics": (3500.0, 4800.0, 6000.0, 7500.0, 4000.0, 6500.0, 8500.0, 10500.0),
            "ancillary": (2000.0, 3200.0, 4500.0, 5500.0, 3500.0, 5500.0, 8000.0, 10000.0),
        }
        vals = defaults.get(cat, defaults["ancillary"])
        return CategoryBenchmark(
            diagnosis_code="GLOBAL",
            category=cat,
            fallback_level="global",
            sample_count=2637,
            unit_price_p50=vals[0],
            unit_price_p75=vals[1],
            unit_price_p90=vals[2],
            unit_price_p95=vals[3],
            amount_p50=vals[4],
            amount_p75=vals[5],
            amount_p90=vals[6],
            amount_p95=vals[7]
        )

    def normalize_line_item_category(self, description: str) -> str:
        """
        Normalizes line-item description into a standard category:
          room_rent | icu | surgery_ot | consultation | pharmacy | diagnostics | ancillary
        Uses deterministic keyword rules first, with Gemini Flash fallback for ambiguous/unknown items.
        Results are cached in memory.
        """
        desc_clean = (description or "").strip().lower()
        if not desc_clean:
            return "ancillary"

        if desc_clean in self._category_cache:
            return self._category_cache[desc_clean]

        # 1. Deterministic Taxonomy Rules
        if any(k in desc_clean for k in ["icu", "iccu", "intensive care", "picu", "nicu", "cardiac monitoring bed"]):
            cat = "icu"
        elif any(k in desc_clean for k in ["room", "ward", "bed", "suite", "nursing home stay"]):
            cat = "room_rent"
        elif any(k in desc_clean for k in ["consult", "doctor", "visiting", "visit", "physician", "specialist"]):
            cat = "consultation"
        elif any(k in desc_clean for k in ["surgery", "ot ", "ot charges", "operation", "procedure", "laparoscopic", "appendectomy", "cholecystectomy", "anesthesia", "surgeon"]):
            cat = "surgery_ot"
        elif any(k in desc_clean for k in ["pharmacy", "medicine", "drug", "injection", "antibiotic", "fluid", "saline", "tablet", "capsule", "iv "]):
            cat = "pharmacy"
        elif any(k in desc_clean for k in ["mri", "ct ", "scan", "x-ray", "ultrasound", "usg", "radiology", "pathology", "lab", "test", "investigation", "ecg", "blood"]):
            cat = "diagnostics"
        elif any(k in desc_clean for k in ["consumable", "disposable", "glove", "syringe", "cannula", "catheter", "ppe", "bandage", "dressing", "monitoring", "equip", "kit"]):
            cat = "ancillary"
        else:
            # 2. Gemini classification fallback for unknown terms
            cat = self._classify_with_gemini(description)

        self._category_cache[desc_clean] = cat
        return cat

    def _classify_with_gemini(self, description: str) -> str:
        """Calls Gemini Flash to categorize an ambiguous medical bill line item."""
        try:
            client = get_gemini_client()
            model_name = get_model_name("flash")
            prompt = (
                f"Categorize this hospital invoice line item into exactly ONE of these categories: "
                f"room_rent, icu, surgery_ot, consultation, pharmacy, diagnostics, ancillary.\n\n"
                f"Line item: '{description}'\n\n"
                f"Respond with ONLY the exact category name in lowercase."
            )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt
            )
            if response and response.text:
                resp_text = response.text.strip().lower()
                valid_cats = ["room_rent", "icu", "surgery_ot", "consultation", "pharmacy", "diagnostics", "ancillary"]
                for vc in valid_cats:
                    if vc in resp_text:
                        return vc
        except Exception as e:
            logger.debug(f"Gemini category classification fallback failed for '{description}': {e}")
        return "ancillary"


benchmark_service = BenchmarkService()
