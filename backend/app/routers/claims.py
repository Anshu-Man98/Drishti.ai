import json
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Response
from fastapi.responses import JSONResponse

from backend.app.schemas import (
    Claim, Document, DocType, Claimant, Provider, LineItem, Dossier, ClaimSummary, Verdict
)
from backend.app.config import settings
from backend.app.services.storage import storage_service
from backend.app.services.db import db_service

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("", response_model=dict)
async def create_claim(
    policy_id: Optional[str] = Form(None),
    insurer_id: Optional[str] = Form(None),
    claimant_id: Optional[str] = Form(None),
    claimant_name: Optional[str] = Form(None),
    claimant_phone: Optional[str] = Form(None),
    bank_account_hash: Optional[str] = Form(None),
    hospital_id: Optional[str] = Form(None),
    hospital_name: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    doctor_id: Optional[str] = Form(None),
    admission_ts: Optional[str] = Form(None),
    discharge_ts: Optional[str] = Form(None),
    diagnosis_code: Optional[str] = Form(None),
    subtotal: Optional[float] = Form(None),
    tax: Optional[float] = Form(None),
    total_claimed: Optional[float] = Form(None),
    line_items_json: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[])
):
    """
    Multipart upload creating a new Claim, saving documents to Storage, and saving metadata to Database.
    Extracts entities, bounding boxes, and metadata automatically via Document AI when PDF is provided.
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
    extracted_entities = []
    docai_claim = None
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

        # Extract entities and bounding boxes with Document AI / layout parser
        if fname_lower.endswith(".pdf"):
            try:
                from backend.tools.docai import process_document_docai
                docai_claim, docai_ents = process_document_docai(contents, f.filename, claim_id)
                extracted_entities.extend(docai_ents)
                if not parsed_line_items and docai_claim.line_items:
                    parsed_line_items = docai_claim.line_items
                else:
                    for i, it in enumerate(parsed_line_items):
                        if i < len(docai_claim.line_items):
                            it.bbox = docai_claim.line_items[i].bbox
                            it.page = docai_claim.line_items[i].page
            except Exception as e:
                print(f"[create_claim] DocAI extraction notice: {e}")

        documents.append(Document(
            doc_id=doc_id,
            gcs_uri=uri,
            doc_type=doc_type,
            sha256=sha256_hash,
            filename=f.filename,
            page_count=docai_claim.documents[0].page_count if docai_claim and docai_claim.documents else 1
        ))

    # Auto-populate missing fields from Document AI if available
    if docai_claim:
        policy_id = policy_id or docai_claim.policy_id
        insurer_id = insurer_id or docai_claim.insurer_id
        claimant_id = claimant_id or docai_claim.claimant.claimant_id
        claimant_name = claimant_name or docai_claim.claimant.name
        claimant_phone = claimant_phone or docai_claim.claimant.phone
        bank_account_hash = bank_account_hash or docai_claim.claimant.bank_account_hash
        hospital_id = hospital_id or docai_claim.provider.hospital_id
        hospital_name = hospital_name or docai_claim.provider.name
        city = city or docai_claim.provider.city
        lat = lat if lat is not None else docai_claim.provider.lat
        lng = lng if lng is not None else docai_claim.provider.lng
        doctor_id = doctor_id or docai_claim.doctor_id
        parsed_admission_ts = datetime.fromisoformat(admission_ts) if admission_ts else docai_claim.admission_ts
        parsed_discharge_ts = datetime.fromisoformat(discharge_ts) if discharge_ts else docai_claim.discharge_ts
        diagnosis_code = diagnosis_code or docai_claim.diagnosis_code
        subtotal = subtotal if subtotal is not None else docai_claim.subtotal
        tax = tax if tax is not None else docai_claim.tax
        total_claimed = total_claimed if total_claimed is not None else docai_claim.total_claimed
        if not parsed_line_items:
            parsed_line_items = docai_claim.line_items
    else:
        policy_id = policy_id or "POL-STANDARD-001"
        insurer_id = insurer_id or "INS-DEFAULT"
        claimant_id = claimant_id or f"CLMNT-{uuid.uuid4().hex[:6]}"
        claimant_name = claimant_name or "Unknown Patient"
        claimant_phone = claimant_phone or "+91-9999999999"
        bank_account_hash = bank_account_hash or "hash_default"
        hospital_id = hospital_id or f"HOSP-{uuid.uuid4().hex[:6]}"
        hospital_name = hospital_name or "General Hospital"
        city = city or "New Delhi"
        lat = lat if lat is not None else 28.6139
        lng = lng if lng is not None else 77.2090
        doctor_id = doctor_id or "DOC-0001"
        parsed_admission_ts = datetime.fromisoformat(admission_ts) if admission_ts else datetime.utcnow()
        parsed_discharge_ts = datetime.fromisoformat(discharge_ts) if discharge_ts else datetime.utcnow()
        diagnosis_code = diagnosis_code or "Z00.0"
        subtotal = subtotal if subtotal is not None else 0.0
        tax = tax if tax is not None else 0.0
        total_claimed = total_claimed if total_claimed is not None else 0.0

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
        admission_ts=parsed_admission_ts,
        discharge_ts=parsed_discharge_ts,
        diagnosis_code=diagnosis_code,
        line_items=parsed_line_items,
        subtotal=subtotal,
        tax=tax,
        total_claimed=total_claimed,
        documents=documents,
        extracted_entities=extracted_entities,
        field_sources={
            "diagnosis_code": "gemini",
            "doctor_id": "gemini",
            "total_claimed": "docai",
            "line_items": "docai",
            "subtotal": "docai"
        },
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


@router.get("/{claim_id}/pages/{page_num}")
def get_claim_page_image(claim_id: str, page_num: int = 1):
    from pathlib import Path
    local_path = Path(settings.LOCAL_DATA_DIR) / "uploads" / claim_id / "pages" / f"page_{page_num}.png"
    if local_path.exists():
        with open(local_path, "rb") as f:
            return Response(content=f.read(), media_type="image/png")

    # Render on the fly from document if not already cached
    claim = db_service.get_claim(claim_id)
    if claim and claim.documents:
        try:
            doc_bytes = storage_service.read_file(claim.documents[0].gcs_uri)
            from backend.tools.docai import render_pdf_to_page_images
            render_pdf_to_page_images(doc_bytes, claim_id)
            if local_path.exists():
                with open(local_path, "rb") as f:
                    return Response(content=f.read(), media_type="image/png")
        except Exception as e:
            print(f"Error on-the-fly rendering page image: {e}")

    raise HTTPException(status_code=404, detail="Page image not found")


@router.get("/{claim_id}/entities")
def get_claim_entities(claim_id: str):
    claim = db_service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return {
        "claim_id": claim.claim_id,
        "entities": [e.model_dump() for e in claim.extracted_entities],
        "field_sources": claim.field_sources or {}
    }
