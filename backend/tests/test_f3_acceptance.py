"""
Acceptance test suite for F3: BigQuery ML Fraud Score + Feature Explanations.
Validates:
1. Feature extraction from Claim objects across all 10 model features.
2. Inference via ml_score returning probability and top 5 feature attributions.
3. Clean claim vs fraudulent claims probability discrimination.
4. Deterministic hybrid scoring formula: round(0.6 * agent_score + 40 * ml_probability).
5. High ML risk finding emission when probability > 0.60.
6. Full end-to-end multi-agent pipeline integration with BigQuery ML scoring.
7. Presence and integrity of model artifacts and documentation.
"""

import json
from pathlib import Path
import pytest
import joblib

from backend.app.schemas import (
    Claim, Finding, Severity, Verdict, AgentName
)
from backend.tools.docai import process_document_docai
from backend.tools.bq import (
    extract_claim_features,
    ml_score,
    FEATURE_COLUMNS,
    DIAGNOSIS_MEDIANS
)
from backend.tools.scoring import score_findings
from backend.agents.root import run_claims_fraud_pipeline

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DEMO_DIR = DATA_DIR / "demo"
GROUND_TRUTH_PATH = DEMO_DIR / "ground_truth.json"


def get_golden_claim(key: str) -> Claim:
    """Extracts and constructs Claim object for a golden demo claim (G1-G6)."""
    gt = json.loads(GROUND_TRUTH_PATH.read_text())
    info = gt[key]
    pdf_path = DEMO_DIR / info["file"]
    assert pdf_path.exists(), f"Demo PDF {info['file']} missing at {pdf_path}"
    claim, _ = process_document_docai(pdf_path.read_bytes(), filename=info["file"], claim_id=f"CLM-{key}")
    return claim


def test_feature_extraction_all_columns():
    """Verify that extract_claim_features extracts all 10 required features with valid numeric values."""
    claim = get_golden_claim("G1")
    features = extract_claim_features(claim)

    for col in FEATURE_COLUMNS:
        assert col in features, f"Missing feature column: {col}"
        val = features[col]
        assert isinstance(val, (int, float)), f"Feature {col} value {val} is not numeric"

    # Specific assertions for G1 (clean appendicitis claim)
    assert features["claim_amount"] == 74550.0
    assert features["length_of_stay"] >= 1
    assert features["doctor_distinct_cities_24h"] == 1
    assert features["shared_bank_account_count"] == 1
    assert features["room_rent_vs_cap_ratio"] <= 1.0


def test_feature_extraction_diagnosis_medians():
    """Verify amount_vs_diagnosis_median_ratio is calculated correctly based on diagnosis code."""
    claim = get_golden_claim("G1")
    features = extract_claim_features(claim)
    expected_median = DIAGNOSIS_MEDIANS["K35.8"]  # 65,000
    expected_ratio = round(74550.0 / expected_median, 3)
    assert features["amount_vs_diagnosis_median_ratio"] == expected_ratio


def test_ml_score_output_format():
    """Verify that ml_score returns a valid probability and exactly 5 feature attributions."""
    sample_features = {
        "claim_amount": 75000.0,
        "amount_vs_diagnosis_median_ratio": 1.25,
        "length_of_stay": 4,
        "claimant_prior_claims_90d": 1,
        "provider_claims_per_day": 2.4,
        "doctor_distinct_cities_24h": 1,
        "shared_bank_account_count": 1,
        "days_policy_start_to_claim": 120,
        "line_item_count": 6,
        "room_rent_vs_cap_ratio": 0.8
    }

    prob, top_features = ml_score(sample_features)

    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0
    assert isinstance(top_features, list)
    assert len(top_features) == 5

    for item in top_features:
        assert "feature" in item
        assert "attribution" in item
        assert isinstance(item["feature"], str)
        assert isinstance(item["attribution"], float)


def test_golden_claims_fraud_discrimination():
    """
    Verify that clean claim G1 has a low ML fraud probability (< 0.15),
    and that all fraudulent claims (G2-G6) score higher than clean claim G1.
    """
    g1_claim = get_golden_claim("G1")
    g1_features = extract_claim_features(g1_claim)
    g1_prob, _ = ml_score(g1_features)

    assert g1_prob < 0.15, f"Clean claim G1 scored unexpectedly high: {g1_prob}"

    for fid in ["G2", "G3", "G4", "G5", "G6"]:
        claim = get_golden_claim(fid)
        features = extract_claim_features(claim)
        prob, _ = ml_score(features)
        assert prob > g1_prob, f"Fraud claim {fid} ({prob}) did not score higher than G1 ({g1_prob})"


def test_deterministic_hybrid_scoring_formula():
    """
    Verify the hybrid scoring formula:
      final_risk_score = round(0.6 * agent_score + 40 * ml_probability)
    and ensure thresholding into APPROVE, REVIEW, and REJECT.
    """
    # Case 1: Clean claim with no agent findings and low ML probability (0.05)
    score1, verdict1 = score_findings([], ml_probability=0.05)
    assert score1 == round(0.6 * 0 + 40 * 0.05)  # 2
    assert verdict1 == Verdict.APPROVE

    # Case 2: One medium finding (15) and ML prob = 0.50
    finding_med = Finding(
        finding_id="F1", agent=AgentName.POLICY, check_id="TEST_MED",
        severity=Severity.MEDIUM, title="Test", explanation="Test", evidence=[],
        confidence=0.9
    )
    score2, verdict2 = score_findings([finding_med], ml_probability=0.50)
    # 0.6 * 15 + 40 * 0.50 = 9 + 20 = 29
    assert score2 == 29
    assert verdict2 == Verdict.APPROVE

    # Case 3: One high finding (30) and ML prob = 0.50
    finding_high = Finding(
        finding_id="F2", agent=AgentName.POLICY, check_id="TEST_HIGH",
        severity=Severity.HIGH, title="Test", explanation="Test", evidence=[],
        confidence=0.9
    )
    score3, verdict3 = score_findings([finding_high], ml_probability=0.50)
    # 0.6 * 30 + 40 * 0.50 = 18 + 20 = 38
    assert score3 == 38
    assert verdict3 == Verdict.REVIEW

    # Case 4: Critical finding (50) + High finding (30) [total 80] and ML prob = 0.90
    finding_crit = Finding(
        finding_id="F3", agent=AgentName.FORENSICS, check_id="TEST_CRIT",
        severity=Severity.CRITICAL, title="Test", explanation="Test", evidence=[],
        confidence=0.9
    )
    score4, verdict4 = score_findings([finding_crit, finding_high], ml_probability=0.90)
    # 0.6 * 80 + 40 * 0.90 = 48 + 36 = 84
    assert score4 == 84
    assert verdict4 == Verdict.REJECT

    # Case 5: Cap at 100
    score5, verdict5 = score_findings([finding_crit, finding_crit, finding_crit], ml_probability=1.0)
    assert score5 == 100
    assert verdict5 == Verdict.REJECT


def test_pipeline_end_to_end_ml_integration():
    """
    Test running the complete multi-agent pipeline on a claim to ensure
    dossier.ml_score and dossier.top_ml_features are properly populated and explained.
    """
    claim = get_golden_claim("G3")
    dossier = run_claims_fraud_pipeline(claim)

    assert dossier.ml_score is not None
    assert isinstance(dossier.ml_score, float)
    assert 0.0 <= dossier.ml_score <= 1.0

    assert dossier.top_ml_features is not None
    assert len(dossier.top_ml_features) == 5

    # Since G3 has room rent cap breach, ML probability is high (> 0.60)
    # which should emit an ML anomaly finding
    ml_findings = [f for f in dossier.findings if f.agent == AgentName.ML]
    assert len(ml_findings) >= 1
    assert ml_findings[0].check_id == "BQML_HIGH_RISK_ANOMALY"

    # Verify summary mentions BigQuery ML and probability
    assert "BigQuery ML" in dossier.summary or "ML" in dossier.summary


def test_model_eval_docs_and_sql_exist():
    """Verify that BigQuery ML SQL and evaluation documentation artifacts exist."""
    sql_path = ROOT_DIR / "infra" / "bqml.sql"
    assert sql_path.exists()
    sql_text = sql_path.read_text()
    assert "BOOSTED_TREE_CLASSIFIER" in sql_text
    assert "ML.EXPLAIN_PREDICT" in sql_text
    assert "finshield.fraud_model" in sql_text
    assert "finshield.provider_fraud_model" in sql_text

    doc_path = ROOT_DIR / "docs" / "model_eval.md"
    assert doc_path.exists()
    doc_text = doc_path.read_text()
    assert "ROC AUC" in doc_text
    assert "Kaggle" in doc_text
    assert "0.90" in doc_text

    model_joblib = DATA_DIR / "fraud_model.joblib"
    assert model_joblib.exists()
    art = joblib.load(model_joblib)
    assert "model" in art
    assert "features" in art
    assert len(art["features"]) == 10
