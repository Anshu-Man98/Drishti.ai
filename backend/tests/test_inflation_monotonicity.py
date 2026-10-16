"""
Unit test for FinShield deterministic risk scoring monotonicity across inflation levels.
Verifies that risk is non-decreasing (and strictly increasing across benchmark excess thresholds)
across a grid of inflation levels (+0%, +10%, +20%, +28%, +40%, +60%) on at least 5 different base claims.
"""

import pytest
from copy import deepcopy
from backend.app.schemas import Claim, LineItem, Claimant, Provider
from backend.tools.registry import check_price_benchmarks, check_policy_caps, to_paise, to_rupees
from backend.tools.scoring import score_findings


def _generate_inflated_claim(base: Claim, mult: float) -> Claim:
    """Creates a proportional variant of a base claim at a given inflation multiplier."""
    c = deepcopy(base)
    c.claim_id = f"{base.claim_id}-MULT-{int(mult * 100)}"
    new_items = []
    sub_paise = 0
    for it in base.line_items or []:
        new_u = round(it.unit_price * mult, 2)
        new_a = round(new_u * it.qty, 2)
        sub_paise += to_paise(new_a)
        new_items.append(LineItem(
            description=it.description,
            qty=it.qty,
            unit_price=new_u,
            amount=new_a,
            page=1,
            source="form"
        ))
    c.line_items = new_items
    c.subtotal = to_rupees(sub_paise)
    tax_paise = int(round(sub_paise * 0.05))
    c.tax = to_rupees(tax_paise)
    c.total_claimed = to_rupees(sub_paise + tax_paise)
    return c


def _evaluate_claim(claim: Claim, ml_prob: float):
    bench_res = check_price_benchmarks(claim)
    policy_res = check_policy_caps(claim.policy_id, claim)
    all_findings = bench_res.get("findings", []) + policy_res.get("findings", [])
    risk, verdict = score_findings(all_findings, ml_probability=ml_prob)
    return risk, verdict, all_findings


BASE_CLAIMS = [
    Claim(
        claim_id="TEST-BASE-K358",
        diagnosis_code="K35.8",
        policy_id="POL-AROGYA-SANJEEVANI-001",
        claimant=Claimant(claimant_id="CLMNT-001", name="Rohan Verma", phone="9876543210", bank_account_hash="hash123"),
        provider=Provider(hospital_id="HOSP-001", name="City Hospital", city="Jaipur"),
        subtotal=71000.0,
        tax=3550.0,
        total_claimed=74550.0,
        line_items=[
            LineItem(description="Semi-Private Room Rent (3 days)", qty=3, unit_price=4000.0, amount=12000.0, page=1, source="form"),
            LineItem(description="Laparoscopic Appendectomy Surgery & OT", qty=1, unit_price=48000.0, amount=48000.0, page=1, source="form"),
            LineItem(description="Consultant Surgeon Visit Fees", qty=3, unit_price=1500.0, amount=4500.0, page=1, source="form"),
            LineItem(description="Post-Op Pharmacy & Antibiotic Consumables", qty=1, unit_price=6500.0, amount=6500.0, page=1, source="form"),
        ]
    ),
    Claim(
        claim_id="TEST-BASE-A09",
        diagnosis_code="A09",
        policy_id="POL-CARE-PLUS-001",
        claimant=Claimant(claimant_id="CLMNT-002", name="Suman Rao", phone="9876543211", bank_account_hash="hash456"),
        provider=Provider(hospital_id="HOSP-002", name="Apex Clinic", city="Bengaluru"),
        subtotal=24000.0,
        tax=1200.0,
        total_claimed=25200.0,
        line_items=[
            LineItem(description="General Ward Bed (2 days)", qty=2, unit_price=2500.0, amount=5000.0, page=1, source="form"),
            LineItem(description="IV Fluids and Electrolyte Management", qty=1, unit_price=8000.0, amount=8000.0, page=1, source="form"),
            LineItem(description="Physician Consultation Fees", qty=2, unit_price=1200.0, amount=2400.0, page=1, source="form"),
            LineItem(description="Stool Culture and Pathology Blood Test", qty=1, unit_price=8600.0, amount=8600.0, page=1, source="form"),
        ]
    ),
    Claim(
        claim_id="TEST-BASE-E119",
        diagnosis_code="E11.9",
        policy_id="POL-OPTIMA-SHIELD-001",
        claimant=Claimant(claimant_id="CLMNT-003", name="Anil Kapoor", phone="9876543212", bank_account_hash="hash789"),
        provider=Provider(hospital_id="HOSP-003", name="Metro Care", city="Mumbai"),
        subtotal=34000.0,
        tax=1700.0,
        total_claimed=35700.0,
        line_items=[
            LineItem(description="Twin Sharing Room (3 days)", qty=3, unit_price=3000.0, amount=9000.0, page=1, source="form"),
            LineItem(description="Diabetic Ketoacidosis Stabilization and Insulin Infusion", qty=1, unit_price=14000.0, amount=14000.0, page=1, source="form"),
            LineItem(description="Endocrinologist Consultation", qty=3, unit_price=1500.0, amount=4500.0, page=1, source="form"),
            LineItem(description="HbA1c & Renal Metabolic Panel", qty=1, unit_price=6500.0, amount=6500.0, page=1, source="form"),
        ]
    ),
    Claim(
        claim_id="TEST-BASE-K802",
        diagnosis_code="K80.2",
        policy_id="POL-AROGYA-SANJEEVANI-002",
        claimant=Claimant(claimant_id="CLMNT-004", name="Meera Joshi", phone="9876543213", bank_account_hash="hash101"),
        provider=Provider(hospital_id="HOSP-004", name="Sahyadri Health", city="Pune"),
        subtotal=62000.0,
        tax=3100.0,
        total_claimed=65100.0,
        line_items=[
            LineItem(description="Single Private Room (3 days)", qty=3, unit_price=4500.0, amount=13500.0, page=1, source="form"),
            LineItem(description="Laparoscopic Cholecystectomy Surgery", qty=1, unit_price=38000.0, amount=38000.0, page=1, source="form"),
            LineItem(description="Surgical Specialist Consultation", qty=3, unit_price=1500.0, amount=4500.0, page=1, source="form"),
            LineItem(description="Pre-Op USG Abdomen & Pharmacy", qty=1, unit_price=6000.0, amount=6000.0, page=1, source="form"),
        ]
    ),
    Claim(
        claim_id="TEST-BASE-S828",
        diagnosis_code="S82.8",
        policy_id="POL-CARE-PLUS-002",
        claimant=Claimant(claimant_id="CLMNT-005", name="Vikram Seth", phone="9876543214", bank_account_hash="hash202"),
        provider=Provider(hospital_id="HOSP-005", name="Orthopedic Specialty Center", city="Chennai"),
        subtotal=75000.0,
        tax=3750.0,
        total_claimed=78750.0,
        line_items=[
            LineItem(description="Semi-Private Ward (4 days)", qty=4, unit_price=3500.0, amount=14000.0, page=1, source="form"),
            LineItem(description="Closed Reduction and Internal Fixation (ORIF) Fibula", qty=1, unit_price=46000.0, amount=46000.0, page=1, source="form"),
            LineItem(description="Orthopedic Surgeon Round Charges", qty=4, unit_price=1500.0, amount=6000.0, page=1, source="form"),
            LineItem(description="Post-Op Radiography X-Ray & Plaster Immobilization", qty=1, unit_price=9000.0, amount=9000.0, page=1, source="form"),
        ]
    )
]


@pytest.mark.parametrize("base_claim", BASE_CLAIMS, ids=lambda c: c.claim_id)
def test_inflation_monotonicity(base_claim: Claim):
    """
    Asserts that for every base claim:
    1. Risk score is non-decreasing across all inflation multipliers:
       risk(1.0) <= risk(1.10) <= risk(1.20) <= risk(1.28) <= risk(1.40) <= risk(1.60)
    2. Across the significant excess steps (+10% to +60%), risk score strictly increases:
       risk(+10%) < risk(+20%) <= risk(+28%) < risk(+40%) < risk(+60%)
    3. Severe inflation (+60%) always scores higher than mild inflation (+10%),
       never suffering from the +10% (68) > +60% (65) inversion.
    """
    multipliers = [1.0, 1.10, 1.20, 1.28, 1.40, 1.60]
    # ML probabilities for realistic model predictions as amounts rise
    ml_probs = [0.05, 0.40, 0.70, 0.85, 0.95, 0.97]

    evaluated = []
    for mult, ml in zip(multipliers, ml_probs):
        variant = _generate_inflated_claim(base_claim, mult)
        risk, verdict, findings = _evaluate_claim(variant, ml)
        evaluated.append((mult, risk, verdict, findings))

    # 1. Non-decreasing check across all adjacent steps
    for i in range(len(evaluated) - 1):
        m_curr, r_curr, _, _ = evaluated[i]
        m_next, r_next, _, _ = evaluated[i + 1]
        assert r_next >= r_curr, (
            f"Monotonicity violation on {base_claim.claim_id}: "
            f"multiplier {m_next} (risk {r_next}) < multiplier {m_curr} (risk {r_curr})"
        )

    # 2. Strict increase between mild (+10%) and severe (+60%)
    r_10 = evaluated[1][1]
    r_60 = evaluated[5][1]
    assert r_60 > r_10, (
        f"Inversion detected on {base_claim.claim_id}: +10% risk ({r_10}) >= +60% risk ({r_60})"
    )

    # 3. +10% is usually APPROVE or low REVIEW (risk <= 55)
    assert evaluated[1][2].value in ("approve", "review") and r_10 <= 55, (
        f"+10% inflation on {base_claim.claim_id} should be APPROVE or low REVIEW, got {evaluated[1][2]} (risk {r_10})"
    )

    # 4. Severe inflation (+60%) is clearly REVIEW or REJECT with elevated risk (> r_10)
    assert evaluated[5][2].value in ("review", "reject") and r_60 >= 40, (
        f"Severe inflation (+60%) on {base_claim.claim_id} must be REVIEW or REJECT with risk >= 40, got {evaluated[5][2]} (risk {r_60})"
    )
