"""
backend/tests/test_golden_claims.py

Parametrized acceptance test suite for all nine Golden Claims (G1-G9).
Validates that each golden claim analyzed through the multi-agent claims fraud pipeline
with fakes at the client boundary (BigQuery, Firestore, GCS, Document AI, Gemini) produces
the exact expected verdict recorded in data/demo/ground_truth.json:
  - G1: APPROVE (Clean claim)
  - G2: REJECT  (Arithmetic mismatch: item sum vs total)
  - G3: REVIEW  (Policy cap breach: room rent cap exceeded)
  - G4: REJECT  (Cross-insurer duplicate claim)
  - G5: REJECT  (Impossible travel: spacetime velocity breach)
  - G6: REJECT  (Forged document: producer/font/metadata tampering)
  - G7: REJECT  (Prompt injection: hidden text instruction to AI)
  - G8: REJECT  (Altered approval letter: cryptographic provenance tamper)
  - G9: REVIEW  (Mule account ring / policy breach pattern)
"""

import json
from pathlib import Path
import pytest

from backend.app.schemas import Claim, Claimant, Provider, LineItem, Document, DocType, Verdict
from backend.agents.root import run_claims_fraud_pipeline
from backend.app.services.db import db_service
from scripts.seed_cloud import GOLDEN_CLAIMS

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = ROOT_DIR / "data" / "demo"
GROUND_TRUTH = json.loads((DEMO_DIR / "ground_truth.json").read_text())


@pytest.mark.parametrize("golden_cfg", GOLDEN_CLAIMS, ids=[g["key"] for g in GOLDEN_CLAIMS])
def test_golden_claim_verdict(golden_cfg):
    """
    Parametrized test for each golden claim G1..G9.
    Asserts actual pipeline verdict matches expected ground truth verdict.
    """
    key = golden_cfg["key"]
    claim_id = golden_cfg["claim_id"]
    pdf_path = DEMO_DIR / golden_cfg["file"]
    assert pdf_path.exists(), f"Golden PDF missing from demo directory: {pdf_path}"

    expected_verdict = GROUND_TRUTH[key]["expected_verdict"].lower()

    # Pre-seed issuance ledger for G8 altered approval letter verification
    if key == "G8":
        db_service._fs_client.collection("issuance_ledger").document("SANCTION-G8-GENUINE").set({
            "doc_id": "SANCTION-G8-GENUINE",
            "claim_id": claim_id,
            "claimant_id": golden_cfg["claimant"]["claimant_id"],
            "amount_paise": 5000000,
            "doc_type": "approval_letter",
            "carrier": "xmp",
            "issuer": "FINSHIELD-DEMO",
            "issued_at": "2026-03-12T09:30:00Z"
        })

    claim = Claim(
        claim_id=claim_id,
        policy_id=golden_cfg["policy_id"],
        insurer_id=golden_cfg["insurer_id"],
        claimant=Claimant(**golden_cfg["claimant"]),
        provider=Provider(**golden_cfg["provider"]),
        doctor_id=golden_cfg["doctor_id"],
        admission_ts=golden_cfg["admission_ts"],
        discharge_ts=golden_cfg["discharge_ts"],
        diagnosis_code=golden_cfg["diagnosis_code"],
        subtotal=golden_cfg["subtotal"],
        tax=golden_cfg["tax"],
        total_claimed=golden_cfg["total_claimed"],
        line_items=[LineItem(**it) for it in golden_cfg["line_items"]],
        documents=[
            Document(
                doc_id=f"DOC-{claim_id}-ORIGINAL",
                gcs_uri=f"file://{pdf_path.resolve()}",
                doc_type=DocType.APPROVAL_LETTER if key == "G8" else DocType.BILL,
                sha256=f"sha_{key}"
            )
        ]
    )
    db_service.save_claim(claim)

    dossier = run_claims_fraud_pipeline(claim)
    actual_verdict = dossier.verdict.value.lower()

    assert actual_verdict == expected_verdict, (
        f"Verdict mismatch on {key} ({claim_id}): expected {expected_verdict.upper()}, "
        f"got {actual_verdict.upper()} (risk_score={dossier.risk_score}, "
        f"findings={[f.check_id for f in dossier.findings]})"
    )
