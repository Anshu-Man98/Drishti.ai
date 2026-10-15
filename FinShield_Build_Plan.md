# FinShield

**Track:** BFSI: Intelligent Risk, Fraud & Financial Experiences
**One-liner:** A multi-agent claims-fraud copilot that catches forged (including AI-generated) insurance claim documents, explains every flag with evidence on the page, and trains itself against an AI fraudster.
**Problem size:** India's insurance sector loses about ₹8,000–10,000 crore a year to health-claim fraud, waste and abuse. Industry estimates put total fraud at about $6B a year, roughly 8–10% of premiums. It happens on every claim cycle.

---

## 1. How to use this file

1. Build **one feature at a time**, in the priority order below.
2. For every prompt, paste the **Shared Context Block (Section 5)** first, then the feature prompt.
3. Do not start the next feature until the current one passes its **acceptance criteria**.
4. Commit after each feature, so you can roll back if the agent breaks something.
5. Save this file in the repo as `docs/BUILD_PLAN.md` so Antigravity can always read it.

---

## 2. Locked features, ranked by build priority

| # | Priority | Feature | Why this position | Est. hours (with Antigravity) |
|---|---|---|---|---|
| P0 | Foundation | Project skeleton + synthetic data + 6 demo claims | Everything depends on it | 3–4 |
| F1 | **1 — Must** | Four-agent core (Forensics, Arithmetic & Policy, Cross-Reference, Synthesizer) on ADK | The engine judges will scrutinize | 5–6 |
| F2 | **2 — Must** | Document AI extraction + bounding-box citations | Makes every flag auditable; big UX win | 2–3 |
| F3 | **3 — Must** | BigQuery ML fraud score + feature explanations | "ML scores, Gemini explains" hybrid story | 2 |
| F8 | **4 — Must** | Conversational audit ("why was this flagged?") | Cheap, shows Gemini reasoning live | 2 |
| F4 | **5 — Showpiece (primary)** | Spacetime check (impossible-travel detection on a map) | Deterministic, so it's reliable on stage; instant "wow" | 3 |
| F6 | **6 — Showpiece (stretch)** | Dueling AI: Red-team fraudster agent vs. FinShield | Most ambitious; cut it if it's flaky by hour 26 | 4–5 |
| — | Parked | Pub/Sub live claim feed | Pull in only if you're ahead of schedule | 1–2 |
| — | Always | Demo video, proposal PDF, rehearsal | Doesn't compress with AI | 4 |

**Total:** about 26–29 hours of your 30. Reinvest anything you save into F6 and demo polish.

**Cut rule:** at hour 22, if F1–F4 aren't all solid, drop F6. A clean core beats a broken showpiece.

---

## 3. Tech stack (all Google)

| Layer | Google product | Used by |
|---|---|---|
| Build environment | **Antigravity** (agentic IDE, Gemini-powered) | Everything |
| Front end | **React + TypeScript (Vite)** on **Firebase Hosting** | UI |
| Maps | **Google Maps Platform** (Maps JavaScript API via `@vis.gl/react-google-maps`) | F4 |
| Backend API | **FastAPI on Cloud Run** | All |
| Agent orchestration | **Agent Development Kit (ADK, Python)**: `SequentialAgent`, `ParallelAgent`, `LlmAgent` | F1, F6 |
| Reasoning model | **Gemini 3.1 Pro on Vertex AI** (env var `GEMINI_PRO_MODEL`) | Synthesizer, Audit chat, Red-team agent |
| Fast model | **Gemini Flash on Vertex AI** (env var `GEMINI_FLASH_MODEL`) | Forensics visual pass, extraction helpers |
| Document extraction | **Document AI**: Invoice Parser or Expense Parser | F2 |
| Policy retrieval | **Vertex AI Search** (datastore of policy PDFs) | Arithmetic & Policy agent |
| Analytics + ML | **BigQuery** + **BigQuery ML** (`BOOSTED_TREE_CLASSIFIER`, `ML.EXPLAIN_PREDICT`) | F1 Cross-Ref, F3, F4 |
| App state + live UI | **Firestore** (real-time listeners) | All |
| File storage | **Cloud Storage** | Uploaded and generated documents |
| Secrets | **Secret Manager** | API keys, config |
| Observability | **Cloud Logging / Cloud Monitoring** | Agent latency, token usage |
| AI-content provenance | **SynthID Detector** (behind a feature flag) | Forensics agent |
| Parked | **Pub/Sub** | Live claim feed |

> **Verify before you start:**
> - **Model IDs.** Check the exact Gemini model IDs in Vertex AI Model Garden on day one and set them as env vars. Never hard-code them.
> - **SynthID access.** The SynthID Detector has been waitlisted, so confirm you can call it. Build it as a pluggable check that returns `"unavailable"` gracefully. The other forensic layers must work without it.

---

## 4. Architecture

```
React (Firebase Hosting)
   │  upload claim docs / view dossier / chat / map / duel arena
   ▼
FastAPI on Cloud Run ──► Cloud Storage (docs)
   │                 ──► Firestore (claims, dossiers, chat, duel rounds)
   ▼
ADK Root: SequentialAgent
   ├── Step 0: Extraction (Document AI → normalized claim JSON + bboxes)
   ├── Step 1: ParallelAgent
   │      ├── Forensics Agent      (SynthID*, PDF metadata, EXIF, ELA, font consistency, Gemini visual review)
   │      ├── Arithmetic & Policy  (deterministic math tools + Vertex AI Search policy clauses)
   │      ├── Cross-Reference      (BigQuery duplicate / cross-insurer / pattern queries)
   │      └── Spacetime Agent      (F4 — added later)
   ├── Step 2: ML Score            (BigQuery ML predict + explain — F3)
   └── Step 3: Synthesizer Agent   (Gemini Pro → final Dossier JSON)

Audit Chat (F8):  Gemini Pro grounded ONLY on Dossier + findings + extracted text
Duel Arena (F6):  Red Agent → PDF renderer → full pipeline → Judge → feedback loop
```

---

## 5. Shared Context Block (paste before EVERY feature prompt)

```text
PROJECT: FinShield — multi-agent insurance-claim fraud copilot for the Google BFSI hackathon.
Read docs/BUILD_PLAN.md in the repo for the full plan. Build ONLY the feature I ask for in this message.

HARD RULES
- Google stack only: Gemini on Vertex AI (google-genai SDK with vertexai=True), ADK (google-adk, Python),
  Document AI, Vertex AI Search, BigQuery + BigQuery ML, Firestore, Cloud Storage, Cloud Run,
  Firebase Hosting, Google Maps Platform, Secret Manager.
- Model IDs come from env vars GEMINI_PRO_MODEL and GEMINI_FLASH_MODEL. Never hard-code model names.
- LLMs never do arithmetic or distance math. All math runs in deterministic Python tools the agents call.
- Every agent returns structured JSON matching the schemas below (use response_schema / Pydantic).
- All demo data is synthetic. Fictional hospitals, doctors, people. No real PII.
- Don't modify files outside the scope of the current feature unless I say so. If you must, list the changes.
- Write tests for every deterministic tool (pytest). Keep a README section per feature.

REPO LAYOUT
/frontend           React + TS + Vite, Tailwind, react-router; Firebase Hosting
/backend
  /app              FastAPI (main.py, routers/, schemas.py, services/)
  /agents           ADK agents (root.py, forensics.py, policy.py, crossref.py, spacetime.py, synthesizer.py, redteam.py)
  /tools            deterministic tools (arithmetic.py, forensics_tools.py, geo.py, bq.py, docai.py, search.py)
  /tests
/data               synthetic data generator + seed scripts + demo claim PDFs
/infra              Dockerfile, cloudbuild.yaml, BigQuery DDL, setup scripts
/docs               BUILD_PLAN.md

CORE SCHEMAS (backend/app/schemas.py — single source of truth)
Claim {
  claim_id, policy_id, insurer_id,
  claimant {claimant_id, name, phone, bank_account_hash},
  provider {hospital_id, name, city, lat, lng}, doctor_id,
  admission_ts, discharge_ts, diagnosis_code,
  line_items [{description, qty, unit_price, amount}], subtotal, tax, total_claimed,
  documents [{doc_id, gcs_uri, doc_type: bill|prescription|discharge_summary|lab_report|photo, sha256}]
}
Evidence { doc_id, page, bbox: [x0,y0,x1,y1] normalized 0..1 or null, quote }
Finding {
  finding_id, agent: forensics|policy|crossref|spacetime|ml,
  check_id, severity: info|low|medium|high|critical,
  title, explanation, evidence: Evidence[], confidence 0..1
}
Dossier {
  claim_id, risk_score 0..100, ml_score 0..1 | null,
  verdict: approve|review|reject,
  summary, findings: Finding[], top_ml_features [{feature, attribution}] | null,
  timeline [{ts, lat, lng, place, doc_id, actor}] | null,
  created_at
}

API (FastAPI)
POST /claims                 multipart upload → creates Claim, stores docs in GCS, returns claim_id
POST /claims/{id}/analyze    runs the agent pipeline, writes Dossier to Firestore
GET  /claims, GET /claims/{id}, GET /claims/{id}/dossier
(Feature-specific endpoints are defined in each feature prompt.)
```

---

## 6. Feature prompts (paste one at a time)

### P0 — Foundation + synthetic data

```text
TASK: Build the project foundation. No agents yet.

1. Scaffold the repo exactly as in REPO LAYOUT.
2. Backend: FastAPI app with /health, the core Pydantic schemas, and POST/GET /claims
   (upload to Cloud Storage, metadata to Firestore). Dockerfile for Cloud Run. Config via env vars + Secret Manager.
3. Frontend: React + TS + Vite + Tailwind. Pages: Claims List, Claim Detail (placeholder), Upload.
   Firebase Hosting config. API base URL from env.
4. Synthetic data generator (/data/generate.py):
   - ~3,000 claims across 5 insurers, 40 fictional hospitals in 12 Indian cities (real city coordinates,
     fictional hospital names), 150 fictional doctors, 2,000 claimants.
   - ~12% fraud, labeled with fraud_type: inflated_line_items, arithmetic_mismatch, policy_cap_breach,
     duplicate_bill, cross_insurer_duplicate, impossible_travel, shared_bank_account_ring, forged_document.
   - Engineered numeric features for ML: claim_amount, amount_vs_diagnosis_median_ratio, length_of_stay,
     claimant_prior_claims_90d, provider_claims_per_day, doctor_distinct_cities_24h, shared_bank_account_count,
     days_policy_start_to_claim, line_item_count, room_rent_vs_cap_ratio.
   - Load into BigQuery dataset `finshield` tables: claims, line_items, doctor_events
     (doctor_id, ts, hospital_id, lat, lng, claim_id). DDL in /infra/bigquery.sql.
5. Six GOLDEN demo claims as real PDFs (reportlab), fictional data, stored in /data/demo:
   G1 clean claim
   G2 bill with padded line items + total that doesn't match the line-item sum
   G3 room rent exceeding the policy cap
   G4 same bill already submitted to another insurer last month
   G5 doctor billed in Delhi and Mumbai 90 minutes apart (impossible travel)
   G6 forged bill: edited total row (different font/size) + PDF producer = an image editor + mod date ≠ create date
6. Three fictional policy PDFs (room-rent caps, exclusions, waiting periods, numbered clauses) in /data/policies
   for Vertex AI Search.
7. Seed script that loads the golden claims via the API.

ACCEPTANCE
- Backend runs on Cloud Run, frontend on Firebase Hosting, they talk to each other.
- Uploading a PDF creates a claim visible in the Claims List.
- BigQuery has all tables with the fraud labels; `SELECT fraud_type, COUNT(*)` looks right.
- The 6 golden PDFs open and look like plausible hospital bills.
```

### F1 — Four-agent core (Priority 1)

```text
TASK: Build the four-agent fraud pipeline with ADK. Extraction for now = Gemini Flash reading the PDF
into the Claim schema (F2 will replace this with Document AI — keep extraction behind an interface
`extract_claim(doc) -> Claim` so it can be swapped).

ROOT (backend/agents/root.py)
SequentialAgent[
  ParallelAgent[ForensicsAgent, PolicyAgent, CrossRefAgent],
  SynthesizerAgent
]
Each specialist writes its Finding[] to session state via output_key; Synthesizer reads all of them.

1) FORENSICS AGENT (LlmAgent, GEMINI_FLASH_MODEL) — "Is this document authentic?"
   Tools (backend/tools/forensics_tools.py, deterministic, each returns a dict + Finding-ready evidence):
   - pdf_metadata_check: producer/creator (flag image editors, online PDF editors), create vs mod date,
     incremental updates count.
   - font_consistency_check (pdfplumber): font name/size per line; flag lines (esp. totals) whose
     font differs from the rest of the table. Return bbox of the anomalous line.
   - image_exif_check + error_level_analysis (Pillow) for photo/scanned docs; return suspicious region bbox.
   - synthid_check: behind feature flag SYNTHID_ENABLED; if unavailable return {"status":"unavailable"}.
   - Then a Gemini visual review of the page image to describe visible tampering, constrained to only
     reference regions flagged by tools OR clearly visible issues. It must not invent pixel-level claims.
   SYSTEM PROMPT:
   "You are a document forensics examiner for insurance claims. Call every available forensic tool on
    every document. Report only what the tool outputs or the page visibly shows. For each anomaly, emit a
    Finding with check_id, severity, a one-sentence plain-English explanation, and evidence with doc_id,
    page and bbox. If tools find nothing, return an empty list. Never guess. Output JSON only."

2) ARITHMETIC & POLICY AGENT (LlmAgent, GEMINI_FLASH_MODEL) — "Do the numbers add up and follow the rules?"
   Tools:
   - validate_arithmetic(line_items, subtotal, tax, total): sum checks, qty*unit_price checks, ±₹1 tolerance.
   - check_dates(admission_ts, discharge_ts, document dates): ordering, bills dated outside the stay.
   - check_policy_caps(policy_id, claim): room-rent cap, sub-limits, waiting period — rules in a JSON table
     derived from the policy PDFs.
   - search_policy(query): Vertex AI Search over the policy datastore; returns clause text + clause id.
     (If ADK won't mix the built-in VertexAiSearchTool with function tools in one agent, wrap Vertex AI
     Search in a plain function tool using the Discovery Engine client.)
   SYSTEM PROMPT:
   "You are a claims auditor. You NEVER compute numbers yourself — always call the tools. For every
    violation, cite the policy clause id and text returned by search_policy. Emit Findings in JSON only."

3) CROSS-REFERENCE AGENT (LlmAgent, GEMINI_FLASH_MODEL) — "Have we seen this before?"
   Tools (backend/tools/bq.py, parameterized BigQuery queries only):
   - find_exact_duplicates(sha256, bill_number, hospital_id)
   - find_cross_insurer_duplicates(claimant_id, admission_ts ±3 days, amount ±5%)
   - claimant_history(claimant_id, 365 days)
   - shared_account_check(bank_account_hash) → other claimants using the same account
   SYSTEM PROMPT:
   "You are a fraud investigator with access to the claims warehouse. Run every lookup. Report matches
    with the matching claim_ids as evidence. Don't speculate beyond query results. JSON only."

4) SYNTHESIZER AGENT (LlmAgent, GEMINI_PRO_MODEL) — "What's the verdict?"
   Input: all Findings. Output: Dossier JSON.
   - risk_score: compute with deterministic tool score_findings(findings) (severity weights:
     info 0, low 5, medium 15, high 30, critical 50, capped at 100) — the LLM does not invent the number.
   - verdict: approve <30, review 30–69, reject ≥70 (also deterministic).
   - summary: 3–5 sentences, plain English, for a busy adjuster; reference finding_ids.
   SYSTEM PROMPT:
   "You write the final risk dossier for an insurance adjuster. Use only the findings provided.
    Do not add new accusations. Call score_findings for the score. Be specific, neutral, and concise."

API: POST /claims/{id}/analyze runs the pipeline and writes the Dossier to Firestore; stream per-agent
status (pending/running/done) into Firestore so the UI can show agents lighting up.

FRONTEND: Claim Detail page
- "Analyze" button. Four agent cards that animate pending → running → done (Firestore listener).
- Dossier panel: risk score gauge, verdict badge, summary, findings grouped by agent with severity chips.

ACCEPTANCE (run on the 6 golden claims)
- G1 → approve, no high/critical findings.
- G2 → arithmetic finding, G3 → policy-cap finding citing a clause, G4 → cross-insurer duplicate,
  G6 → forensics findings (producer + font mismatch on totals row + date mismatch).
- Same claim analyzed 3 times gives the same verdict and score.
- Unit tests pass for every tool.
```

### F2 — Document AI extraction + bounding-box citations (Priority 2)

```text
TASK: Replace the Gemini extraction stub with Document AI and add visual citations.

BACKEND
- backend/tools/docai.py: process each PDF/image with the Document AI Invoice Parser (fallback: Expense
  Parser). Map entities to Claim fields and line_items. Keep each entity's normalized bounding box and page.
- Use Gemini Flash only to fill fields Document AI misses (diagnosis, doctor) — mark those fields
  source="gemini" vs source="docai".
- Every Finding that refers to a field (total, a line item, a date) must carry that field's bbox
  in evidence. Add a helper locate_field(doc_id, field_path) -> Evidence.
- Store page images (PNG, 150 dpi) in Cloud Storage for the viewer.

FRONTEND
- Document viewer next to the dossier: page image with SVG overlay rectangles for every evidence bbox,
  colored by severity.
- Clicking a finding scrolls to and pulses its box; hovering a box shows the finding title.
- Toggle: "Show all extracted fields" (light grey boxes) vs "Show only flags".

ACCEPTANCE
- On G2 the mismatched total row and the padded line items are boxed correctly.
- On G6 the edited total row is boxed.
- Extraction of all 6 golden claims matches the ground truth in /data/demo/ground_truth.json (write a test).
```

### F3 — BigQuery ML fraud score (Priority 3)

```text
TASK: Add a trained ML fraud score next to the agent score.

1. /infra/bqml.sql:
   CREATE OR REPLACE MODEL finshield.fraud_model
   OPTIONS(model_type='BOOSTED_TREE_CLASSIFIER', input_label_cols=['is_fraud'],
           enable_global_explain=TRUE, data_split_method='AUTO_SPLIT')
   AS SELECT <engineered features from P0>, is_fraud FROM finshield.claims;
   Save ML.EVALUATE output (precision, recall, ROC AUC) to /docs/model_eval.md for the pitch deck.
2. backend/tools/bq.py: ml_score(claim_features) runs ML.PREDICT + ML.EXPLAIN_PREDICT (top_k_features=5)
   for a single claim; returns probability + top feature attributions.
3. Add an ML step after the ParallelAgent: write ml_score and top_ml_features into the Dossier and
   add an agent="ml" Finding when probability > 0.6.
4. Update score_findings: final risk_score = round(0.6 * agent_score + 40 * ml_probability).
   Document the formula in the README.
5. Synthesizer summary must explain the ML score in plain words using the top features
   (e.g., "claim amount is 3.1× the median for this diagnosis").

FRONTEND
- Show "Agent score" and "ML score" side by side, plus a small horizontal bar chart of top feature
  attributions (recharts).

ACCEPTANCE
- Model trains; ROC AUC recorded. ML score appears on every dossier.
- Fraudulent golden claims score higher than G1.
```

### F8 — Conversational audit (Priority 4)

```text
TASK: Let the adjuster chat with the dossier.

BACKEND
- POST /claims/{id}/chat {message} → streamed answer (SSE).
- Gemini Pro, grounded ONLY on: the Dossier, all Findings, extracted Claim JSON, and policy clauses
  already cited. No web, no outside knowledge about real people or hospitals.
- Response JSON: {answer, cited_finding_ids[], cited_evidence[]}. Every factual sentence must map to at
  least one finding or evidence item; if the answer isn't in the context, say so.
- Save chat history in Firestore under the claim.
SYSTEM PROMPT:
  "You are FinShield's audit assistant talking to an insurance adjuster. Answer only from the case file
   provided. Cite finding ids like [F3]. If asked something the case file can't answer, say what's
   missing and what the adjuster could check. Be brief and neutral. Never call the claimant a
   criminal — describe evidence and risk."

FRONTEND
- Chat drawer on Claim Detail with suggested questions: "Why was this flagged?",
  "What's the strongest evidence?", "Which policy clause applies?", "What should I verify next?"
- Citations [F3] are clickable and highlight the bbox in the document viewer (reuse F2).

ACCEPTANCE
- On G2, "Why was this flagged?" cites the arithmetic finding and highlights the total row.
- An off-topic question gets a polite "not in the case file" answer.
```

### F4 — Spacetime check (Priority 5, primary showpiece)

```text
TASK: Detect physically impossible timelines and show them on a map.

BACKEND
- backend/tools/geo.py (deterministic + tested):
  haversine_km(a, b); min_travel_hours(km) = km/80 for ≤300 km road, else 2.5h airport overhead + km/700;
  is_feasible(event_a, event_b) → {feasible, km, available_h, required_h}.
- build_timeline(claim): events from documents (admission, procedures, prescriptions, lab reports)
  plus doctor_events from BigQuery for the same doctor ±24h. Gemini Flash only extracts timestamps and
  places from documents into events; it never judges feasibility.
- SpacetimeAgent (LlmAgent, Flash) added to the ParallelAgent. Tools: build_timeline, is_feasible over
  consecutive events for the same actor (doctor or patient). Emits a critical Finding per impossible leg,
  e.g. "Dr. X billed procedures in Delhi at 14:10 and Mumbai at 15:40 — 1,150 km in 90 min; minimum
  realistic travel ≈ 4.1 h."
- Store the timeline in Dossier.timeline.
- Bonus query for the pitch: SQL in BigQuery listing all doctors with impossible legs in the dataset.

FRONTEND
- "Spacetime" tab: Google Map (@vis.gl/react-google-maps) with numbered markers in time order,
  polylines between consecutive events; impossible legs drawn red and pulsing with a label
  "1,150 km in 90 min".
- A vertical timeline beside the map; clicking an event pans the map and opens its source document.

ACCEPTANCE
- G5 shows one red impossible leg with the correct numbers; G1 shows all-green legs.
- geo.py tests cover edge cases (same city, overnight gaps, missing coordinates → skipped, not flagged).
```

### F6 — Dueling AI: Red-team fraudster vs. FinShield (Priority 6, stretch)

```text
TASK: Build a live "Duel Arena" where an AI fraudster tries to beat FinShield and both sides adapt.

SAFETY / SCOPE
- 100% synthetic: fictional hospitals and people from the P0 generator only.
- Every generated PDF has metadata keyword "FINSHIELD-SYNTHETIC-DEMO". Forensics must NOT use this
  marker as a signal (strip it before analysis; add a test proving that).
- No real insurer, hospital or person names. Never export generated docs outside the app.

BACKEND
1. RedTeamAgent (LlmAgent, GEMINI_PRO_MODEL). Input: round number, list of tactics tried so far and
   which FinShield checks caught them. Output: a fake Claim JSON + chosen tactic + rationale.
   Tactic menu (it may combine or vary): padding line items subtly, splitting a bill across two claims,
   cross-insurer resubmission with changed dates, policy-cap evasion via relabeling room charges,
   tampered total row, impossible-travel doctor schedule.
   SYSTEM PROMPT: "You are a red-team simulator for a fraud-detection system, used only on synthetic data.
   Each round, design one synthetic fraudulent claim that you think will evade the detection checks
   that caught you before. Explain your tactic in one sentence. Output JSON only."
2. Renderer: Claim JSON → realistic bill PDF (reportlab). For "tampered" tactics, render the edited row
   with a different font/size and set producer metadata accordingly.
3. Run the full FinShield pipeline on it.
4. JudgeAgent (deterministic): caught = verdict in {review, reject}. Record the round
   {tactic, caught, risk_score, catching_finding_ids}.
5. Feedback loop — both sides learn:
   - Red gets which checks caught it and must try a different approach next round.
   - When Red WINS (evades), save the claim as a new known pattern in BigQuery table
     finshield.learned_patterns; CrossRefAgent gets a new tool match_learned_patterns() and catches
     that tactic in later rounds. This is the "it trains against tomorrow's fraud" moment.
6. POST /duel/start {rounds: 5} runs rounds sequentially, writing each to Firestore live.

FRONTEND: "Duel Arena" page
- Left: Red agent card (tactic + rationale + rendered bill thumbnail).
  Right: FinShield's four agents lighting up, verdict, score.
- Scoreboard (Caught vs Evaded), round timeline, and a "New pattern learned" toast when Red wins
  and the next round's similar attempt gets caught.

ACCEPTANCE
- A 5-round duel finishes in under 3 minutes.
- At least one round shows evade → learn → catch on a similar tactic (seed a deliberate early win if needed
  so the demo reliably shows the learning loop).
- Duel results persist and can be replayed for the video if the live run misbehaves.
```

### Parked — Pub/Sub live claim feed (only if ahead)

```text
TASK: POST /claims publishes {claim_id} to Pub/Sub topic claims-submitted; a Cloud Run worker
subscribed via push runs the pipeline. Add a "Live Feed" page listing claims as they arrive and get
scored (Firestore listener). Add /data/stream_demo.py to submit 20 synthetic claims over 60 seconds.
```

---

