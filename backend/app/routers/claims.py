import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Response, Header, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse

from backend.app.schemas import (
    Claim, Document, DocType, Claimant, Provider, LineItem, Dossier, ClaimSummary, Verdict,
    ChatMessage, ChatRequest, ChatResponse, Evidence, IssueApprovalRequest, IssueApprovalResponse
)
from backend.agents.chat import stream_chat_response
from backend.app.config import settings
from backend.app.services.storage import storage_service
from backend.app.services.db import db_service
from backend.app.dependencies import require_adjuster_role

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
    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
    ALLOWED_EXTS = {".pdf", ".png", ".jpg", ".jpeg"}

    for f in files:
        contents = await f.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Payload Too Large: File '{f.filename}' exceeds 25 MB size limit."
            )

        safe_filename = Path(f.filename).name if f.filename else f"doc_{uuid.uuid4().hex[:8]}.pdf"
        ext = Path(safe_filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type '{ext}' for file '{safe_filename}'. Allowed types: {', '.join(sorted(ALLOWED_EXTS))}"
            )

        uri, sha256_hash = storage_service.upload_file(contents, safe_filename, claim_id)
        doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
        
        # Determine doc_type heuristically if not specified
        doc_type = DocType.BILL
        fname_lower = safe_filename.lower()
        if "prescription" in fname_lower:
            doc_type = DocType.PRESCRIPTION
        elif "discharge" in fname_lower:
            doc_type = DocType.DISCHARGE_SUMMARY
        elif "lab" in fname_lower:
            doc_type = DocType.LAB_REPORT
        elif any(e in fname_lower for e in [".jpg", ".jpeg", ".png"]):
            doc_type = DocType.PHOTO

        # Extract entities and bounding boxes with Document AI / layout parser (offloaded to thread)
        if fname_lower.endswith((".pdf", ".png", ".jpg", ".jpeg")):
            try:
                from backend.tools.docai import process_document_docai
                docai_claim, docai_ents = await asyncio.to_thread(process_document_docai, contents, safe_filename, claim_id)
                extracted_entities.extend(docai_ents)
                if not parsed_line_items and docai_claim.line_items:
                    parsed_line_items = docai_claim.line_items
                else:
                    for i, it in enumerate(parsed_line_items):
                        if i < len(docai_claim.line_items):
                            it.bbox = docai_claim.line_items[i].bbox
                            it.page = docai_claim.line_items[i].page
            except Exception as e:
                from backend.app.exceptions import CloudServiceError
                if isinstance(e, CloudServiceError):
                    raise
                raise CloudServiceError(service="Document AI", message=f"Document AI extraction failed: {e}", retryable=True) from e

        documents.append(Document(
            doc_id=doc_id,
            gcs_uri=uri,
            doc_type=doc_type,
            sha256=sha256_hash,
            filename=safe_filename,
            page_count=docai_claim.documents[0].page_count if docai_claim and docai_claim.documents else 1
        ))

    # Validate and parse date fields safely
    try:
        if admission_ts:
            parsed_admission_ts = datetime.fromisoformat(admission_ts.replace("Z", "+00:00"))
        else:
            parsed_admission_ts = docai_claim.admission_ts if docai_claim else datetime.utcnow()

        if discharge_ts:
            parsed_discharge_ts = datetime.fromisoformat(discharge_ts.replace("Z", "+00:00"))
        else:
            parsed_discharge_ts = docai_claim.discharge_ts if docai_claim else datetime.utcnow()
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format for admission_ts or discharge_ts: {e}"
        )

    # Track which fields were explicitly provided via multipart form fields
    form_provided = {
        "claimant_name": claimant_name is not None,
        "hospital_name": hospital_name is not None,
        "city": city is not None,
        "doctor_id": doctor_id is not None,
        "diagnosis_code": diagnosis_code is not None,
        "admission_date": admission_ts is not None,
        "discharge_date": discharge_ts is not None,
        "subtotal": subtotal is not None,
        "tax": tax is not None,
        "total_claimed": total_claimed is not None,
        "line_items": line_items_json is not None,
        "policy_id": policy_id is not None,
        "insurer_id": insurer_id is not None
    }

    # Auto-populate missing fields from Document AI if available
    if docai_claim:
        policy_id = policy_id or docai_claim.policy_id
        insurer_id = insurer_id or docai_claim.insurer_id
        claimant_id = claimant_id or (docai_claim.claimant.claimant_id if docai_claim.claimant else f"CLMNT-{uuid.uuid4().hex[:6]}")
        claimant_name = claimant_name or (docai_claim.claimant.name if docai_claim.claimant else "Unknown Patient")
        claimant_phone = claimant_phone or (docai_claim.claimant.phone if docai_claim.claimant else "+91-9999999999")
        bank_account_hash = bank_account_hash or (docai_claim.claimant.bank_account_hash if docai_claim.claimant else "hash_default")
        hospital_id = hospital_id or (docai_claim.provider.hospital_id if docai_claim.provider else f"HOSP-{uuid.uuid4().hex[:6]}")
        hospital_name = hospital_name or (docai_claim.provider.name if docai_claim.provider else "General Hospital")
        city = city or (docai_claim.provider.city if docai_claim.provider else "New Delhi")
        lat = lat if lat is not None else (docai_claim.provider.lat if docai_claim.provider else 28.6139)
        lng = lng if lng is not None else (docai_claim.provider.lng if docai_claim.provider else 77.2090)
        doctor_id = doctor_id or docai_claim.doctor_id or "DOC-0001"
        diagnosis_code = diagnosis_code or docai_claim.diagnosis_code or "Z00.0"
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
        diagnosis_code = diagnosis_code or "Z00.0"
        subtotal = subtotal if subtotal is not None else 0.0
        tax = tax if tax is not None else 0.0
        total_claimed = total_claimed if total_claimed is not None else 0.0

    # Build genuine field sources
    resolved_field_sources: Dict[str, str] = {}
    if docai_claim and docai_claim.field_sources:
        resolved_field_sources.update(docai_claim.field_sources)
    for field_k, was_form in form_provided.items():
        if was_form:
            resolved_field_sources[field_k] = "form"

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
        field_sources=resolved_field_sources,
        metadata=docai_claim.metadata.copy() if (docai_claim and docai_claim.metadata) else {},
        created_at=datetime.utcnow()
    )

    db_service.save_claim(claim)
    return {"claim_id": claim.claim_id, "status": "created", "documents_uploaded": len(documents)}


@router.post("/direct", response_model=dict)
def create_claim_direct(claim: Claim):
    """
    JSON creation endpoint for synthetic generators and seed scripts.
    Guarded against arbitrary client-supplied file read URIs.
    """
    for doc in (claim.documents or []):
        if doc.gcs_uri:
            if doc.gcs_uri.startswith("file://"):
                path_str = doc.gcs_uri.replace("file://", "")
                resolved = Path(path_str).resolve()
                repo_root = Path(__file__).resolve().parent.parent.parent.resolve()
                allowed_roots = [
                    (repo_root / "data").resolve(),
                    (repo_root / "data" / "demo").resolve(),
                ]
                if not any(str(resolved).startswith(str(root)) for root in allowed_roots):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Security error: Invalid storage URI '{doc.gcs_uri}'. Arbitrary file read attempt rejected."
                    )
            elif doc.gcs_uri.startswith("gs://"):
                if not doc.gcs_uri.startswith(f"gs://{settings.GCS_BUCKET_NAME}/uploads/"):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Security error: Invalid GCS URI '{doc.gcs_uri}'. Must be under gs://{settings.GCS_BUCKET_NAME}/uploads/"
                    )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Security error: Unsupported URI scheme in '{doc.gcs_uri}'."
                )

    if not claim.created_at:
        claim.created_at = datetime.utcnow()
    db_service.save_claim(claim)
    return {"claim_id": claim.claim_id, "status": "created"}


@router.get("", response_model=List[ClaimSummary])
def list_claims(
    response: Response,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    verdict: Optional[str] = Query(default=None),
    sort_by: Optional[str] = Query(default="created_at"),
    sort_order: Optional[str] = Query(default="desc"),
    search: Optional[str] = Query(default=None),
    exclude_synthetic: bool = Query(default=False),
):
    claims, total_count = db_service.list_claims_paged(
        limit=limit,
        offset=offset,
        verdict=verdict,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        exclude_synthetic=exclude_synthetic,
    )
    response.headers["X-Total-Count"] = str(total_count)
    return claims


@router.get("/{claim_id}", response_model=Claim)
def get_claim(claim_id: str):
    try:
        claim = db_service.get_claim(claim_id)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid claim data format: {e}")
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.get("/{claim_id}/dossier", response_model=Dossier)
def get_dossier(claim_id: str):
    dossier = db_service.get_dossier(claim_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Dossier not found for this claim")
    return dossier


from backend.agents.root import run_adk_pipeline, run_claims_fraud_pipeline


@router.get("/{claim_id}/agent-status")
def get_agent_status(claim_id: str):
    return db_service.get_agent_statuses(claim_id)


@router.post("/{claim_id}/analyze", response_model=Dossier)
def analyze_claim(claim_id: str, force: bool = False):
    """
    Runs the multi-agent fraud pipeline via ADK Runner.
    Writes Dossier to DB/Firestore.
    """
    claim = db_service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if not force:
        existing_dossier = db_service.get_dossier(claim_id)
        if existing_dossier and existing_dossier.findings:
            return existing_dossier

    dossier = run_adk_pipeline(claim)
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
    page_blob_name = f"uploads/{claim_id}/pages/page_{page_num}.png"
    page_uri = f"gs://{settings.GCS_BUCKET_NAME}/{page_blob_name}"
    try:
        content = storage_service.read_file(page_uri)
        return Response(content=content, media_type="image/png")
    except Exception:
        pass

    # Render on the fly from document if not already cached
    claim = db_service.get_claim(claim_id)
    if claim and claim.documents:
        try:
            doc_bytes = storage_service.read_file(claim.documents[0].gcs_uri)
            from backend.tools.docai import render_pdf_to_page_images
            render_pdf_to_page_images(doc_bytes, claim_id)
            content = storage_service.read_file(page_uri)
            return Response(content=content, media_type="image/png")
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


@router.post("/{claim_id}/chat")
async def chat_with_claim_dossier(
    claim_id: str,
    request: ChatRequest,
    accept: Optional[str] = Header(None)
):
    """
    Adjuster chat with the claim dossier via Server-Sent Events (SSE) or direct JSON.
    Grounded strictly on: the Dossier, all Findings, extracted Claim JSON, and policy clauses.
    """
    claim = db_service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    # If client specifically requests application/json and not text/event-stream (e.g. testing)
    if accept and "application/json" in accept and "text/event-stream" not in accept:
        final_payload = None
        async for event in stream_chat_response(claim_id, request.message):
            if event.get("done"):
                final_payload = event
        if final_payload:
            return ChatResponse(
                answer=final_payload["answer"],
                cited_finding_ids=final_payload["cited_finding_ids"],
                cited_evidence=[Evidence(**ev) if isinstance(ev, dict) else ev for ev in final_payload["cited_evidence"]]
            )

    async def sse_generator():
        async for event in stream_chat_response(claim_id, request.message):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )


@router.get("/{claim_id}/chat", response_model=List[ChatMessage])
def get_claim_chat_history(claim_id: str):
    """
    Retrieves saved adjuster chat messages for the claim.
    """
    claim = db_service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return db_service.get_chat_history(claim_id)


@router.post("/{claim_id}/issue-approval", response_model=IssueApprovalResponse)
async def issue_claim_approval(
    claim_id: str,
    request: IssueApprovalRequest,
    current_user: Dict[str, Any] = Depends(require_adjuster_role)
):
    """
    Invisibly marks and cryptographically signs an outbound approval / sanction document
    using dual-carrier redundancy (XMP Metadata + LSB Steganography) and Ed25519 digital signature.
    Restricted strictly to users with the 'adjuster' role.
    """
    if not settings.WATERMARK_ENABLED:
        raise HTTPException(status_code=400, detail="Provenance marking is currently disabled (WATERMARK_ENABLED=False).")

    claim = db_service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")

    # Bounded amount_paise check: cannot exceed total claimed amount
    max_allowed_paise = int(round(claim.total_claimed * 100))
    if request.amount_paise > max_allowed_paise:
        raise HTTPException(
            status_code=400,
            detail=f"Sanction amount ({request.amount_paise} paise) cannot exceed total claimed amount ({max_allowed_paise} paise)."
        )

    from backend.services.provenance import sign_and_mark
    doc_id = f"SANCTION-{uuid.uuid4().hex[:8].upper()}"
    fields = {
        "claim_id": claim.claim_id,
        "claimant_id": claim.claimant.claimant_id if claim.claimant else "CLMNT-UNKNOWN",
        "claimant_name": claim.claimant.name if claim.claimant else "Claimant",
        "amount_paise": request.amount_paise,
        "doc_type": "approval_letter",
        "doc_id": doc_id,
        "policy_id": claim.policy_id,
        "insurer_id": claim.insurer_id,
        "notes": request.notes or "Sanction order issued following audit review."
    }

    try:
        pdf_bytes, payload = await asyncio.to_thread(sign_and_mark, fields)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate signed document: {e}")

    filename = f"approval_{doc_id}.pdf"
    uri, sha256_hash = storage_service.upload_file(pdf_bytes, filename, claim_id)

    # Register as an issued document under the claim
    new_doc = Document(
        doc_id=doc_id,
        filename=filename,
        gcs_uri=uri,
        sha256=sha256_hash,
        doc_type=DocType.APPROVAL_LETTER,
        page_count=1
    )
    claim.documents.append(new_doc)
    db_service.save_claim(claim)

    download_url = f"/claims/{claim_id}/documents/{doc_id}"

    return IssueApprovalResponse(
        download_url=download_url,
        doc_id=doc_id,
        amount_paise=request.amount_paise,
        payload=payload
    )


