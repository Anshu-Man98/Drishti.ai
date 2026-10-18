import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from backend.app.schemas import ClaimSummary, Verdict
from backend.app.services.db import db_service
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_claim_matches_category_helper():
    # Dossier with math finding
    math_dossier = {
        "findings": [
            {
                "check_id": "SUBTOTAL_SUM_MISMATCH",
                "severity": "high",
                "title": "Subtotal mismatch",
                "category": "Arithmetic"
            }
        ]
    }
    
    # Dossier with spacetime finding
    spacetime_dossier = {
        "findings": [
            {
                "check_id": "SPACETIME_VELOCITY_IMPOSSIBLE",
                "severity": "critical",
                "title": "Impossible travel speed",
            }
        ]
    }

    # Clean dossier
    clean_dossier = {
        "findings": []
    }

    # Info-only dossier (should be ignored as non-anomaly)
    info_dossier = {
        "findings": [
            {
                "check_id": "UNGROUNDED_FIELD_NOTICE",
                "severity": "info",
                "title": "Ungrounded notice",
            }
        ]
    }

    assert db_service._claim_matches_category(math_dossier, "Arithmetic & Math Mismatches") is True
    assert db_service._claim_matches_category(math_dossier, "arithmetic") is True
    assert db_service._claim_matches_category(math_dossier, "Spacetime & Teleportation Anomalies") is False

    assert db_service._claim_matches_category(spacetime_dossier, "Spacetime & Teleportation Anomalies") is True
    assert db_service._claim_matches_category(spacetime_dossier, "Arithmetic & Math Mismatches") is False

    assert db_service._claim_matches_category(math_dossier, "all_anomalies") is True
    assert db_service._claim_matches_category(spacetime_dossier, "all_anomalies") is True
    assert db_service._claim_matches_category(clean_dossier, "all_anomalies") is False
    assert db_service._claim_matches_category(info_dossier, "all_anomalies") is False


def test_list_claims_endpoint_accepts_category_and_vector():
    with patch.object(db_service, "list_claims_paged") as mock_paged:
        mock_paged.return_value = ([], 0)

        # Query with category
        resp = client.get("/api/claims?category=Arithmetic%20%26%20Math%20Mismatches")
        assert resp.status_code == 200
        assert mock_paged.call_args[1]["category"] == "Arithmetic & Math Mismatches"

        # Query with vector
        resp = client.get("/api/claims?vector=Spacetime%20%26%20Teleportation%20Anomalies")
        assert resp.status_code == 200
        assert mock_paged.call_args[1]["category"] == "Spacetime & Teleportation Anomalies"

        # Query with all_anomalies
        resp = client.get("/api/claims?category=all_anomalies")
        assert resp.status_code == 200
        assert mock_paged.call_args[1]["category"] == "all_anomalies"
