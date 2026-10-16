# FinShield (Drishti.ai) 🛡️

**Track:** BFSI: Intelligent Risk, Fraud & Financial Experiences  
**One-liner:** A cloud-native, multi-agent claims-fraud copilot that catches forged medical bills and claims-fraud rings, visually grounds every finding on the document, and continuously stress-tests itself with adversarial AI dueling.

---

## 📌 Problem & Impact

India's health insurance sector loses ₹8,000–10,000 crore annually to health-claim fraud, waste, and abuse (~$6B industry-wide, 8–10% of premiums). Fraud manifests across multiple coordinated vectors:
- **Altered and Forged Invoices**: Modified totals, fake hospital letterheads, Canva/Photoshop digital tampering.
- **Arithmetic Inflation**: Fabricated quantities, unit price multiplication errors, subtotal/tax padding.
- **Policy Limit Breaches**: Room rent and ICU charges billed well above IRDAI policy caps (e.g. Arogya Sanjeevani Clause 3.1).
- **Cross-Insurer Duplicate Claims**: The same original bill submitted simultaneously to multiple insurance carriers.
- **Spacetime Impossible Travel**: Attending physicians billed as performing simultaneous procedures hundreds of kilometers apart.
- **Adversarial Prompt Injections**: Hidden white-on-white text in PDFs commanding LLMs to disregard flags and approve claims.

FinShield (Drishti.ai) solves this with a **cloud-only multi-agent inspection architecture** powered by Google Cloud and the Google Agent Development Kit (ADK).

---

## 🏗️ Cloud-Only Architecture

FinShield operates **100% on Google Cloud** and the **Google Gemini API**. There is no local mode or offline fallback engine. All application state, documents, data warehousing, and AI models execute directly against Google Cloud managed services.

```
                                  +-----------------------------------------------+
                                  |            FinShield React 19 Frontend        |
                                  |        (Interactive SVG Bounding Boxes,       |
                                  |       Document Viewer, Spacetime Maps)        |
                                  +-----------------------+-----------------------+
                                                          |
                                           Authorization: Bearer <Token>
                                                          |
                                                          v
                                  +-----------------------------------------------+
                                  |             FastAPI Backend Service           |
                                  |       (REST Endpoints, SSE Streaming, ADK)    |
                                  +-----------------------+-----------------------+
                                                          |
       +--------------------+-----------------------------+-----------------------------+--------------------+
       |                    |                             |                             |                    |
       v                    v                             v                             v                    v
+--------------+   +------------------+         +-------------------+         +--------------------+  +--------------+
| Cloud        |   | Google Cloud     |         | Google BigQuery   |         | Google Cloud       |  | Google Cloud |
| Firestore    |   | Storage (GCS)    |         | & BigQuery ML     |         | Document AI        |  | Secret Mgr   |
| (Native Mode)|   |                  |         |                   |         |                    |  |              |
| Claims,      |   | Uploaded PDFs,   |         | Claims warehouse, |         | Invoice Parser,    |  | Ed25519      |
| Dossiers,    |   | 150 DPI page     |         | doctor schedules, |         | entity extraction, |  | Provenance   |
| Chat history,|   | PNGs, signed     |         | BQML boosted tree |         | normalized         |  | Private Key  |
| Duel rounds  |   | sanction notes   |         | ML.EXPLAIN_PREDICT|         | bounding boxes     |  |              |
+--------------+   +------------------+         +-------------------+         +--------------------+  +--------------+
                                                          |
                                                          v
                                        +-----------------------------------+
                                        |         Google Gemini API         |
                                        |  (google-genai SDK, Configurable) |
                                        |  - Forensics Visual Review        |
                                        |  - Prompt Injection Classifier    |
                                        |  - Executive Dossier Synthesizer  |
                                        |  - Interactive Chat Copilot       |
                                        |  - Adversarial Fraudster Agent    |
                                        +-----------------------------------+
```

---

## ⚙️ Prerequisites & Cloud Provisioning

FinShield requires an active Google Cloud Project with the following 5 managed services and a Gemini API key:
1. **Cloud Firestore** (Native mode, e.g. `(default)`)
2. **Cloud Storage** (Bucket for claims documents and rendered page images)
3. **BigQuery** (Dataset `finshield` with warehouse tables and BQML fraud model)
4. **Cloud Document AI** (Invoice Parser processor)
5. **Cloud Secret Manager** (Secret `finshield-provenance-signing-key`)
6. **Google Gemini API Key** (or Vertex AI Application Default Credentials)

Detailed, command-by-command setup instructions are provided in:
👉 **[`docs/CLOUD_SETUP.md`](docs/CLOUD_SETUP.md)**

---

## 🚀 Running FinShield

### 1. Environment Setup
Configure your `.env` file (copied from `.env.example`):
```bash
cp .env.example .env
```
Fill in your Google Cloud and Gemini credentials:
```ini
GOOGLE_CLOUD_PROJECT=drishti-demo
GCP_PROJECT=drishti-demo
GCP_REGION=asia-south1
GCS_BUCKET_NAME=finshield-claims-docs-drishti-demo
FIRESTORE_DATABASE=(default)
BIGQUERY_DATASET=finshield

# Gemini API Key (from Google AI Studio or Vertex AI ADC)
GOOGLE_API_KEY=your_gemini_api_key_here

# Configurable Model IDs (never hardcoded)
GEMINI_PRO_MODEL=gemini-3.5-flash
GEMINI_FLASH_MODEL=gemini-3.5-flash

# Document AI (Processor deployed in US location) & Cryptographic Provenance
DOCUMENTAI_PROCESSOR_ID=projects/848168056257/locations/us/processors/8cb7d125a43425e4
DOCUMENTAI_LOCATION=us
# FINSHIELD_PROVENANCE_KEY is loaded directly from Secret Manager: finshield-provenance-signing-key

# Cloud Enforcement
REQUIRE_CLOUD_ON_STARTUP=true
ALLOW_DEV_TOKENS=true
```

### 2. Seed Cloud Data & Warehouse
All warehouse records and claims data are **synthetic**, modeled after IRDAI Indian health insurance standards. Seed them into Cloud Firestore, Cloud Storage, and BigQuery idempotently:
```bash
# Dry-run preview:
python scripts/seed_cloud.py --dry-run

# Apply to Google Cloud:
python scripts/seed_cloud.py --apply
```

### 3. Launch Backend API (FastAPI)
```bash
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health) (validates live connectivity to Firestore, GCS, BigQuery, Document AI, and Gemini).

### 4. Launch Frontend Dashboard (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
- Web Application: [http://localhost:3000](http://localhost:3000)

---

## 🤖 Multi-Agent Engine: Gemini vs. Deterministic Tools

FinShield orchestrates specialists using the **Google Agent Development Kit (ADK)**:
```text
ADK Root: SequentialAgent (root.py)
  ├── ParallelAgent (Specialist Audits)
  │     ├── Forensics Agent      (PDF producer, font consistency, Gemini visual review)
  │     ├── Arithmetic & Policy  (Integer paise math + IRDAI policy limit engine)
  │     ├── Cross-Reference      (BigQuery warehouse queries: duplicates, shared accounts)
  │     ├── Spacetime Agent      (Haversine transit physics + schedule feasibility)
  │     ├── Injection Agent      (Hidden text extraction + Gemini safety classification)
  │     └── Provenance Agent     (Ed25519 asymmetric signature & watermark verification)
  └── Synthesizer Agent          (Gemini Pro grounded narrative + deterministic hybrid scoring)
```

### Which Agents Use Google Gemini:
- **Forensics Agent**: Calls `gemini_visual_review` using `GEMINI_FLASH_MODEL` to inspect high-resolution bill renderings for digital tampering, mismatched seals, and font anomalies.
- **Injection Agent**: Calls `classify_hidden_text` using `GEMINI_FLASH_MODEL` to inspect extracted hidden text layers for adversarial prompt injections.
- **Synthesizer Agent**: Calls `GEMINI_PRO_MODEL` with system instructions to author an executive audit summary that directly cites specific Finding IDs.
- **Adjuster Chat Copilot**: Streams conversational answers via SSE using `GEMINI_FLASH_MODEL` / `GEMINI_PRO_MODEL` with strict numeric grounding against verified tool calculations.
- **Adversarial Fraudster (F6 Dueling AI)**: An ADK `LlmAgent` using `GEMINI_FLASH_MODEL` that red-teams the pipeline by mutating claims to discover evasion opportunities.

### Which Tools Are Strictly Deterministic (No LLM Math or Hallucinations):
- **Integer Paise Arithmetic (`backend/tools/arithmetic.py`)**: All calculations (quantities $\times$ unit rates, line item totals, taxes, deductions) are performed in 64-bit integer paise (`₹1 = 100 paise`), eliminating floating-point rounding errors.
- **Spacetime Transit Math (`backend/agents/spacetime.py`, `backend/tools/geo.py`)**: Computes great-circle haversine distances and travel velocity between hospital locations (<900 km/h airline, <120 km/h ground).
- **Policy Limit Engine (`backend/agents/policy.py`)**: Evaluates IRDAI Arogya Sanjeevani Clause 3.1 room rent caps (₹5,000/day) and Clause 3.2 ICU caps (₹10,000/day).
- **Hybrid Scoring Formula (`backend/tools/scoring.py`)**:
  $$\text{Score} = \min\left(100, \text{round}(0.6 \times \text{AgentScore} + 40 \times \text{ML\_Probability})\right)$$
  - **APPROVE**: Score $< 30$
  - **REVIEW**: Score $30 - 69$
  - **REJECT**: Score $\ge 70$
- **Numeric Grounding Guard (`backend/tools/grounding.py`)**: Scans all LLM text against an in-memory registry of computed values to redact or flag any hallucinated numbers.
- **PDF Font & XMP Inspection (`backend/tools/forensics_tools.py`)**: Detects font family anomalies across line items and flags desktop publishing tools in PDF Producer metadata.

---

## 🎯 Golden Acceptance Claims Matrix

FinShield includes 9 canonical golden demo claims (G1–G9) demonstrating end-to-end detection:

| Claim | Anomaly Type | Key Detected Findings | Risk Score | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **G1** | Clean Claim | All forensic, math, policy, and warehouse checks clean | 0 / 100 | **APPROVE** |
| **G2** | Padded Bill / Math Mismatch | `SUBTOTAL_SUM_MISMATCH`, `TOTAL_PAYABLE_MISMATCH` | 60 / 100 | **REVIEW** |
| **G3** | Policy Limit Breach | `POLICY_ROOM_RENT_CAP_EXCEEDED` (Clause 3.1) | 30 / 100 | **REVIEW** |
| **G4** | Cross-Insurer Duplicate | `CROSS_INSURER_DUPLICATE_CLAIM`, `EXACT_DUPLICATE_BILL` | 100 / 100 | **REJECT** |
| **G5** | Spacetime Impossible Travel | `DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL` (1,150 km in 90 min) | 100 / 100 | **REJECT** |
| **G6** | Forged Hospital Bill | `SUSPICIOUS_PRODUCER_METADATA`, `FONT_INCONSISTENCY_TAMPERING` | 100 / 100 | **REJECT** |
| **G7** | Prompt Injection Attack | `PROMPT_INJECTION_DETECTED` (white-on-white text layer) | 80 / 100 | **REJECT** |
| **G8** | Tampered Sanction Note | `PROVENANCE_SIGNATURE_INVALID`, `HASH_MISMATCH` | 90 / 100 | **REJECT** |
| **G9** | Complex Multi-Vector | Multi-vector fraud: font forgery + policy cap + duplicate bill | 100 / 100 | **REJECT** |

---

## 🧪 Verification & Continuous Integration

- **Run Backend Pytest Suite**:
  ```bash
  PYTHONPATH=. .venv/bin/pytest backend/tests -q
  ```
- **Run Frontend Build**:
  ```bash
  cd frontend && npm run build
  ```
- **Automated CI**: GitHub Actions workflow at `.github/workflows/ci.yml` validates all backend tests and frontend compilation on pull requests and pushes to `main`.
