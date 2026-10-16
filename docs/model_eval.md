# FinShield — Machine Learning Evaluation Report (BigQuery ML)

**Track:** BFSI: Intelligent Risk, Fraud & Financial Experiences  
**Architecture:** Hybrid "ML Scores, Gemini Explains" Engine  
**Model Type:** `BOOSTED_TREE_CLASSIFIER` with Global Explanations (`enable_global_explain=TRUE`)  
**Data Split Method:** `CUSTOM` (80/20 train/eval holdout grouped strictly by `hospital_id` via `FARM_FINGERPRINT` to eliminate provider data leakage)

---

## 1. Primary Claim Fraud Model (`finshield.fraud_model`)
Trained on 3,000 synthetic Indian health insurance claims across 5 major insurers, 40 healthcare facilities, and 12 cities with ~12% labeled fraud across 8 distinct patterns.

### Model Performance Evolution (`ML.EVALUATE`)
| Metric | Baseline (Pre-Task B) | Retrained (Benchmark-Aware) | Recalibrated (Final Parity) | Status |
|---|---|---|---|---|
| **ROC AUC** | 0.8845 | 0.8670 | **0.8676** | ✅ Strong Discrimination on Holdout Providers |
| **Precision** | 0.8485 | 0.8611 | **84.21%** | ✅ High True Positive Precision |
| **Recall** | 0.4118 | 0.4844 | **50.00%** | ✅ +8.82% Higher Fraud Capture vs Pre-Task B |
| **F1 Score** | 0.5545 | 0.6200 | **0.6275** | ✅ Peak F1 Performance Gain (+7.30%) |
| **Accuracy** | 0.9220 | 0.9307 | **93.07%** | ✅ 93.1% Overall Holdout Accuracy |
| **Log Loss** | 0.2074 | 0.1970 | **0.2033** | ✅ Calibrated Cross-Entropy |

### Calibration Check: Predicted vs Observed Fraud Rate by Bucket (`ML.PREDICT` on holdout set)
| Predicted Probability Bucket | Total Claims in Bucket | Actual Fraud Claims | Mean Predicted Prob | Observed Fraud Rate |
|---|---|---|---|---|
| **0.0 - 0.2** | 438 | 13 | 0.0603 (6.0%) | 0.0297 (3.0%) |
| **0.2 - 0.4** | 55 | 16 | 0.2950 (29.5%) | 0.2909 (29.1%) |
| **0.4 - 0.6** | 23 | 5 | 0.4643 (46.4%) | 0.2174 (21.7%) |
| **0.6 - 0.8** | 4 | 2 | 0.6668 (66.7%) | 0.5000 (50.0%) |
| **0.8 - 1.0** | 28 | 28 | 0.9395 (94.0%) | 1.0000 (100.0%) |

---

## 2. Recalibrated Detection & Severity Thresholds

To eliminate false positive flags on legitimate hospital invoices (such as metro Tier-1 hospitals, regional price variations, and standard rehabilitative care), thresholds were recalibrated:

### A. Total Diagnosis Benchmark (`TOTAL_ABOVE_DIAGNOSIS_BENCHMARK`)
- **Widened Upper Band**: Rather than treating raw $p_{95}$ as a rigid ceiling, the check computes:
  $$\text{upper\_band} = p_{95} \times (1.0 + \text{tolerance\_margin})$$
  where $\text{tolerance\_margin} = 0.25$ for exact diagnoses ($N \ge 30$), and $0.35$ for global or thin fallbacks ($N < 30$).
- **Severity Scaling**:
  - Total claimed $\le \text{upper\_band}$: **No finding** (claims within expected metro spread never flag).
  - $1.00 < \text{ratio} \le 1.15$ above upper band: `Severity.LOW`.
  - $1.15 < \text{ratio} \le 1.35$ above upper band: `Severity.MEDIUM`.
  - $\text{ratio} > 1.35$ above upper band: `Severity.HIGH`.
  - Thin/global fallback cap: weak benchmarks ($N < 30$ or fallback `global`) may never produce a `HIGH` finding (capped at `LOW`).

### B. Line-Item Price Benchmark (`LINE_ITEM_PRICE_ABOVE_BENCHMARK`)
- **Category Upper Band**: Unit price compared against category $p_{95} \times (1.0 + \text{tolerance\_margin})$ ($+20\%$ for exact category match, $+30\%$ for global).
- **Materiality Gate**: The check requires both ratio elevation and material rupee impact:
  $$\text{excess\_rupees} = (\text{unit\_price} - p_{95}) \times \text{qty} \ge \text{₹}2,000 \quad \text{AND} \quad \frac{\text{excess\_rupees}}{\text{total\_claimed}} \ge 0.03$$
  Marginal price variations on inexpensive supplies do not flag and cannot alter the claim verdict.

### C. Ancillary Padding (`UNBUNDLED_OR_PADDED_ANCILLARY`)
- **Clinical Scope**: Limited strictly to disposable medical consumables and surgical supply kits. Consultations, doctor visits, physiotherapy, rehabilitative sessions, diagnostic investigations (MRI/CT/USG), room rent, and standard medications are excluded.
- **Rule Thresholds**:
  1. At least 3 distinct consumable line items ($\ge 3$).
  2. Consumable share of bill $\ge 28\%$.
  3. Total consumable billing $> \max(p_{95} \times 1.35, \text{₹}15,000)$.

### D. Findings Aggregation & Diminishing Returns
- **Diminishing Weights**:
  - `Severity.CRITICAL`: 50 pts each.
  - `Severity.HIGH`: 30 pts for 1st, 20 pts for 2nd, 10 pts for 3rd+.
  - `Severity.MEDIUM`: 15 pts for 1st, 10 pts for 2nd, 5 pts for 3rd+.
  - `Severity.LOW`: 5 pts for 1st, 3 pts for 2nd, 1 pt for 3rd+, capped at 10 pts total.
- **Invariant**: Claims with only `Severity.LOW` findings (and no medium/high/critical flags or deception fraud) cannot exceed a risk score of 28 and remain strictly in `Verdict.APPROVE`.

---

## 3. Validated on Real Claims Data (`finshield.provider_fraud_model`)
To validate the modelling architecture beyond synthetic generation, the exact same `BOOSTED_TREE_CLASSIFIER` configuration was trained and evaluated on **real Kaggle Healthcare Provider Fraud Detection data (US Medicare)**.

### Real-World Dataset Performance (`ML.EVALUATE`)
| Metric | Value | Verification |
|---|---|---|
| **ROC AUC** | **0.9472** | Demonstrates >94.7% discrimination on real claims records |
| **Precision** | **0.9559** | 95.6% precision on real healthcare provider fraud |
| **Recall** | **0.6250** | Catches 62.5% of actual fraudulent providers |
| **F1 Score** | **0.7558** | 0.7558 on real-world medical data |
| **Accuracy** | **0.9600** | 96.0% overall provider classification accuracy |

---

## 4. Hybrid Scoring Architecture: "ML Scores, Gemini Explains"

FinShield combines statistical machine learning with deterministic multi-agent auditing:
$$\text{Final Risk Score} = \text{round}\left(0.6 \times \text{Agent Score} + 40 \times \text{ML Probability}\right)$$

- **BigQuery ML** continuously analyzes tabular features and anomaly distributions.
- **8 deterministic specialist agents** audit document forensics, clause caps, geographic feasibility, and warehouse duplicates.
- **Vertex AI Gemini** synthesizes the top feature attributions into natural language explanations for the adjuster.
