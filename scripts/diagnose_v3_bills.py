#!/usr/bin/env python3
"""
scripts/diagnose_v3_bills.py

Diagnoses raw Document AI and Gemini Vision extractions on:
1. data/eval_bills_v3/bill_01_uti_dehradun.pdf
2. data/eval_bills_v3/bill_02_fracture_indore.pdf

Prints:
- Raw Document AI entities (properties: quantity, unit_price, amount with confidences)
- Gemini Vision cross-check line items
- Explanation of merge behavior and quantity handling
"""

import json
from pathlib import Path
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai

from backend.app.config import settings
from backend.tools.docai import (
    render_document_to_images,
    extract_with_gemini_vision,
    _parse_amount
)


def diagnose_bill(pdf_path: Path):
    print(f"\n{'='*80}")
    print(f"DIAGNOSING: {pdf_path.name}")
    print(f"{'='*80}")

    pdf_bytes = pdf_path.read_bytes()

    # 1. Document AI
    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(api_endpoint=settings.docai_endpoint)
    )
    raw_doc = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
    request = documentai.ProcessRequest(name=settings.docai_processor_name, raw_document=raw_doc)
    docai_result = client.process_document(request=request)
    doc = docai_result.document

    print("\n--- [Document AI Raw line_item Entities] ---")
    line_item_entities = [e for e in doc.entities if e.type_ == "line_item"]
    print(f"Found {len(line_item_entities)} line_item entities in Document AI:")

    for idx, e in enumerate(line_item_entities, 1):
        print(f"\n  Entity #{idx} (confidence: {e.confidence:.4f}):")
        props = {}
        for p in e.properties:
            p_val = p.normalized_value.text if p.normalized_value and p.normalized_value.text else p.mention_text
            props[p.type_] = {
                "mention_text": p.mention_text,
                "normalized_text": p.normalized_value.text if p.normalized_value else None,
                "confidence": p.confidence,
                "parsed": _parse_amount(p_val)
            }
            print(f"    - property '{p.type_}': mention='{p.mention_text}', norm='{p.normalized_value.text if p.normalized_value else None}', conf={p.confidence:.4f}")

    # 2. Gemini Vision
    print("\n--- [Gemini Vision Cross-Check] ---")
    _, page_images = render_document_to_images(pdf_bytes, "DIAGNOSE", pdf_path.name)
    gemini_res = extract_with_gemini_vision(page_images, doc_text=doc.text, claim_id="DIAGNOSE")

    if gemini_res:
        print(f"Gemini extracted hospital_name: {gemini_res.hospital_name}")
        print(f"Gemini extracted city: {gemini_res.city}")
        print(f"Gemini extracted subtotal: {gemini_res.subtotal}, tax: {gemini_res.tax}, total: {gemini_res.total_claimed}")
        print(f"Found {len(gemini_res.line_items)} line items in Gemini Vision:")
        for idx, item in enumerate(gemini_res.line_items, 1):
            print(f"  Item #{idx}: '{item.description}' | qty={item.qty} | unit_price={item.unit_price} | amount={item.amount}")
    else:
        print("Gemini Vision returned None!")


if __name__ == "__main__":
    p_uti = Path("data/eval_bills_v3/bill_01_uti_dehradun.pdf")
    p_frac = Path("data/eval_bills_v3/bill_02_fracture_indore.pdf")
    diagnose_bill(p_uti)
    diagnose_bill(p_frac)
