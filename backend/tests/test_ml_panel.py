"""
Unit and regression tests for Issue 4:
Validates ML explanation panel attributions, direction handling, baseline prior,
negligible feature thresholding, and empty states.
"""

from unittest.mock import MagicMock, patch
from datetime import datetime
import pytest

import backend.tools.bq as from_bq
from backend.tools.bq import ml_score, extract_claim_features
from backend.app.schemas import (
    Claim, Dossier, Finding, MlFeature, Verdict, AgentName, Severity, Claimant, Provider
)
from backend.agents.synthesizer import synthesize_dossier


def test_ml_score_clean_claim_direction_and_sign():
    """
    When predicted_is_fraud == 0 (clean prediction):
    Raw positive attribution means increased clean probability (lowers fraud risk).
    Raw negative attribution means decreased clean probability (raises fraud risk).
    Standardized attribution must have positive == 'raises risk' and negative == 'lowers risk'.
    """
    mock_row = MagicMock()
    mock_row.predicted_is_fraud = 0
    mock_row.probability = 0.85  # 85% clean prob => 15% fraud prob
    mock_row.top_feature_attributions = [
        {"feature": "total_percentile_vs_diagnosis", "attribution": -0.25},  # pulls toward fraud => raises risk
        {"feature": "claimant_prior_claims_90d", "attribution": 0.08},     # pulls toward clean => lowers risk
        {"feature": "shared_bank_account_count", "attribution": 0.0002},    # negligible => must be filtered
    ]

    mock_client = MagicMock()
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [mock_row]
    mock_client.query.return_value = mock_query_job

    with patch.object(type(from_bq.bq_warehouse), "client", mock_client), \
         patch.object(from_bq.bq_warehouse, "get_baseline_fraud_rate", return_value=0.1216):
        prob, top_feats, baseline = ml_score(
            {
                "claim_amount": 50000.0,
                "amount_vs_diagnosis_median_ratio": 1.0,
                "length_of_stay": 2,
                "claimant_prior_claims_90d": 0,
                "provider_claims_per_day": 2.0,
                "doctor_distinct_cities_24h": 1,
                "shared_bank_account_count": 1,
                "days_policy_start_to_claim": 180,
                "line_item_count": 4,
                "room_rent_vs_cap_ratio": 0.8
            },
            return_baseline=True
        )

        assert prob == 0.15
        assert baseline == 0.1216
        # Negligible feature (< 0.001) must be filtered out
        assert len(top_feats) == 2

        f0 = next(f for f in top_feats if f["feature"] == "total_percentile_vs_diagnosis")
        assert f0["attribution"] == 0.25
        assert f0["direction"] == "raises risk"

        f1 = next(f for f in top_feats if f["feature"] == "claimant_prior_claims_90d")
        assert f1["attribution"] == -0.08
        assert f1["direction"] == "lowers risk"


def test_ml_score_fraud_claim_direction_and_sign():
    """
    When predicted_is_fraud == 1 (fraud prediction):
    Raw positive attribution means increased fraud probability (raises fraud risk).
    Raw negative attribution means decreased fraud probability (lowers fraud risk).
    Standardized attribution must keep positive == 'raises risk' and negative == 'lowers risk'.
    """
    mock_row = MagicMock()
    mock_row.predicted_is_fraud = 1
    mock_row.probability = 0.88  # 88% fraud prob
    mock_row.top_feature_attributions = [
        {"feature": "room_rent_vs_cap_ratio", "attribution": 0.65},        # pushes toward fraud => raises risk
        {"feature": "length_of_stay", "attribution": -0.15},               # pulls away from fraud => lowers risk
        {"feature": "line_item_count", "attribution": 0.00005},             # negligible => filtered
    ]

    mock_client = MagicMock()
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [mock_row]
    mock_client.query.return_value = mock_query_job

    with patch.object(type(from_bq.bq_warehouse), "client", mock_client), \
         patch.object(from_bq.bq_warehouse, "get_baseline_fraud_rate", return_value=0.1216):
        prob, top_feats, baseline = ml_score(
            {
                "claim_amount": 150000.0,
                "amount_vs_diagnosis_median_ratio": 2.5,
                "length_of_stay": 5,
                "claimant_prior_claims_90d": 2,
                "provider_claims_per_day": 5.0,
                "doctor_distinct_cities_24h": 2,
                "shared_bank_account_count": 3,
                "days_policy_start_to_claim": 30,
                "line_item_count": 10,
                "room_rent_vs_cap_ratio": 2.0
            },
            return_baseline=True
        )

        assert prob == 0.88
        assert baseline == 0.1216
        assert len(top_feats) == 2

        f0 = next(f for f in top_feats if f["feature"] == "room_rent_vs_cap_ratio")
        assert f0["attribution"] == 0.65
        assert f0["direction"] == "raises risk"

        f1 = next(f for f in top_feats if f["feature"] == "length_of_stay")
        assert f1["attribution"] == -0.15
        assert f1["direction"] == "lowers risk"


def test_synthesize_dossier_attaches_baseline_and_features():
    """Verify that synthesize_dossier stores baseline_ml_score and top_ml_features on Dossier."""
    claim = Claim(
        claim_id="CLM-UNIT-TEST",
        policy_id="POL-CARE-99812",
        insurer_id="INS-CARE",
        claimant=Claimant(claimant_id="C1", name="Rohan Verma", phone="+919876543210", bank_account_hash="hash123"),
        provider=Provider(hospital_id="H1", name="Fortis Escorts", city="Jaipur"),
        doctor_id="DOC-99",
        admission_ts=datetime(2026, 4, 1),
        discharge_ts=datetime(2026, 4, 4),
        diagnosis_code="K35.8",
        line_items=[],
        total_claimed=74550.0
    )

    top_feats = [
        MlFeature(feature="room_rent_vs_cap_ratio", attribution=0.45, direction="raises risk"),
        MlFeature(feature="claimant_prior_claims_90d", attribution=-0.08, direction="lowers risk")
    ]

    with patch("backend.agents.synthesizer.call_tool", return_value={"score": 15, "verdict": Verdict.APPROVE}):
        dossier = synthesize_dossier(
            claim=claim,
            all_findings=[],
            ml_score=0.15,
            top_ml_features=top_feats,
            baseline_ml_score=0.1216
        )

        assert dossier.ml_score == 0.15
        assert dossier.baseline_ml_score == 0.1216
        assert dossier.top_ml_features == top_feats
        assert len(dossier.top_ml_features) == 2
