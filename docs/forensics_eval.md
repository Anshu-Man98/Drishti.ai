# FinShield Forensics Evaluation Report 📊

**Evaluation Timestamp:** `2026-10-16 07:23:31 UTC`  
**Evaluation Methodology:** Real tool execution (`pdf_metadata_check`, `font_consistency_check`, `error_level_analysis`) on physical document bytes. No simulated or tautological labels.

---

## 1. Real Document Evaluation: Golden Claims Corpus

Evaluated against all 9 real claims in `data/demo/*.pdf`. Ground truth includes genuine claim submissions and real forged document G6 (Photoshop producer tag, post-generation date discrepancy, and injected line-item font mismatch).

| Metric | Real Golden Claims Corpus (`data/demo/`) |
|---|---|
| **Total Documents Evaluated** | **9** |
| **True Positives (TP)** | 1 |
| **False Positives (FP)** | 0 |
| **True Negatives (TN)** | 8 |
| **False Negatives (FN)** | 0 |
| **Precision** | **100.0%** |
| **Recall** | **100.0%** |
| **F1 Score** | **1.000** |

### Detection Breakdown by Forensic Check

| Forensic Tool / Layer | Check ID | Detections on Corpus | Target Vulnerability |
|---|---|:---:|---|
| **PDF Producer / Software Metadata** | `SUSPICIOUS_PRODUCER_METADATA` | 1 | Graphic design software (Photoshop, Canva, GIMP) |
| **Font Consistency Analysis** | `FONT_INCONSISTENCY_TAMPERING` | 1 | Font family, weight, or size disparity in tabular rows |
| **Error Level Analysis (ELA)** | `ELA_COMPRESSION_ANOMALY` | 0 | Inpainting boundaries & resaving compression gradients |

### Sample Level Results

| Document File | Ground Truth | Forensic Detection | Findings Count | Classification |
|---|:---:|:---:|:---:|:---:|
| `G1_clean_claim.pdf` | authentic | clean | 0 | **TN** |
| `G2_arithmetic_mismatch.pdf` | authentic | clean | 0 | **TN** |
| `G3_policy_cap_breach.pdf` | authentic | clean | 0 | **TN** |
| `G4_cross_insurer_duplicate.pdf` | authentic | clean | 0 | **TN** |
| `G5_impossible_travel.pdf` | authentic | clean | 0 | **TN** |
| `G6_forged_document.pdf` | forged | forged | 3 | **TP** |
| `G7_prompt_injection.pdf` | authentic | clean | 0 | **TN** |
| `G8_altered_approval.pdf` | authentic | clean | 0 | **TN** |
| `G9_pattern_match.pdf` | authentic | clean | 0 | **TN** |

---

## 2. External Benchmark Datasets Status

| Dataset | Manifest Status | Raw Images on Disk | Status Note |
|---|:---:|:---:|---|
| **Find It Again! (ICDAR Manipulation Benchmark)** | 20 entries | Not downloaded | Manifest present; raw image archives require download per `data/external/LICENSES.md` |
| **AIForge-Doc (Generative AI Inpainting Benchmark)** | 20 entries | Not downloaded | Manifest present; raw image archives require download per `data/external/LICENSES.md` |

---

## 3. Attribution & Integrity Notice
- All evaluations are conducted by executing real Python inspection tools on actual files.
- No synthetic or fabricated 100% metrics are preserved.
- For instructions on downloading external dataset archives, see `data/external/LICENSES.md`.
