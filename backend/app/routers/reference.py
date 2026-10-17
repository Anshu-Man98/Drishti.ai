from typing import Dict, Any
from fastapi import APIRouter

router = APIRouter(prefix="/reference", tags=["reference"])

ICD10_MAP = {
    # Musculoskeletal & Connective
    "M54": "Dorsalgia (Spinal Pain)",
    "M54.5": "Low Back Pain (Lumbago)",
    "M54.50": "Low Back Pain, Unspecified",
    "M54.2": "Cervicalgia (Neck Pain)",

    # Circulatory & Cardiac
    "I10": "Essential (Primary) Hypertension",
    "I20": "Angina Pectoris",
    "I20.9": "Angina Pectoris, Unspecified",
    "I21.9": "Acute Myocardial Infarction",
    "I25.10": "Atherosclerotic Heart Disease",

    # Endocrine & Metabolic
    "E11": "Type 2 Diabetes Mellitus",
    "E11.9": "Type 2 Diabetes Without Complications",
    "E11.65": "Type 2 Diabetes with Hyperglycemia",

    # Respiratory
    "J18": "Pneumonia",
    "J18.9": "Pneumonia, Unspecified Organism",
    "J06.9": "Acute Upper Respiratory Infection",
    "J45.909": "Unspecified Asthma, Uncomplicated",

    # Digestive
    "K35": "Acute Appendicitis",
    "K35.8": "Acute Appendicitis, Other & Unspecified",
    "K35.80": "Acute Appendicitis",
    "K80": "Cholelithiasis (Gallstones)",
    "K80.0": "Calculus of Gallbladder with Acute Cholecystitis",
    "K80.2": "Calculus of Gallbladder Without Cholecystitis",
    "K80.20": "Calculus of Gallbladder (Gallstones)",
    "K29.70": "Gastritis, Unspecified",

    # Infectious
    "A09": "Infectious Gastroenteritis & Colitis",

    # Genitourinary
    "N39": "Disorders of Urinary System",
    "N39.0": "Urinary Tract Infection",
    "N20.0": "Calculus of Kidney (Kidney Stones)",

    # Injury & Trauma
    "S82": "Fracture of Lower Leg",
    "S82.2": "Fracture of Shaft of Tibia",
    "S82.201A": "Fracture of Right Tibia Shaft",
    "S82.202A": "Fracture of Left Tibia Shaft",
    "S82.8": "Fracture of Other Parts of Lower Leg",

    # General / Symptoms / Other
    "Z00.00": "General Adult Medical Examination",
    "H26.9": "Unspecified Cataract",
    "R10.9": "Abdominal Pain, Unspecified",
    "R50.9": "Fever, Unspecified",
}

INSURER_MAP = {
    "INS-HDFC": {"name": "HDFC ERGO General Insurance", "short": "HDFC ERGO"},
    "INS-STAR": {"name": "Star Health & Allied Insurance", "short": "Star Health"},
    "INS-ICICI": {"name": "ICICI Lombard General Insurance", "short": "ICICI Lombard"},
    "INS-MAX": {"name": "Niva Bupa (Max Bupa) Health", "short": "Niva Bupa"},
    "INS-NIVA": {"name": "Niva Bupa Health Insurance", "short": "Niva Bupa"},
    "INS-CARE": {"name": "Care Health Insurance", "short": "Care Health"},
    "INS-FINSHIELD": {"name": "FinShield Underwriting (Internal)", "short": "FinShield"},
    "INS-SBI": {"name": "SBI General Insurance", "short": "SBI General"},
    "INS-BAJAJ": {"name": "Bajaj Allianz General Insurance", "short": "Bajaj Allianz"},
    "INS-TATA": {"name": "Tata AIG General Insurance", "short": "Tata AIG"},
    "INS-REL": {"name": "Reliance General Insurance", "short": "Reliance Gen"},
    "INS-DIGIT": {"name": "Go Digit General Insurance", "short": "Digit"},
}

POLICY_PREFIX_MAP = {
    "POL-AROGYA": "Arogya Sanjeevani Plan",
    "POL-CARE": "Care Comprehensive Health Plan",
    "POL-OPTIMA": "Optima Secure & Restore",
    "POL-STAR": "Star Comprehensive Health",
    "POL-FAMILY": "Family Health Optima",
    "POL-MEDICLAIM": "Individual Comprehensive Mediclaim",
    "POL-SUPER": "Super Top-up Floater",
    "POL-SENIOR": "Senior Citizens Red Carpet",
    "POL-CRITICAL": "Critical Illness Protection",
    "POL-CORONA": "Corona Kavach Plan",
}


def normalize_icd10(code: str) -> str:
    """
    Normalizes an ICD-10 code and returns the human-readable description.
    Tries exact match, trailing-zero adjustment, and 3-character category block fallback.
    If truly unknown, returns 'description not in reference table'.
    """
    if not code:
        return "Not Specified"
    clean = code.strip().upper()
    if clean in ICD10_MAP:
        return ICD10_MAP[clean]

    # Try stripping or appending trailing zero (e.g. K35.8 <-> K35.80)
    if clean.endswith("0") and clean[:-1] in ICD10_MAP:
        return ICD10_MAP[clean[:-1]]
    if f"{clean}0" in ICD10_MAP:
        return ICD10_MAP[f"{clean}0"]

    # Try parent 3-character block (e.g. K35 from K35.8)
    prefix = clean.split(".")[0]
    if prefix in ICD10_MAP:
        return ICD10_MAP[prefix]

    return "description not in reference table"


def resolve_policy_name(policy_id: str) -> str:
    """Resolves policy ID to a readable policy product name."""
    if not policy_id:
        return "Standard Health Policy"
    clean = policy_id.strip().upper()
    for prefix, name in POLICY_PREFIX_MAP.items():
        if clean.startswith(prefix):
            return name
    return "Standard Health Policy"


@router.get("/icd10", response_model=Dict[str, str])
def get_icd10_codes():
    """Returns human-readable dictionary of ICD-10 clinical codes."""
    return ICD10_MAP


@router.get("/icd10/{code}")
def get_single_icd10(code: str):
    """Returns normalized human description for a specific ICD-10 code."""
    description = normalize_icd10(code)
    return {"code": code.strip().upper(), "description": description}


@router.get("/insurers", response_model=Dict[str, Any])
def get_insurers():
    """Returns human-readable dictionary of registered Indian health insurers."""
    return INSURER_MAP


@router.get("/policies", response_model=Dict[str, str])
def get_policies():
    """Returns standard health policy prefixes and product titles."""
    return POLICY_PREFIX_MAP
