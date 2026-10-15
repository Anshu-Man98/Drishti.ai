# Drishti.ai (FinShield) 🛡️

**Track:** BFSI: Intelligent Risk, Fraud & Financial Experiences  
**One-liner:** A multi-agent claims-fraud copilot that catches forged (including AI-generated) insurance claim documents, explains every flag with evidence on the page, and trains itself against an AI fraudster.

---

## 📌 Problem & Impact
India's insurance sector loses ₹8,000–10,000 crore annually to health-claim fraud, waste, and abuse (~$6B industry-wide, 8–10% of premiums). Fraud occurs across every claim cycle through:
- Inflated & fabricated line items
- Arithmetic mismatches & policy limit breaches
- Cross-insurer duplicate submissions
- Doctor impossible-travel anomalies
- Tampered and forged documents

---

## 🏗️ Architecture & Technology Stack
Built 100% on the Google Cloud & AI ecosystem:
- **Agent Orchestration:** Google Agent Development Kit (ADK, Python) – `SequentialAgent`, `ParallelAgent`, `LlmAgent`
- **Models:** Gemini 3.1 Pro (Reasoning / Synthesizer / Audit / Red-team) & Gemini Flash (Visual Forensics, Document Extraction) via Vertex AI
- **Document Processing:** Google Cloud Document AI (Invoice & Expense Parsers) with normalized bounding-box citations
- **Policy Grounding:** Vertex AI Search (grounded retrieval on insurer policy clauses)
- **Analytics & Fraud ML:** BigQuery & BigQuery ML (`BOOSTED_TREE_CLASSIFIER`, `ML.EXPLAIN_PREDICT`)
- **Backend:** FastAPI on Google Cloud Run
- **Frontend:** React + TypeScript + Vite + Tailwind CSS on Firebase Hosting
- **Mapping:** Google Maps Platform (`@vis.gl/react-google-maps`) for spacetime feasibility checks
- **State & Storage:** Cloud Firestore (real-time agent listeners) & Google Cloud Storage

---

## 📁 Repository Layout
```text
/frontend           React + TS + Vite, Tailwind CSS, react-router (Firebase Hosting)
/backend
  /app              FastAPI application (main.py, routers/, schemas.py, services/)
  /agents           ADK agents (root.py, forensics.py, policy.py, crossref.py, spacetime.py, synthesizer.py, redteam.py)
  /tools            Deterministic tools (arithmetic.py, forensics_tools.py, geo.py, bq.py, docai.py, search.py)
  /tests            Pytest test suite
/data               Synthetic data generator, seed scripts, golden demo claim PDFs
/infra              Dockerfile, cloudbuild.yaml, BigQuery DDL, setup scripts
/docs               BUILD_PLAN.md
```

---

## 🤖 Feature 1 (F1): Four-Agent Core Pipeline

The core fraud engine runs on the **Google Agent Development Kit (ADK)** using a hybrid deterministic-reasoning pattern:
```text
ADK Root: SequentialAgent
  ├── ParallelAgent (Specialists)
  │     ├── Forensics Agent      (PDF metadata, font consistency, EXIF/ELA, SynthID*, Gemini visual review)
  │     ├── Arithmetic & Policy  (Deterministic math tools + policy rules engine citing clause IDs)
  │     └── Cross-Reference      (BigQuery warehouse lookups: exact duplicate, cross-insurer, shared accounts)
  └── Synthesizer Agent          (Gemini Pro grounded synthesis + deterministic score_findings)
```

### Deterministic Tools & Rules
- **Forensics (`backend/tools/forensics_tools.py`):**
  - Flags non-standard PDF producers (Photoshop, Canva, GIMP, online editors).
  - Inspects `CreationDate` vs `ModDate` divergence.
  - Extracts typography with `pdfplumber` to detect font family anomalies on totals/table rows and returns normalized bounding boxes.
- **Arithmetic & Policy (`backend/tools/arithmetic.py`, `backend/tools/policy_tools.py`):**
  - Reconciles quantity $\times$ unit price, subtotal sum, and tax/total with $\pm 1$ INR tolerance.
  - Checks room rent and ICU charges against policy limits (e.g. IRDAI Arogya Sanjeevani Clause 3.1 room rent cap).
- **Cross-Reference (`backend/tools/bq.py`):**
  - Parameterized warehouse lookups matching exact bill numbers and cross-insurer submissions ($\pm 3$ days, $\pm 5\%$ amount).
- **Deterministic Scoring (`backend/tools/scoring.py`):**
  - Severity weights: `info`: 0, `low`: 5, `medium`: 15, `high`: 30, `critical`: 50 (capped at 100).
  - Verdict thresholds: `approve` $< 30$, `review` $30–69$, `reject` $\ge 70$.

### Golden Claims Acceptance Matrix
| Claim | Type / Anomaly | Detected Checks | Risk Score | Verdict |
|---|---|---|---|---|
| **G1** | Clean Claim | All checks clean | 0 | **APPROVE** |
| **G2** | Padded Bill / Math Mismatch | `SUBTOTAL_SUM_MISMATCH`, `TOTAL_PAYABLE_MISMATCH` | 60 | **REVIEW** |
| **G3** | Policy Limit Breach | `POLICY_ROOM_RENT_CAP_EXCEEDED` (Clause 3.1) | 30 | **REVIEW** |
| **G4** | Cross-Insurer Duplicate | `CROSS_INSURER_DUPLICATE_CLAIM`, `EXACT_DUPLICATE_BILL` | 100 | **REJECT** |
| **G6** | Forged Bill | `SUSPICIOUS_PRODUCER_METADATA`, `FONT_INCONSISTENCY_TAMPERING`, `METADATA_DATE_DISCREPANCY` | 100 | **REJECT** |

---

## 🚀 Getting Started
Refer to [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) for the implementation roadmap and architecture details.
