from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class DocType(str, Enum):
    BILL = "bill"
    PRESCRIPTION = "prescription"
    DISCHARGE_SUMMARY = "discharge_summary"
    LAB_REPORT = "lab_report"
    PHOTO = "photo"


class AgentName(str, Enum):
    FORENSICS = "forensics"
    POLICY = "policy"
    CROSSREF = "crossref"
    SPACETIME = "spacetime"
    ML = "ml"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Verdict(str, Enum):
    APPROVE = "approve"
    REVIEW = "review"
    REJECT = "reject"


class Claimant(BaseModel):
    claimant_id: str
    name: str
    phone: str
    bank_account_hash: str


class Provider(BaseModel):
    hospital_id: str
    name: str
    city: str
    lat: float
    lng: float


class LineItem(BaseModel):
    description: str
    qty: float
    unit_price: float
    amount: float


class Document(BaseModel):
    doc_id: str
    gcs_uri: str
    doc_type: DocType
    sha256: str
    filename: Optional[str] = None


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    insurer_id: str
    claimant: Claimant
    provider: Provider
    doctor_id: str
    admission_ts: datetime
    discharge_ts: datetime
    diagnosis_code: str
    line_items: List[LineItem] = Field(default_factory=list)
    subtotal: float
    tax: float
    total_claimed: float
    documents: List[Document] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class Evidence(BaseModel):
    doc_id: str
    page: int = 1
    bbox: Optional[List[float]] = None  # [x0, y0, x1, y1] normalized 0..1
    quote: Optional[str] = None


class Finding(BaseModel):
    finding_id: str
    agent: AgentName
    check_id: str
    severity: Severity
    title: str
    explanation: str
    evidence: List[Evidence] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class MlFeature(BaseModel):
    feature: str
    attribution: float


class TimelineEvent(BaseModel):
    ts: datetime
    lat: float
    lng: float
    place: str
    doc_id: Optional[str] = None
    actor: str  # doctor or claimant


class Dossier(BaseModel):
    claim_id: str
    risk_score: int = Field(ge=0, le=100)
    ml_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    verdict: Verdict
    summary: str
    findings: List[Finding] = Field(default_factory=list)
    top_ml_features: Optional[List[MlFeature]] = None
    timeline: Optional[List[TimelineEvent]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClaimSummary(BaseModel):
    claim_id: str
    policy_id: str
    insurer_id: str
    claimant_name: str
    hospital_name: str
    city: str
    total_claimed: float
    admission_ts: datetime
    discharge_ts: datetime
    diagnosis_code: str
    doc_count: int
    created_at: datetime
    verdict: Optional[Verdict] = None
    risk_score: Optional[int] = None
