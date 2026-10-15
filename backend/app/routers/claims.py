import json
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Response
from fastapi.responses import JSONResponse

from backend.app.schemas import (
    Claim, Document, DocType, Claimant, Provider, LineItem, Dossier, ClaimSummary, Verdict
)
from backend.app.services.storage import storage_service
from backend.app.services.db import db_service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", response_model=dict)
async def create_claim(
    policy_id: str = Form(...),
    insurer_id: str = Form(...),
    claimant_id: str = Form(...),
    claimant_name: str = Form(...),
    claimant_phone: str = Form(...),
    bank_account_hash: str = Form(...),
    hospital_id: str = Form(...),
    hospital_name: str = Form(...),
    city: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    doctor_id: str = Form(...),
    admission_ts: str = Form(...),
    discharge_ts: str = Form(...),
    diagnosis_code: str = Form(...),
    subtotal: float = Form(...),
    tax: float = Form(...),
    total_claimed: float = Form(...),
    line_items_json: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[])
):
    """
    Multipart upload creating a new Claim, saving documents to Storage, and saving metadata to Database.
    """
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"

    # Parse line items
    parsed_line_items = []
    if line_items_json:
        try:
            items_raw = json.loads(line_items_json)
            for it in items_raw:
                parsed_line_items.append(LineItem(
                    description=it.get("description", "Medical Service"),
                    qty=float(it.get("qty", 1)),
                    unit_price=float(it.get("unit_price", 0)),
                    amount=float(it.get("amount", 0))
                ))
        except Exception as e:
            print(f"Error parsing line items: {e}")

    # Process and upload attached files
    documents: List[Document] = []
    for f in files:
        contents = await f.read()
        uri, sha256_hash = storage_service.upload_file(contents, f.filename, claim_id)
        doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
        
        # Determine doc_type heuristically if not specified
        doc_type = DocType.BILL
        fname_lower = (f.filename or "").lower()
        if "prescription" in fname_lower:
            doc_type = DocType.PRESCRIPTION
        elif "discharge" in fname_lower:
            doc_type = DocType.DISCHARGE_SUMMARY
        elif "lab" in fname_lower:
            doc_type = DocType.LAB_REPORT
        elif any(ext in fname_lower for ext in [".jpg", ".jpeg", ".png"]):
            doc_type = DocType.PHOTO

        documents.append(Document(
            doc_id=doc_id,
            gcs_uri=uri,
            doc_type=doc_type,
            sha256=sha256_hash,
            filename=f.filename
        ))

    claim = Claim(
        claim_id=claim_id,
        policy_id=policy_id,
        insurer_id=insurer_id,
        claimant=Claimant(
            claimant_id=claimant_id,
            name=claimant_name,
            phone=claimant_phone,
            bank_account_hash=bank_account_hash
        ),
        provider=Provider(
            hospital_id=hospital_id,
            name=hospital_name,
            city=city,
            lat=lat,
            lng=lng
        ),
        doctor_id=doctor_id,
        admission_ts=datetime.fromisoformat(admission_ts),
        discharge_ts=datetime.fromisoformat(discharge_ts),
        diagnosis_code=diagnosis_code,
        line_items=parsed_line_items,
        subtotal=subtotal,
        tax=tax,
        total_claimed=total_claimed,
        documents=documents,
        created_at=datetime.utcnow()
    )

    db_service.save_claim(claim)
    return {"claim_id": claim.claim_id, "status": "created", "documents_uploaded": len(documents)}


@router.post("/direct", response_model=dict)
def create_claim_direct(claim: Claim):
    """
    JSON creation endpoint for synthetic generators and seed scripts.
    """
    if not claim.created_at:
        claim.created_at = datetime.utcnow()
    db_service.save_claim(claim)
    return {"claim_id": claim.claim_id, "status": "created"}


@router.get("", response_model=List[ClaimSummary])
def list_claims(limit: int = 50):
    return db_service.list_claims(limit=limit)


@router.get("/{claim_id}", response_model=Claim)
def get_claim(claim_id: str):
    claim = db_service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.get("/{claim_id}/dossier", response_model=Dossier)
def get_dossier(claim_id: str):
    dossier = db_service.get_dossier(claim_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found for this claim")
    return dossier


from backend.agents.root import run_claims_fraud_pipeline

# In-memory agent status tracker for live UI feedback
_agent_statuses = {}


@router.get("/{claim_id}/agent-status")
def get_agent_status(claim_id: str):
    return _agent_statuses.get(claim_id, {
        "forensics": "idle",
        "policy": "idle",
        "crossref": "idle",
        "synthesizer": "idle"
    })


@router.post("/{claim_id}/analyze", response_model=Dossier)
def analyze_claim(claim_id: str, force: bool = False):
    """
    Runs the four-agent fraud pipeline (Forensics, Policy, CrossRef, Synthesizer).
    Writes Dossier to DB/Firestore.
    """
    claim = db_service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not force:
        existing_dossier = db_service.get_dossier(claim_id)
        if existing_dossier and existing_dossier.findings:
            return existing_dossier

    def status_callback(agent_name: str, status: str):
        if claim_id not in _agent_statuses:
            _agent_statuses[claim_id] = {}
        _agent_statuses[claim_id][agent_name] = status

    # Execute 4-agent scrutiny
    dossier = run_claims_fraud_pipeline(claim, status_callback=status_callback)
    db_service.save_dossier(dossier)
    return dossier


@router.get("/{claim_id}/documents/{doc_id}")
def get_claim_document(claim_id: str, doc_id: str):
    claim = db_service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    doc = next((d for d in claim.documents if d.doc_id == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        data = storage_service.read_file(doc.gcs_uri)
        media_type = "application/pdf" if doc.filename and doc.filename.endswith(".pdf") else "image/png"
        return Response(content=data, media_type=media_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read document: {e}")
