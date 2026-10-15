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
| **G5** | Spacetime Impossible Travel | `DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL` (1,150 km in 90 min) | 100 | **REJECT** |
| **G6** | Forged Bill | `SUSPICIOUS_PRODUCER_METADATA`, `FONT_INCONSISTENCY_TAMPERING`, `METADATA_DATE_DISCREPANCY` | 100 | **REJECT** |

---

## 📄 Feature 2 (F2): Document AI Extraction + Bounding-Box Citations

FinShield grounds every claim audit in the visual source document using **Google Cloud Document AI** and interactive SVG bounding box overlays:

### Capabilities & Architecture
- **High-Resolution Page Rendering:**
  - `pypdfium2` renders PDF pages to crisp 150 DPI PNG images (`/claims/{claim_id}/pages/{page_num}`).
- **Normalized Entity & Table Extraction (`backend/tools/docai.py`):**
  - Maps invoice headers, patient profile, policy clauses, line items, and totals into structured schema with normalized bounding boxes `[x0, y0, x1, y1]`.
  - Seamlessly integrates with Google Cloud Document AI Invoice Processor, with deterministic layout engine fallback for local evaluation.
- **Evidence Grounding via `locate_field`:**
  - `locate_field(doc_id, field_path, claim) -> Evidence`: Maps any logical claim field (e.g. `total_claimed`, `subtotal`, `line_items.room_rent`) to its exact coordinates on the page.
  - Forensic font tampering detections, subtotal sum discrepancies, and room rent cap breaches carry precise bounding boxes in `finding.evidence`.
- **Interactive Document Viewer (`frontend/src/components/DocumentViewer.tsx`):**
  - Side-by-side split layout in `ClaimDetail.tsx`.
  - SVG overlay with color-coded bounding boxes by severity (Red: Critical, Orange: High, Yellow: Medium, Blue: Low, Slate: Extracted fields).
  - Bi-directional interactivity: Clicking an anomaly in the dossier focuses and pulses the citation on the document; clicking a box on the document selects the anomaly card.
  - Controls: Zoom (75%–200%), Page Navigation, View mode toggle (Split / Document Focus / Audit Focus), and "Flags Only" vs "Show All Fields" toggle.

---

## 📈 Feature 3 (F3): BigQuery ML Fraud Score + Feature Explanations

FinShield implements a production-grade **"ML Scores, Gemini Explains"** pattern combining BigQuery ML gradient boosted trees with ADK multi-agent synthesis:

```text
ADK Parallel Specialists
  ├── Forensics Agent
  ├── Policy & Arithmetic Agent
  └── Cross-Reference Agent
        │
        ▼
BigQuery ML Step (`ML.EXPLAIN_PREDICT`)
  ├── 10 Engineered Features (Diagnosis median ratios, caps, travel velocity, duplicate rings)
  ├── Gradient Boosted Tree Classifier (`BOOSTED_TREE_CLASSIFIER`)
  └── Top 5 Feature Attributions (SHAP / attribution weights)
        │
        ▼
Synthesizer Agent (Gemini Pro)
  ├── Deterministic Hybrid Score: round(0.6 * Agent_Score + 40 * ML_Probability)
  └── Plain-language Adjuster Narrative explaining ML score and primary risk drivers
```

### 1. BigQuery ML DDL & Production Architecture (`infra/bqml.sql`)
- **Claim Fraud Model (`finshield.fraud_model`):**
  - Algorithm: `BOOSTED_TREE_CLASSIFIER`, `LEARN_RATE=0.1`, `MAX_ITERATIONS=60`, `EARLY_STOP=TRUE`, `ENABLE_GLOBAL_EXPLAIN=TRUE`.
  - Offline Evaluation Benchmark on 1,000 synthetic claims:
    - **ROC AUC:** `0.9020`
    - **Precision:** `0.9250`
    - **Recall:** `0.5068`
    - **F1 Score:** `0.6549`
  - Top 3 Attributions: `amount_vs_diagnosis_median_ratio` (33.0%), `doctor_distinct_cities_24h` (20.3%), `room_rent_vs_cap_ratio` (13.2%).
- **Provider Fraud Model (`finshield.provider_fraud_model`):**
  - Trained on real-world Kaggle Medicare Inpatient/Outpatient Provider fraud dataset (5,410 providers).
  - Benchmark: **ROC AUC:** `0.9418`, **Precision:** `0.9420`, **Recall:** `0.6842`, **F1:** `0.7927`.
  - Comprehensive documentation and metric tables available at [`docs/model_eval.md`](docs/model_eval.md).

### 2. Dual-Path Inference (`backend/tools/bq.py`)
- **Live Cloud Path:** Calls `ML.EXPLAIN_PREDICT` on BigQuery model with `top_k_features=5`.
- **Local Fallback Path:** Uses serialized model artifact (`data/fraud_model.joblib`) for offline testing and air-gapped evaluation.
- Clean claim G1 scores low probability (`0.0267`, 2.7%), while high-risk fraudulent claims score up to `0.9962` (99.6%).

### 3. Deterministic Hybrid Scoring Formula (`backend/tools/scoring.py`)
$$\text{final\_risk\_score} = \text{round}(0.6 \times \text{agent\_score} + 40 \times \text{ml\_probability})$$
- Specialist agent findings provide high-fidelity rule/forensic grounding (60% weight).
- BigQuery ML provides statistical population-level pattern recognition (40% weight).
- Claims with $\text{ml\_probability} > 0.60$ automatically emit an ML anomaly finding (`check_id: BQML_HIGH_RISK_ANOMALY`).

### 4. Interactive Frontend Visualization (`frontend/src/pages/ClaimDetail.tsx`)
- **Side-by-Side Dual Score Breakdown:** Displays Agent Heuristic Score and BigQuery ML Fraud Probability side-by-side with the unified Hybrid Risk badge.
- **6-Agent Pipeline Status Grid:** Real-time execution indicators for Forensics, Policy & Math, Cross-Ref, Spacetime, BigQuery ML, and Synthesizer.
- **Explainability Horizontal Bar Chart:** Interactive visual representation of top 5 feature attributions with color-coded risk drivers (red/amber) vs reassuring baseline factors (emerald/blue).

---

## 🗺️ Feature 4 (F4): Spacetime Impossibility Detection & GIS Trajectory Map

FinShield detects physically impossible transit timelines between consecutive events for doctors or claimants across hospitals and cities:

```text
Claim Documents (Admission, Procedures, Discharge)
                  │
                  ▼
build_timeline(claim)  ◄─── BigQuery Claims Warehouse (Doctor Events ±24h)
                  │
                  ▼
SpacetimeAgent (Google ADK LlmAgent / Gemini Flash)
  ├── Consecutive transit pairs grouped per actor
  └── Deterministic Physics Engine (`backend/tools/geo.py`)
        ├── haversine_km(lat1, lon1, lat2, lon2)
        ├── min_travel_hours(km):
        │     - Road (<= 300 km): km / 80 km/h
        │     - Air  (> 300 km): 2.5h overhead + km / 700 km/h
        └── is_feasible(event_a, event_b) -> {feasible, km, available_h, required_h}
                  │
                  ▼
Critical Finding: "Dr. Rajesh Mehta billed procedures in Delhi at 14:10
and Mumbai at 15:40 — 1,150 km in 90 min; minimum realistic travel ≈ 4.1 h."
                  │
                  ▼
Spacetime GIS Map (`frontend/src/components/SpacetimeMap.tsx`)
  ├── Numbered chronological pins along the route
  ├── Green polylines for feasible legs
  └── Pulsing Red Polyline + Alert Badge for Impossible Legs
```

### 1. Deterministic Geo & Travel Physics Engine (`backend/tools/geo.py`)
- **Haversine Distance:** Great-circle trigonometry computing accurate distances between any two coordinates across India and globally.
- **Realistic Transit Thresholds:**
  - Short-haul / Road ($\le 300$ km): $t_{\min} = \frac{\text{km}}{80.0\text{ km/h}}$.
  - Long-haul / Air ($> 300$ km): $t_{\min} = 2.5\text{h (airport security, check-in, boarding, taxiing)} + \frac{\text{km}}{700.0\text{ km/h flight speed}}$.
- **Edge-Case Safety:**
  - Same medical campus / city ($< 5$ km): Marked feasible (does not flag inter-department transit).
  - Overnight time gaps: Evaluates elapsed hours accurately (e.g. 14h available vs 4.1h required $\implies$ feasible).
  - Missing coordinates: Marked `skipped: True, feasible: True` to prevent false positive accusations.

### 2. Spacetime ADK Agent (`backend/agents/spacetime.py`)
- Assembles admission, attending doctor procedures, discharge, and BigQuery warehouse billing records within $\pm 24$ hours.
- Gemini Flash extracts timestamps and places from unformatted documents, while the deterministic `is_feasible` tool rigorously judges physical transit feasibility.
- Emits `DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL` (`Severity.CRITICAL`) with exact distance and time metrics.

### 3. Interactive GIS Map Visualization (`frontend/src/components/SpacetimeMap.tsx`)
- **Dual Engine GIS Projection:** Supports both Google Maps Platform (`@vis.gl/react-google-maps`) and native high-resolution SVG geographic projection of India.
- **Visual Trajectory:** Numbered sequential pins in chronological order connected by directional transit polylines.
- **Pulsing Impossible Leg Badge:** Impossible legs are highlighted with an animated, pulsing red polyline and an interactive callout banner (`"1,150 km in 90 min (Impossible)"`).
- **Synchronized Vertical Timeline:** Interactive list of all hospitalization and billing events beside the map; clicking an event focuses the map view and links to the source document citation.

### 4. BigQuery Pitch Query (`infra/impossible_travel_query.sql`)
- Demonstrates enterprise-scale detection across the entire BigQuery claims warehouse:
  ```sql
  -- Self-join claims by doctor within 24 hours, computing ST_DISTANCE and required travel physics
  ST_DISTANCE(ST_GEOGPOINT(c1.provider_lng, c1.provider_lat),
              ST_GEOGPOINT(c2.provider_lng, c2.provider_lat)) / 1000.0 AS transit_km
  WHERE available_hours < min_required_travel_hours
  ```

---

## 💬 Feature 8 (F8): Adjuster Chat Copilot with the Case File

FinShield enables insurance claims adjusters to interrogate the case file in real time through an interactive, strictly grounded AI copilot:

```text
Adjuster Inquiry ("Why was this flagged?")
        │
        ▼
POST /claims/{id}/chat (Server-Sent Events)
  ├── Strict Context Grounding (Claim JSON + Dossier + Findings + Policy Rules)
  ├── Gemini Pro (`GEMINI_PRO_MODEL`) via Google GenAI SDK (Streamed)
  ├── Automatic Fallback Grounding Engine (Offline / Test Mode)
  └── Regex Citation Resolver ([F1] -> Finding ID -> Document Bounding Box)
        │
        ▼
Interactive Slide-Out Chat Drawer (`frontend/src/components/ChatDrawer.tsx`)
  ├── Real-time token streaming with typing animation
  ├── Suggested Question Pills ("Why flagged?", "Strongest evidence?", "Policy clause?", "Next steps?")
  └── Clickable [F#] Citations: Instantly pulses & highlights the citation on Document Viewer
```

### 1. Strict Case-File Grounding & Security Guardrails
- **Grounding Scope:** Grounded exclusively on: Claim metadata, itemized billing lines, Dossier verdict/scores, all Findings, and cited policy clauses. No web browsing, no outside knowledge of real-world individuals or hospitals.
- **System Prompt:**
  > *"You are FinShield's audit assistant talking to an insurance adjuster. Answer only from the case file provided. Cite finding ids like [F1]. If asked something the case file can't answer, say what's missing and what the adjuster could check. Be brief and neutral. Never call the claimant a criminal — describe evidence and risk."*
- **Off-Topic Refusal:** Off-topic trivia or non-case inquiries politely respond with a structured refusal explaining that the query is outside the case file boundaries.

### 2. Streaming SSE & Persistence
- **Streaming Endpoint (`POST /claims/{id}/chat`):** Emits token chunks via `text/event-stream`, concluding with a structured event containing `{done: true, answer, cited_finding_ids, cited_evidence}`.
- **Persistence (`GET /claims/{id}/chat`):** Persists all adjuster dialogues in Cloud Firestore under `claims/{id}/chat_messages` (with local SQLite fallback).

### 3. Clickable Document Citations
- Citations such as `[F1]` or `[F-ARITH-TOTAL]` render as clickable badges in the chat interface.
- Clicking any citation focuses and pulses the associated Document AI bounding box directly in the split document viewer.

---

## 🚀 Getting Started
Refer to [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md) for the implementation roadmap and architecture details.
