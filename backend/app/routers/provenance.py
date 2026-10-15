import asyncio
import io
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from backend.app.config import settings
from backend.app.schemas import ProvenanceVerifyResponse
from backend.services.provenance import verify_document, PUBKEY_PATH, get_verifying_key
from cryptography.hazmat.primitives import serialization

router = APIRouter(prefix="/provenance", tags=["provenance"])


@router.post("/verify", response_model=ProvenanceVerifyResponse)
async def verify_provenance_document(
    file: UploadFile = File(...),
    claim_id: Optional[str] = Form(None)
):
    """
    Verifies authenticity and tamper integrity of an outbound or submitted document.
    Recovers dual-carrier invisible watermark (XMP metadata + LSB letterhead) and checks
    cryptographic Ed25519 signature against canonical semantic fields.
    """
    if not settings.WATERMARK_ENABLED:
        return ProvenanceVerifyResponse(
            status="disabled",
            detail="Provenance verification is disabled (WATERMARK_ENABLED=False).",
            payload=None,
            carrier=None,
            diff=None,
            issued_doc_id=None
        )

    safe_name = Path(file.filename).name if file.filename else "doc.pdf"
    if not safe_name.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF documents are accepted for provenance verification.")

    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {e}")

    MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"Payload Too Large: File '{safe_name}' exceeds 25 MB limit.")

    result = await asyncio.to_thread(verify_document, contents, claim_id=claim_id)
    return ProvenanceVerifyResponse(
        status=result.get("status", "unknown"),
        detail=result.get("detail"),
        payload=result.get("payload"),
        carrier=result.get("carrier"),
        diff=result.get("diff"),
        issued_doc_id=result.get("issued_doc_id")
    )


@router.get("/pubkey")
def get_provenance_public_key():
    """
    Returns the Ed25519 public key PEM for external verifiers and third-party validation.
    """
    if PUBKEY_PATH.exists():
        with open(PUBKEY_PATH, "rb") as f:
            pem_bytes = f.read()
    else:
        pubkey = get_verifying_key()
        pem_bytes = pubkey.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    return Response(content=pem_bytes, media_type="text/plain")
