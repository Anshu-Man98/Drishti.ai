"""
Acceptance test suite for Feature A4: Two-Corpus RAG & Retrieval-Augmented Fraud Pattern Discovery.

Validates:
1. Golden claim G3 (Arogya Sanjeevani) produces room rent finding citing Clause 3.1 with layer: "retrieved",
   quoting real IRDAI wording.
2. Every policy finding carries evidence with layer: "retrieved", quoting the exact clause and citing clause_id.
3. Similarity floor >= 0.5: Nonsense queries to search_policy and search_patterns return empty lists [].
4. Pattern cards catalog contains 40-60 structured cards across 8 fraud types with valid signatures.
5. Golden claim G9 (clean documents matching historical pattern) surfaces pattern >= 0.5,
   produces agent: "rag" finding with severity: "low", and verdict does not exceed REVIEW.
6. Guardrail enforcement: Retrieved pattern findings cannot force a REJECT verdict, clamped to LOW in score_findings.
7. Kill-switch test: When RAG_PATTERNS_ENABLED is False, pattern retrieval is cleanly disabled.
"""

from pathlib import Path
from datetime import datetime
import json
import pytest

from backend.app.config import settings
from backend.app.schemas import (
    Claim, Finding, Severity, AgentName, Verdict,
    Claimant, Provider, LineItem, Evidence
)
from backend.tools.policy_tools import search_policy, check_policy_caps
from backend.tools.pattern_tools import (
    build_claim_fingerprint,
    search_patterns,
    load_pattern_cards
)
from backend.tools.scoring import score_findings
from backend.tools.docai import process_document_docai
from backend.agents.root import run_claims_fraud_pipeline

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DEMO_DIR = DATA_DIR / "demo"


# ==============================================================================
# 1. G3 ROOM RENT FINDING CITES REAL IRDAI CLAUSE 3.1
# ==============================================================================

def test_g3_room_rent_finding_cites_real_clause_and_quotes_text():
    """
    On Arogya Sanjeevani (G3), room rent cap breach cites Clause 3.1 with layer: 'retrieved'
    and quotes official IRDAI statutory wording.
    """
    sample_g3_claim = Claim(
        claim_id="G3-TEST",
        policy_id="POL-AROGYA-SANJEEVANI-001",
        insurer_id="INS-HDFC-ERGO",
        claimant=Claimant(
            claimant_id="C-1",
            name="Priya Sharma",
            phone="+91-9876543210",
            bank_account_hash="1122334455667788",
            age=34,
            gender="Female"
        ),
        provider=Provider(hospital_id="H-1", name="Fortis Hospital", city="Mumbai", lat=19.0596, lng=72.8295),
        doctor_id="DOC-9001",
        admission_ts=datetime(2026, 7, 10, 10, 0),
        discharge_ts=datetime(2026, 7, 12, 14, 0),
        diagnosis_code="I20.9",
        line_items=[
            LineItem(description="Deluxe Room Rent (2 days @ Rs. 15,000/day)", qty=2, unit_price=15000.0, amount=30000.0, category="room_rent")
        ],
        subtotal=30000.0,
        tax=0.0,
        total_claimed=30000.0
    )

    findings = check_policy_caps("POL-AROGYA-SANJEEVANI-001", sample_g3_claim)
    room_findings = [f for f in findings if "ROOM_RENT" in f.check_id]
    assert len(room_findings) == 1, "Expected one room rent cap breach finding"

    rf = room_findings[0]
    retrieved_ev = [ev for ev in rf.evidence if ev.layer == "retrieved"]
    assert len(retrieved_ev) >= 1, "Policy finding must contain evidence with layer: 'retrieved'"

    ev = retrieved_ev[0]
    assert ev.doc_id == "Clause 3.1", f"Expected Clause 3.1 citation, got {ev.doc_id}"
    assert "Room, Boarding and Nursing Expenses" in ev.quote
    assert "5,000" in ev.quote


# ==============================================================================
# 2. EVERY POLICY FINDING CARRIES RETRIEVED EVIDENCE
# ==============================================================================

def test_every_policy_finding_carries_retrieved_evidence():
    """
    All findings emitted by check_policy_caps must carry at least one evidence item
    with layer == 'retrieved', citing a numbered clause and quoting policy text.
    """
    test_claim = Claim(
        claim_id="TEST-MULTI-BREACH",
        policy_id="POL-AROGYA-SANJEEVANI-001",
        insurer_id="INS-HDFC-ERGO",
        claimant=Claimant(
            claimant_id="C-2",
            name="Rahul Verma",
            phone="+91-9876543211",
            bank_account_hash="2233445566778899",
            age=45,
            gender="Male"
        ),
        provider=Provider(hospital_id="H-2", name="Apollo Hospital", city="Delhi", lat=28.5284, lng=77.2185),
        doctor_id="DOC-9002",
        admission_ts=datetime(2026, 7, 10, 10, 0),
        discharge_ts=datetime(2026, 7, 12, 14, 0),
        diagnosis_code="H25.9",
        line_items=[
            LineItem(description="Deluxe Room Charges (2 days @ Rs. 12,000)", qty=2, unit_price=12000.0, amount=24000.0, category="room_rent"),
            LineItem(description="Intensive Care Unit (2 days @ Rs. 20,000)", qty=2, unit_price=20000.0, amount=40000.0, category="icu"),
            LineItem(description="Cataract Eye Surgery Left Eye", qty=1, unit_price=65000.0, amount=65000.0, category="cataract")
        ],
        subtotal=129000.0,
        tax=0.0,
        total_claimed=129000.0
    )

    findings = check_policy_caps("POL-AROGYA-SANJEEVANI-001", test_claim)
    assert len(findings) >= 2, "Must produce multiple cap breach findings"

    for f in findings:
        retrieved_evidence = [ev for ev in f.evidence if ev.layer == "retrieved"]
        assert len(retrieved_evidence) >= 1, f"Finding {f.check_id} lacks layer: 'retrieved' evidence"
        ev = retrieved_evidence[0]
        assert ev.doc_id.startswith("Clause"), f"Citation doc_id must start with Clause: {ev.doc_id}"
        assert ev.quote and len(ev.quote) > 10, f"Citation quote must not be empty for {f.check_id}"


# ==============================================================================
# 3. SIMILARITY FLOOR >= 0.5: NONSENSE QUERIES RETURN EMPTY LISTS
# ==============================================================================

def test_nonsense_query_returns_nothing():
    """
    Queries below similarity threshold 0.5 (or nonsense jargon) return empty lists.
    No hallucinated or low-confidence matches allowed.
    """
    # Policy search nonsense
    p_results = search_policy(
        "quantum mechanical particle wave duality interstellar photon drive",
        policy_id="POL-AROGYA-SANJEEVANI-001",
        min_score=0.5
    )
    assert p_results == [], f"Expected [] on nonsense policy search, got {p_results}"

    # Pattern search nonsense
    pat_results = search_patterns(
        "alien spacecraft lunar expedition zero gravity hydroponics telemetry",
        k=3,
        min_score=0.5
    )
    assert pat_results == [], f"Expected [] on nonsense pattern search, got {pat_results}"


# ==============================================================================
# 4. PATTERN CARDS CATALOG COUNT AND STRUCTURE
# ==============================================================================

def test_pattern_cards_catalog_count_and_structure():
    """
    Target 40-60 distinct pattern cards across 8 fraud types, each with
    pattern_id, fraud_type, title, narrative, signature, and example_claim_ids.
    """
    patterns_file = DATA_DIR / "patterns" / "fraud_patterns.json"
    assert patterns_file.exists(), f"Missing patterns file at {patterns_file}"

    with open(patterns_file, "r") as f:
        cards = json.load(f)

    assert 40 <= len(cards) <= 60, f"Expected 40-60 pattern cards, got {len(cards)}"

    fraud_types = set()
    for card in cards:
        assert "pattern_id" in card and card["pattern_id"].startswith("PAT-")
        assert "fraud_type" in card
        assert "title" in card and len(card["title"]) > 5
        assert "narrative" in card and len(card["narrative"]) > 20
        assert "signature" in card and len(card["signature"]) > 10
        assert "typical_severity" in card
        assert "example_claim_ids" in card and isinstance(card["example_claim_ids"], list)
        fraud_types.add(card["fraud_type"])

    assert len(fraud_types) == 8, f"Must cover all 8 fraud types, got: {fraud_types}"


# ==============================================================================
# 5. GOLDEN CLAIM G9 PATTERN MATCH ACCEPTANCE
# ==============================================================================

def test_g9_pattern_match_acceptance():
    """
    G9 is a clean document (no math errors, no forensic tampering, no spacetime faults),
    but matches a known historical fraud pattern (e.g. shared bank account ring).
    - Surfaces pattern with similarity score >= 0.5
    - Emits finding with agent: 'rag', check_id: 'matches_known_pattern', severity: 'low'
    - Verdict does NOT exceed REVIEW (risk score <= 65).
    """
    g9_path = DEMO_DIR / "G9_pattern_match.pdf"
    assert g9_path.exists(), f"G9 PDF missing at {g9_path}"

    claim, _ = process_document_docai(g9_path, claim_id="G9-ACCEPTANCE")
    dossier = run_claims_fraud_pipeline(claim)

    # 1. Zero document-level forensic/math errors
    doc_errors = [
        f for f in dossier.findings
        if f.agent in (AgentName.FORENSICS, AgentName.SPACETIME, AgentName.INJECTION)
    ]
    assert len(doc_errors) == 0, f"G9 document should have 0 forensic/tampering errors, got: {doc_errors}"

    # 2. Surfaces RAG pattern finding
    rag_findings = [f for f in dossier.findings if f.agent == AgentName.RAG]
    assert len(rag_findings) >= 1, "G9 must surface a RAG pattern finding"
    rf = rag_findings[0]
    assert rf.severity == Severity.LOW, f"RAG finding must be capped at Severity.LOW, got {rf.severity}"
    assert "PAT-SHARED_BAN" in rf.title or "PAT-SHARED_BAN" in rf.detail or "SHARED_BAN" in rf.title

    # 3. Check retrieved_context in Dossier
    assert dossier.retrieved_context is not None and len(dossier.retrieved_context) > 0
    pattern_contexts = [c for c in dossier.retrieved_context if c.source == "pattern"]
    assert len(pattern_contexts) >= 1, "Dossier must store retrieved pattern in retrieved_context"
    top_p = pattern_contexts[0]
    assert top_p.score >= 0.5, f"Top pattern similarity score must be >= 0.5, got {top_p.score}"

    # 4. Overall verdict must NOT exceed REVIEW (can never be REJECT)
    assert dossier.verdict in (Verdict.APPROVE, Verdict.REVIEW), f"Verdict must not exceed REVIEW, got {dossier.verdict}"
    assert dossier.risk_score <= 65, f"Risk score must be <= 65, got {dossier.risk_score}"


# ==============================================================================
# 6. GUARDRAIL: RETRIEVED PATTERN CANNOT FORCE REJECT
# ==============================================================================

def test_retrieved_pattern_guardrail_cannot_force_reject():
    """
    A finding whose only evidence is a retrieved pattern is capped at severity 'low' (5 points).
    Even if an LLM incorrectly proposes severity HIGH or CRITICAL for a RAG finding,
    score_findings mathematically guarantees it cannot force a REJECT verdict.
    """
    rogue_rag_finding = Finding(
        finding_id="F-RAG-ROGUE",
        agent=AgentName.RAG,
        check_id="matches_known_pattern",
        title="Pattern Match",
        explanation="Testing rogue severity on pattern finding",
        severity=Severity.CRITICAL,  # Attempting to assign CRITICAL
        confidence=0.90,
        evidence=[Evidence(doc_id="PAT-TEST", page=1, quote="Example quote", layer="retrieved")]
    )

    # 1. On an otherwise completely clean claim
    clean_score, clean_verdict = score_findings([rogue_rag_finding])
    assert clean_score == 5, f"Expected 5 points for clamped LOW finding, got {clean_score}"
    assert clean_verdict == Verdict.APPROVE, f"Clean claim with only RAG pattern must APPROVE, got {clean_verdict}"
    assert rogue_rag_finding.severity == Severity.LOW, "score_findings must enforce severity: LOW"

    # 2. On a claim with small low-risk findings (e.g. baseline non-RAG score = 15)
    mild_finding = Finding(
        finding_id="F-CROSS-MILD",
        agent=AgentName.CROSSREF,
        check_id="HOSPITAL_VOLUME_SPIKE",
        title="Volume spike",
        explanation="Mild volume spike",
        severity=Severity.MEDIUM,
        confidence=0.85,
        evidence=[]
    )
    score, verdict = score_findings([mild_finding, rogue_rag_finding])
    assert score == 20  # 15 + 5
    assert verdict == Verdict.APPROVE

    # 3. Even with a HIGH finding (baseline score = 30), total is 35 -> REVIEW, not REJECT
    high_finding = Finding(
        finding_id="F-POL-HIGH",
        agent=AgentName.POLICY,
        check_id="ROOM_RENT_CAP",
        title="Room rent cap",
        explanation="Room rent exceeded",
        severity=Severity.HIGH,
        confidence=0.90,
        evidence=[]
    )
    score, verdict = score_findings([high_finding, rogue_rag_finding])
    assert score == 35  # 30 + 5
    assert verdict == Verdict.REVIEW, "Score 35 is REVIEW (30-69), not REJECT"


# ==============================================================================
# 7. KILL-SWITCH TEST: RAG_PATTERNS_ENABLED
# ==============================================================================

def test_rag_patterns_kill_switch(monkeypatch):
    """
    When RAG_PATTERNS_ENABLED is False in settings, pattern retrieval is skipped,
    no pattern cards are retrieved, and no RAG finding is emitted.
    """
    monkeypatch.setattr(settings, "RAG_PATTERNS_ENABLED", False)

    g9_path = DEMO_DIR / "G9_pattern_match.pdf"
    claim, _ = process_document_docai(g9_path, claim_id="G9-KILLSWITCH")
    dossier = run_claims_fraud_pipeline(claim)

    rag_findings = [f for f in dossier.findings if f.agent == AgentName.RAG]
    assert len(rag_findings) == 0, "No RAG findings should be emitted when kill-switch is active"

    if dossier.retrieved_context:
        pattern_contexts = [c for c in dossier.retrieved_context if c.source == "pattern"]
        assert len(pattern_contexts) == 0, "No pattern contexts should be stored when kill-switch is active"
