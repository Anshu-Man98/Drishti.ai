# External Evaluation Datasets — Licenses & Attribution

These public evaluation datasets are used strictly for offline validation and benchmark testing of FinShield's algorithms and forensics layers. They are **never shown in the live demo** and never exposed to end users.

---

### 1. Kaggle Healthcare Provider Fraud Detection Analysis
- **Source:** Kaggle / CMS Medicare Part A and B synthetic public data
- **Original Publisher:** Centers for Medicare & Medicaid Services (CMS) DE-SynPUF
- **License:** Open Database License (ODbL) / Public Domain Government Data
- **Use in FinShield:** Offline evaluation only (`finshield.ext_provider_fraud`). Used in F3 to validate the boosted tree classification architecture on genuine provider claims aggregation structures. Amounts are kept in USD as published.

---

### 2. "Find It Again!" Document Forgery Dataset
- **Source:** ICDAR / Scientific Document Analysis Community
- **License:** Research & Non-Commercial Academic Use Only
- **Content:** Real-world scanned receipts with authentic copies alongside manually manipulated versions (splicing, copy-move, font alterations) with ground-truth bounding box coordinates.
- **Use in FinShield:** Used in offline evaluation benchmark (`backend/eval/forensics_eval.py`) to measure traditional forensics detection rates (font anomaly, metadata manipulation, ELA).

---

### 3. AIForge-Doc Benchmark
- **Source:** AI Generated Document Forensics Benchmark
- **License:** Research & Evaluation Use Only
- **Content:** Contemporary generative AI / inpainting tampered receipts, medical bills, and invoices with ground-truth pixel tamper masks.
- **Use in FinShield:** Used in offline evaluation benchmark (`backend/eval/forensics_eval.py`) to quantify the detection gap between traditional heuristic checks and Gemini multimodal visual inspection on AI-altered documents.
