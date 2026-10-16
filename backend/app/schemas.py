from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field


class DocType(str, Enum):
    BILL = "bill"
    PRESCRIPTION = "prescription"
    DISCHARGE_SUMMARY = "discharge_summary"
    LAB_REPORT = "lab_report"
    PHOTO = "photo"
    APPROVAL_LETTER = "approval_letter"
    SANCTION_ORDER = "sanction_order"


class AgentName(str, Enum):
    FORENSICS = "forensics"
    POLICY = "policy"
    CROSSREF = "crossref"
    SPACETIME = "spacetime"
    ML = "ml"
    INJECTION = "injection"
    PROVENANCE = "provenance"
    RAG = "rag"


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
    city: str = "Unknown"
    lat: float = 19.0760
    lng: float = 72.8777


class ExtractedEntity(BaseModel):
    field_name: str
    text: str
    bbox: Optional[List[float]] = None  # [x0, y0, x1, y1] normalized 0..1
    page: int = 1
    confidence: float = 1.0
    source: str = "docai"  # "docai" vs "gemini"


class LineItem(BaseModel):
    description: str
    qty: float
    unit_price: float
    amount: float
    bbox: Optional[List[float]] = None
    page: int = 1
    source: str = "docai"


class Document(BaseModel):
    doc_id: str
    gcs_uri: str
    doc_type: DocType
    sha256: str
    filename: Optional[str] = None
    page_count: int = 1


class Claim(BaseModel):
    claim_id: str
    policy_id: Optional[str] = None
    insurer_id: Optional[str] = None
    claimant: Optional[Claimant] = None
    provider: Optional[Provider] = None
    doctor_id: Optional[str] = None
    admission_ts: Optional[datetime] = None
    discharge_ts: Optional[datetime] = None
    diagnosis_code: Optional[str] = None
    line_items: List[LineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total_claimed: Optional[float] = 0.0
    documents: List[Document] = Field(default_factory=list)
    extracted_entities: List[ExtractedEntity] = Field(default_factory=list)
    field_sources: Optional[dict[str, str]] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


class Evidence(BaseModel):
    doc_id: str
    page: int = 1
    bbox: Optional[List[float]] = None  # [x0, y0, x1, y1] normalized 0..1
    quote: Optional[str] = None
    layer: Optional[str] = None  # "visible" | "hidden" | "metadata" | "retrieved" | None


class Finding(BaseModel):
    finding_id: str
    agent: AgentName
    check_id: str
    severity: Severity
    title: str
    explanation: str
    evidence: List[Evidence] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    category: Optional[str] = None
    computed_chip: Optional[str] = None
    computed_details: Optional[dict[str, Any]] = None


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
    description: Optional[str] = None


class RetrievedContext(BaseModel):
    source: str  # "policy" | "pattern"
    ref_id: str
    title: str
    snippet: str
    score: float


class Provenance(BaseModel):
    status: str  # "verified" | "tampered" | "unmarked" | "not_applicable"
    issued_doc_id: Optional[str] = None
    detail: Optional[str] = None
    diff: Optional[Dict[str, Any]] = None
    carrier: Optional[str] = None


class Dossier(BaseModel):
    claim_id: str
    risk_score: int = Field(ge=0, le=100)
    ml_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    verdict: Verdict
    status: str = Field(default="complete", description="'complete' | 'incomplete'")
    summary: str
    findings: List[Finding] = Field(default_factory=list)
    top_ml_features: Optional[List[MlFeature]] = None
    timeline: Optional[List[TimelineEvent]] = None
    retrieved_context: Optional[List[RetrievedContext]] = None
    provenance: Optional[Provenance] = None
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


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    cited_finding_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    answer: str
    cited_finding_ids: List[str] = Field(default_factory=list)
    cited_evidence: List[Evidence] = Field(default_factory=list)


class IssueApprovalRequest(BaseModel):
    amount_paise: int = Field(..., gt=0, description="Amount in paise to sanction (must be > 0)")
    notes: Optional[str] = None


class IssueApprovalResponse(BaseModel):
    download_url: str
    doc_id: str
    amount_paise: int
    payload: Dict[str, Any]


class ProvenanceVerifyResponse(BaseModel):
    status: str
    detail: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    carrier: Optional[str] = None
    diff: Optional[Dict[str, Any]] = None
    issued_doc_id: Optional[str] = None

