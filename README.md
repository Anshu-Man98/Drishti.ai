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

## 🚀 Getting Started
Refer to [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) for the implementation roadmap and architecture details.
