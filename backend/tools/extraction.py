"""
Document extraction interface for FinShield.
Powered by Google Cloud Document AI (Invoice Parser) and layout engine.
"""

from typing import Optional
from backend.app.schemas import Claim
from backend.tools.docai import process_document_docai


def extract_claim(doc_bytes: bytes, filename: str = "claim.pdf") -> Claim:
    """
    Standard interface to extract a normalized Claim schema and entities from an uploaded document.
    """
    claim, entities = process_document_docai(doc_bytes, filename=filename)
    return claim
