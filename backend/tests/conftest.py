import os
import io
import json
from datetime import datetime
from typing import Any, List, Dict, Optional
import pytest
from pathlib import Path

# Ensure cloud startup check and dev tokens are configured for test environment
os.environ["REQUIRE_CLOUD_ON_STARTUP"] = "false"
os.environ["ALLOW_DEV_TOKENS"] = "true"
os.environ["GOOGLE_CLOUD_PROJECT"] = "drishti-demo"
os.environ["GCP_PROJECT"] = "drishti-demo"
os.environ["BIGQUERY_DATASET"] = "finshield"
os.environ["FIRESTORE_DATABASE"] = "(default)"
os.environ["GCS_BUCKET_NAME"] = "finshield-claims-docs-drishti-demo"

# --- Client Boundary Fakes ---

class FakeDocSnapshot:
    def __init__(self, doc_id: str, data: Optional[Dict[str, Any]]):
        self.id = doc_id
        self._data = dict(data) if data is not None else None
        self.exists = data is not None

    def to_dict(self) -> Optional[Dict[str, Any]]:
        return dict(self._data) if self._data is not None else None


class FakeQuery:
    def __init__(self, docs: List[FakeDocSnapshot]):
        self._docs = list(docs)

    def stream(self):
        return iter(self._docs)

    def limit(self, n: int):
        return FakeQuery(self._docs[:n])

    def offset(self, n: int):
        return FakeQuery(self._docs[n:])

    def order_by(self, field: str, direction: Any = None):
        rev = False
        if direction is not None:
            name = getattr(direction, "name", str(direction))
            rev = "DESC" in str(name).upper()
        sorted_docs = sorted(self._docs, key=lambda d: str((d.to_dict() or {}).get(field, "")), reverse=rev)
        return FakeQuery(sorted_docs)

    def where(self, filter: Any = None):
        if filter is not None:
            field = getattr(filter, "field_path", None)
            op = getattr(filter, "op_string", "==")
            val = getattr(filter, "value", None)
            if field and op == "==":
                matched = [d for d in self._docs if (d.to_dict() or {}).get(field) == val]
                return FakeQuery(matched)
        return self


class FakeDocRef:
    def __init__(self, doc_id: str, col: Any):
        self.id = doc_id
        self._col = col
        self._subcollections: Dict[str, Any] = {}

    def set(self, data: Dict[str, Any]):
        self._col._docs[self.id] = dict(data)

    def get(self):
        data = self._col._docs.get(self.id)
        return FakeDocSnapshot(self.id, data)

    def collection(self, sub_name: str):
        if sub_name not in self._subcollections:
            self._subcollections[sub_name] = FakeCollection(sub_name)
        return self._subcollections[sub_name]


class FakeCollection:
    def __init__(self, name: str):
        self.name = name
        self._docs: Dict[str, Dict[str, Any]] = {}
        self._doc_refs: Dict[str, FakeDocRef] = {}

    def document(self, doc_id: Optional[str] = None):
        if not doc_id:
            import uuid
            doc_id = uuid.uuid4().hex
        if doc_id not in self._doc_refs:
            self._doc_refs[doc_id] = FakeDocRef(doc_id, self)
        return self._doc_refs[doc_id]

    def add(self, data: Dict[str, Any]):
        import uuid
        doc_id = uuid.uuid4().hex
        ref = self.document(doc_id)
        ref.set(data)
        return None, ref

    def stream(self):
        return (FakeDocSnapshot(k, v) for k, v in list(self._docs.items()))

    def limit(self, n: int):
        docs = [FakeDocSnapshot(k, v) for k, v in list(self._docs.items())]
        return FakeQuery(docs).limit(n)

    def offset(self, n: int):
        docs = [FakeDocSnapshot(k, v) for k, v in list(self._docs.items())]
        return FakeQuery(docs).offset(n)

    def order_by(self, field: str, direction: Any = None):
        docs = [FakeDocSnapshot(k, v) for k, v in list(self._docs.items())]
        return FakeQuery(docs).order_by(field, direction)

    def where(self, filter: Any = None):
        docs = [FakeDocSnapshot(k, v) for k, v in list(self._docs.items())]
        return FakeQuery(docs).where(filter)


class FakeFirestoreClient:
    def __init__(self):
        self._collections: Dict[str, FakeCollection] = {}

    def collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = FakeCollection(name)
        return self._collections[name]

    def get_all(self, refs: List[Any]):
        return [ref.get() for ref in refs]

    def clear(self):
        self._collections.clear()


class FakeBlob:
    def __init__(self, name: str, bucket: Any):
        self.name = name
        self.bucket = bucket

    def upload_from_string(self, data: Any):
        self.bucket._blobs[self.name] = data if isinstance(data, bytes) else data.encode("utf-8")

    def download_as_bytes(self) -> bytes:
        if self.name not in self.bucket._blobs:
            # Check demo directory fallback if asking for local demo file
            demo_file = Path(__file__).resolve().parent.parent.parent / "data" / "demo" / Path(self.name).name
            if demo_file.exists():
                return demo_file.read_bytes()
            raise Exception(f"Blob {self.name} not found in {self.bucket.name}")
        return self.bucket._blobs[self.name]


class FakeBucket:
    def __init__(self, name: str):
        self.name = name
        self._blobs: Dict[str, bytes] = {}

    def blob(self, name: str):
        return FakeBlob(name, self)


class FakeStorageClient:
    def __init__(self):
        self._buckets: Dict[str, FakeBucket] = {}

    def bucket(self, name: str):
        if name not in self._buckets:
            self._buckets[name] = FakeBucket(name)
        return self._buckets[name]

    def clear(self):
        self._buckets.clear()


class FakeBQRow:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeBQQueryJob:
    def __init__(self, rows: List[Any]):
        self._rows = rows

    def result(self):
        return iter(self._rows)


class FakeBQClient:
    def query(self, query: str, job_config: Any = None):
        q = query.upper()
        params = {}
        if job_config and getattr(job_config, "query_parameters", None):
            for p in job_config.query_parameters:
                params[p.name] = p.value

        if "ML.EXPLAIN_PREDICT" in q:
            amt_ratio = float(params.get("amount_vs_median", 1.0))
            room_ratio = float(params.get("room_rent_vs_cap", 0.8))
            cities = int(params.get("doctor_cities_24h", 1))
            shared_bank = int(params.get("shared_bank_count", 1))
            prior = int(params.get("prior_claims", 0))
            claim_amt = float(params.get("claim_amount", 50000.0))

            is_fraud = (amt_ratio > 1.25 or room_ratio > 1.1 or cities > 1 or shared_bank > 2 or prior > 1 or claim_amt > 80000)
            if is_fraud:
                fraud_prob = min(0.95, max(0.20, 0.20 + (amt_ratio - 1.0) * 0.2 + (room_ratio - 1.0) * 0.2 + (cities - 1) * 0.2 + max(0.0, (claim_amt - 75000) / 100000 * 0.2)))
                pred = 1
                prob = fraud_prob
            else:
                fraud_prob = 0.04
                pred = 0
                prob = 0.96

            top_attrs = [
                {"feature": "amount_vs_diagnosis_median_ratio", "attribution_weight": round(0.35 * (amt_ratio - 1.0), 4)},
                {"feature": "room_rent_vs_cap_ratio", "attribution_weight": round(0.25 * (room_ratio - 1.0), 4)},
                {"feature": "doctor_distinct_cities_24h", "attribution_weight": round(0.20 * (cities - 1), 4)},
                {"feature": "claimant_prior_claims_90d", "attribution_weight": round(0.10 * prior, 4)},
                {"feature": "shared_bank_account_count", "attribution_weight": round(0.10 * (shared_bank - 1), 4)},
            ]
            row = FakeBQRow(
                predicted_is_fraud=pred,
                probability=prob,
                top_feature_attributions=top_attrs
            )
            return FakeBQQueryJob([row])

        elif "COUNT(DISTINCT CLAIMANT_ID)" in q:
            bhash = params.get("bhash", "")
            cnt = 12 if ("ring" in bhash or "shared" in bhash or "G4" in bhash) else 1
            return FakeBQQueryJob([FakeBQRow(cnt=cnt)])

        elif "COUNT(CLAIM_ID)" in q:
            cid = params.get("cid", "")
            cnt = 3 if ("G4" in cid or "9901" in cid) else 0
            return FakeBQQueryJob([FakeBQRow(cnt=cnt)])

        elif "BANK_ACCOUNT_HASH" in q:
            cname = str(params.get("cname", "")).lower()
            if "kavita" in cname or "g9" in cname or "ring" in cname:
                return FakeBQQueryJob([FakeBQRow(bank_account_hash="bank_ring_shared_hash_9999")])
            return FakeBQQueryJob([FakeBQRow(bank_account_hash="clean_hash_11")])

        elif "DOCTOR_EVENTS" in q or "DOCTOR_ID" in q:
            doc_id = params.get("doctor_id") or params.get("doc_id", "")
            rows = []
            if doc_id in ["DOC-9021", "DOC-G5"] or "9021" in str(doc_id) or "G5" in str(doc_id):
                rows.append(FakeBQRow(
                    claim_id="CLM-WAREHOUSE-MUM-8821",
                    event_id="EVT-MUM-8821",
                    doctor_id=doc_id,
                    ts=datetime(2026, 7, 20, 15, 40),
                    hospital_name="Lifeline Super Speciality Hospital",
                    city="Mumbai",
                    lat=19.0596,
                    lng=72.8295
                ))
            return FakeBQQueryJob(rows)

        elif "CLAIMANT_ID = @CLAIMANT_ID" in q or ("INSURER_ID" in q and "TOTAL_CLAIMED" in q and "ADMISSION_TS" in q):
            cid = params.get("claimant_id", "")
            if cid in ["CLMNT-9901", "CLMNT-G4"] or "9901" in str(cid):
                return FakeBQQueryJob([FakeBQRow(
                    claim_id="CLM-STAR-77102",
                    claimant_id=cid,
                    insurer_id="INS-STAR",
                    total_claimed=80850.0,
                    admission_ts=datetime(2026, 6, 7, 11, 0)
                )])
            return FakeBQQueryJob([])

        elif "BILL_NUMBER" in q:
            bnum = params.get("bill_number", "")
            if "88219" in str(bnum):
                return FakeBQQueryJob([FakeBQRow(
                    claim_id="CLM-STAR-77102",
                    hospital_name="Apex Super Speciality Hospital",
                    total_claimed=80850.0,
                    bill_number=bnum
                )])
            return FakeBQQueryJob([])

        elif "EXT_PROVIDER_FRAUD" in q:
            return FakeBQQueryJob([])

        return FakeBQQueryJob([])


# Fake Document AI
class MockVertex:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class MockBoundingPoly:
    def __init__(self, bbox):
        self.normalized_vertices = [
            MockVertex(bbox[0], bbox[1]),
            MockVertex(bbox[2], bbox[1]),
            MockVertex(bbox[2], bbox[3]),
            MockVertex(bbox[0], bbox[3]),
        ]

class MockPageRef:
    def __init__(self, page, bbox):
        self.page = max(0, page - 1)
        self.bounding_poly = MockBoundingPoly(bbox) if bbox else None

class MockPageAnchor:
    def __init__(self, page, bbox):
        self.page_refs = [MockPageRef(page, bbox)]

class MockEntityProp:
    def __init__(self, type_, text):
        self.type_ = type_
        self.mention_text = str(text)
        self.normalized_value = type("Norm", (), {"text": str(text)})()

class MockEntity:
    def __init__(self, type_, text, bbox=None, page=1, properties=None):
        self.type_ = type_
        self.mention_text = str(text)
        self.confidence = 0.98
        self.normalized_value = type("Norm", (), {"text": str(text)})()
        self.page_anchor = MockPageAnchor(page, bbox) if bbox else None
        self.properties = properties or []

class FakeDocAIClient:
    def __init__(self, *args, **kwargs):
        pass

    def process_document(self, request=None):
        raw_doc = getattr(request, "raw_document", None)
        pdf_bytes = getattr(raw_doc, "content", b"")
        from backend.tools.docai import _parse_invoice_layout
        import pdfplumber
        claim, ents = _parse_invoice_layout(pdf_bytes, "doc.pdf", "test_claim", 1)
        mock_entities = []
        for e in ents:
            if e.field_name == "supplier_name":
                mock_entities.append(MockEntity("supplier_name", e.text, bbox=e.bbox, page=e.page))
            elif e.field_name == "patient_name":
                mock_entities.append(MockEntity("receiver_name", e.text, bbox=e.bbox, page=e.page))
            elif e.field_name == "total_amount":
                mock_entities.append(MockEntity("total_amount", e.text, bbox=e.bbox, page=e.page))
            elif e.field_name == "net_amount":
                mock_entities.append(MockEntity("net_amount", e.text, bbox=e.bbox, page=e.page))
            elif e.field_name == "total_tax_amount":
                mock_entities.append(MockEntity("total_tax_amount", e.text, bbox=e.bbox, page=e.page))

        for it in claim.line_items:
            props = [
                MockEntityProp("line_item/description", it.description),
                MockEntityProp("line_item/quantity", it.qty),
                MockEntityProp("line_item/unit_price", it.unit_price),
                MockEntityProp("line_item/amount", it.amount)
            ]
            mock_entities.append(MockEntity("line_item", it.description, bbox=it.bbox, page=it.page, properties=props))

        raw_text = ""
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                raw_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            raw_text = ""

        doc = type("Doc", (), {"entities": mock_entities, "text": raw_text})()
        return type("Resp", (), {"document": doc})()


# Fake Gemini
class FakeGenAIModels:
    def generate_content(self, model=None, contents=None, config=None):
        prompt_str = str(contents)
        if "Fraudster" in prompt_str or "adversarial" in prompt_str.lower() or "mutation" in prompt_str.lower():
            mutation_data = {
                "tactic": "Subtle Line-Item Padding with Integer Arithmetic Balancing",
                "rationale": "Increases unit prices uniformly across services",
                "target_multiplier": 1.25,
                "manipulation_type": "subtle_padding",
                "line_item_mutations": [
                    {"description": "Specialist Consult", "qty": 2.0, "unit_price": 2500.0, "amount": 5000.0, "category": "consultation"},
                    {"description": "Room Rent", "qty": 2.0, "unit_price": 4375.0, "amount": 8750.0, "category": "room_rent"},
                    {"description": "Diagnostic Panel", "qty": 1.0, "unit_price": 4375.0, "amount": 4375.0, "category": "investigations"},
                    {"description": "Pharmacy & Fluids", "qty": 1.0, "unit_price": 5625.0, "amount": 5625.0, "category": "pharmacy"}
                ]
            }
            return type("GenAIResp", (), {"text": json.dumps(mutation_data)})()
        elif "forensic" in prompt_str.lower() or "visual" in prompt_str.lower():
            return type("GenAIResp", (), {"text": "Visual review of region: Confirmed noticeable font family and weight disparity compared to surrounding tabular text."})()
        
        sys_inst = ""
        if config and hasattr(config, "system_instruction"):
            sys_inst = str(config.system_instruction)

        if "instruction_to_ai" in sys_inst or "untrusted_extracted_text" in prompt_str:
            p_lower = prompt_str.lower()
            if any(k in p_lower for k in ["watermark", "xmpmeta", "provenance", "adobe pdf library"]):
                resp_json = {
                    "classification": "benign_metadata",
                    "rationale": "Standard document metadata and watermark markers.",
                    "quoted_excerpt": "Watermark metadata"
                }
            elif any(k in p_lower for k in ["approve", "ignore", "override", "instruction", "system:"]):
                resp_json = {
                    "classification": "instruction_to_ai",
                    "rationale": "Adversarial prompt injection instructing AI reviewer to approve claim.",
                    "quoted_excerpt": "hidden prompt injection"
                }
            else:
                resp_json = {
                    "classification": "benign_metadata",
                    "rationale": "Benign background text.",
                    "quoted_excerpt": ""
                }
            return type("GenAIResp", (), {"text": json.dumps(resp_json)})()

        return type("GenAIResp", (), {"text": "Analysis response"})()

    def generate_content_stream(self, model=None, contents=None, config=None):
        import re
        prompt_str = str(contents)
        finding_ids = re.findall(r"\[(F\d+|F-[A-Z0-9_\-]+)\]", prompt_str)

        if "capital of france" in prompt_str.lower():
            text = "I cannot answer this question because it is not in the case file."
        elif "why was this flagged" in prompt_str.lower():
            fid = next((f for f in finding_ids if "TOTAL" in f), next((f for f in finding_ids if "MATH" in f or "ARITH" in f), finding_ids[0] if finding_ids else "F1"))
            text = f"Based on the case file [{fid}], the claim was flagged because the line item sum does not match the total payable."
        elif "which policy clause applies" in prompt_str.lower():
            fid = next((f for f in finding_ids if "POLICY" in f or "CAP" in f), finding_ids[0] if finding_ids else "F1")
            text = f"According to the case file [{fid}], Clause 3.1 regarding the room rent cap of ₹5,000 per day applies to this claim."
        elif "strongest evidence" in prompt_str.lower():
            fid = next((f for f in finding_ids if "FOREN" in f or "MODDATE" in f or "PRODUCER" in f or "FONT" in f), finding_ids[0] if finding_ids else "F1")
            text = f"The strongest evidence is documented in finding [{fid}] regarding forensic alterations, Photoshop producer tags, and metadata tampering."
        else:
            fid = finding_ids[0] if finding_ids else "F1"
            text = f"Based on the case file [{fid}], the claim analysis shows the reported findings."

        return iter([type("Chunk", (), {"text": text})()])


class FakeGenAIClient:
    def __init__(self, *args, **kwargs):
        self.models = FakeGenAIModels()


# Initialize singleton test fakes
fake_fs = FakeFirestoreClient()
fake_storage = FakeStorageClient()
fake_bq = FakeBQClient()

# Now safely import application modules
from backend.app.config import settings
from backend.app.services.db import db_service
from backend.app.services.storage import storage_service
from backend.tools.bq import bq_warehouse
from backend.app.main import app
from backend.app.dependencies import get_current_user

# Wire test fakes into services
db_service._fs_client = fake_fs
storage_service._client = fake_storage
bq_warehouse._client = fake_bq


@pytest.fixture(scope="session", autouse=True)
def setup_test_boundary_fakes():
    """Sets up client boundary fakes for Document AI and Gemini during tests."""
    from unittest.mock import patch
    with patch("google.cloud.documentai_v1.DocumentProcessorServiceClient", FakeDocAIClient), \
         patch("google.genai.Client", FakeGenAIClient):
        yield


@pytest.fixture(scope="function", autouse=True)
def isolated_test_environment():
    """Ensures test database, storage, and Gemini client are isolated and reset before and after each test."""
    from backend.app.services.gemini_client import reset_gemini_client
    reset_gemini_client()
    fake_fs.clear()
    fake_storage.clear()
    yield
    reset_gemini_client()
    fake_fs.clear()
    fake_storage.clear()


@pytest.fixture
def auth_headers():
    """Default bearer token headers for tests requiring explicit Authorization headers."""
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def auth_client():
    """TestClient instance pre-configured with default Authorization bearer token."""
    from fastapi.testclient import TestClient
    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer test-token"})
    return c


@pytest.fixture(autouse=True)
def override_auth_default():
    """
    Default autouse fixture providing an authenticated adjuster principal
    for existing functional and regression test suites.
    Dedicated security tests can clear or override this fixture.
    """
    app.dependency_overrides[get_current_user] = lambda: {
        "uid": "test-adjuster-1",
        "email": "adjuster@finshield.test",
        "role": "adjuster"
    }
    yield
    app.dependency_overrides.clear()
