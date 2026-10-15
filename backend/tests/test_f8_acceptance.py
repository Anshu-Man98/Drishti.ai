"""
Acceptance test suite for F8: Adjuster Chat Copilot with the Dossier.
Validates:
1. Grounded answering strictly on Dossier, Findings, Claim JSON, and policy rules.
2. On G2, "Why was this flagged?" cites the arithmetic finding and highlights the total row.
3. Off-topic questions receive a polite "not in the case file" response.
4. "Which policy clause applies?" cites Clause 3.1 room rent cap.
5. "What's the strongest evidence?" cites high/critical severity forensic findings.
6. Server-Sent Events (SSE) streaming format and event schema.
7. Chat history persistence under the claim in SQLite/Firestore.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import Claim, Finding, Severity, AgentName, Verdict
from backend.app.services.db import db_service
from backend.tools.docai import process_document_docai
from backend.agents.root import run_claims_fraud_pipeline

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = ROOT_DIR / "data" / "demo"
GROUND_TRUTH_PATH = DEMO_DIR / "ground_truth.json"

client = TestClient(app)


def setup_claim_in_db(key: str) -> str:
    """Helper that extracts, analyzes, and saves a golden claim into db_service."""
    gt = json.loads(GROUND_TRUTH_PATH.read_text())
    info = gt[key]
    pdf_path = DEMO_DIR / info["file"]
    claim_id = f"CLM-{key}-F8-TEST"

    # Extract claim from PDF
    claim, _ = process_document_docai(pdf_path.read_bytes(), filename=info["file"], claim_id=claim_id)
    if claim.documents:
        claim.documents[0].gcs_uri = f"file://{pdf_path}"
    db_service.save_claim(claim)

    # Run multi-agent pipeline to generate and save dossier
    dossier = run_claims_fraud_pipeline(claim)
    db_service.save_dossier(dossier)

    return claim_id


def test_chat_g2_why_was_this_flagged_cites_arithmetic_finding():
    """
    Acceptance Criterion:
    On G2, "Why was this flagged?" cites the arithmetic finding and highlights the total row.
    """
    claim_id = setup_claim_in_db("G2")

    response = client.post(
        f"/claims/{claim_id}/chat",
        headers={"Accept": "application/json"},
        json={"message": "Why was this flagged?"}
    )
    assert response.status_code == 200
    data = response.json()

    assert "answer" in data
    assert "cited_finding_ids" in data
    assert "cited_evidence" in data

    answer = data["answer"]
    # Verify arithmetic discrepancy is explained
    assert any(w in answer.lower() for w in ["arithmetic", "mismatch", "total", "sum", "subtotal"])

    # Verify at least one finding ID was cited
    cited_ids = data["cited_finding_ids"]
    assert len(cited_ids) >= 1
    assert any("ARITH" in cid or "SUBTOTAL" in cid or "TOTAL" in cid for cid in cited_ids)

    # Verify evidence citations exist and have bounding box coordinates on total/line item rows
    evidence = data["cited_evidence"]
    assert len(evidence) >= 1
    has_bbox = any(ev.get("bbox") is not None and len(ev.get("bbox")) == 4 for ev in evidence)
    assert has_bbox, "Evidence citation must contain bounding box coordinates"


def test_chat_off_topic_question_polite_refusal():
    """
    Acceptance Criterion:
    An off-topic question gets a polite 'not in the case file' answer.
    """
    claim_id = setup_claim_in_db("G2")

    response = client.post(
        f"/claims/{claim_id}/chat",
        headers={"Accept": "application/json"},
        json={"message": "What is the capital of France?"}
    )
    assert response.status_code == 200
    data = response.json()

    answer = data["answer"]
    # Must politely state that this cannot be answered from the case file
    assert "case file" in answer.lower() or "not found" in answer.lower() or "cannot be answered" in answer.lower()
    # No claim findings should be cited for off-topic query
    assert len(data["cited_finding_ids"]) == 0


def test_chat_which_policy_clause_applies_on_g3():
    """
    Verify that asking about policy clauses on G3 (policy cap breach) cites Clause 3.1 room rent cap.
    """
    claim_id = setup_claim_in_db("G3")

    response = client.post(
        f"/claims/{claim_id}/chat",
        headers={"Accept": "application/json"},
        json={"message": "Which policy clause applies?"}
    )
    assert response.status_code == 200
    data = response.json()

    answer = data["answer"]
    assert "clause 3.1" in answer.lower() or "room rent" in answer.lower()
    assert "5,000" in answer or "5000" in answer or "cap" in answer.lower()


def test_chat_strongest_evidence_on_g6():
    """
    Verify that asking for strongest evidence on G6 cites critical forensic findings.
    """
    claim_id = setup_claim_in_db("G6")

    response = client.post(
        f"/claims/{claim_id}/chat",
        headers={"Accept": "application/json"},
        json={"message": "What's the strongest evidence?"}
    )
    assert response.status_code == 200
    data = response.json()

    answer = data["answer"]
    assert len(data["cited_finding_ids"]) >= 1
    assert any(w in answer.lower() for w in ["producer", "photoshop", "font", "tamper", "date", "metadata"])


def test_chat_sse_streaming_protocol():
    """
    Verify that POST /claims/{id}/chat streams SSE events with 'chunk' and a final 'done' event.
    """
    claim_id = setup_claim_in_db("G1")

    response = client.post(
        f"/claims/{claim_id}/chat",
        headers={"Accept": "text/event-stream"},
        json={"message": "Why was this flagged?"}
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["Content-Type"]

    raw_text = response.text
    assert "data:" in raw_text

    # Parse SSE events
    events = []
    for line in raw_text.split("\n"):
        line = line.trim() if hasattr(line, "trim") else line.strip()
        if line.startswith("data:"):
            payload = json.loads(line[5:].strip())
            events.append(payload)

    assert len(events) >= 2
    # Intermediate events have "chunk" and done=False
    chunk_events = [e for e in events if not e.get("done")]
    assert len(chunk_events) >= 1
    assert all("chunk" in e for e in chunk_events)

    # Final event has done=True, answer, and cited_finding_ids
    done_events = [e for e in events if e.get("done")]
    assert len(done_events) == 1
    final_event = done_events[0]
    assert "answer" in final_event
    assert "cited_finding_ids" in final_event
    assert "cited_evidence" in final_event


def test_chat_history_persistence():
    """
    Verify that conversations are persisted under the claim and can be retrieved via GET /claims/{id}/chat.
    """
    claim_id = setup_claim_in_db("G2")

    # Send 1st question
    client.post(
        f"/claims/{claim_id}/chat",
        headers={"Accept": "application/json"},
        json={"message": "Why was this flagged?"}
    )

    # Send 2nd question
    client.post(
        f"/claims/{claim_id}/chat",
        headers={"Accept": "application/json"},
        json={"message": "What should I verify next?"}
    )

    # Fetch history
    history_resp = client.get(f"/claims/{claim_id}/chat")
    assert history_resp.status_code == 200
    messages = history_resp.json()

    # Should contain at least 4 messages (2 user + 2 assistant)
    assert len(messages) >= 4
    roles = [m["role"] for m in messages]
    assert roles.count("user") >= 2
    assert roles.count("assistant") >= 2
    assert any("Why was this flagged?" in m["content"] for m in messages)
