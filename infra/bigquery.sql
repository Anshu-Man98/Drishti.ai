-- BigQuery DDL for FinShield Fraud Copilot
-- Dataset: finshield

CREATE SCHEMA IF NOT EXISTS `finshield`
OPTIONS (
  location = 'asia-south1',
  description = 'FinShield insurance claims, doctor trajectories, and fraud analytics'
);

-- Table 1: claims (with engineered features for ML model training)
CREATE TABLE IF NOT EXISTS `finshield.claims` (
  claim_id STRING NOT NULL,
  policy_id STRING NOT NULL,
  insurer_id STRING NOT NULL,
  claimant_id STRING NOT NULL,
  claimant_name STRING,
  claimant_phone STRING,
  bank_account_hash STRING NOT NULL,
  hospital_id STRING NOT NULL,
  hospital_name STRING,
  city STRING NOT NULL,
  lat FLOAT64 NOT NULL,
  lng FLOAT64 NOT NULL,
  doctor_id STRING NOT NULL,
  admission_ts TIMESTAMP NOT NULL,
  discharge_ts TIMESTAMP NOT NULL,
  diagnosis_code STRING NOT NULL,
  subtotal FLOAT64 NOT NULL,
  tax FLOAT64 NOT NULL,
  total_claimed FLOAT64 NOT NULL,
  -- Engineered features for BigQuery ML
  claim_amount FLOAT64 NOT NULL,
  amount_vs_diagnosis_median_ratio FLOAT64 NOT NULL,
  length_of_stay INT64 NOT NULL,
  claimant_prior_claims_90d INT64 NOT NULL,
  provider_claims_per_day FLOAT64 NOT NULL,
  doctor_distinct_cities_24h INT64 NOT NULL,
  shared_bank_account_count INT64 NOT NULL,
  days_policy_start_to_claim INT64 NOT NULL,
  line_item_count INT64 NOT NULL,
  room_rent_vs_cap_ratio FLOAT64 NOT NULL,
  -- Target labels
  is_fraud INT64 NOT NULL, -- 0 = authentic, 1 = fraud
  fraud_type STRING, -- clean, inflated_line_items, arithmetic_mismatch, policy_cap_breach, duplicate_bill, cross_insurer_duplicate, impossible_travel, shared_bank_account_ring, forged_document
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(admission_ts)
CLUSTER BY insurer_id, hospital_id, doctor_id;

-- Table 2: line_items
CREATE TABLE IF NOT EXISTS `finshield.line_items` (
  claim_id STRING NOT NULL,
  item_id STRING NOT NULL,
  description STRING NOT NULL,
  qty FLOAT64 NOT NULL,
  unit_price FLOAT64 NOT NULL,
  amount FLOAT64 NOT NULL
)
CLUSTER BY claim_id;

-- Table 3: doctor_events (for Spacetime travel feasibility checks)
CREATE TABLE IF NOT EXISTS `finshield.doctor_events` (
  event_id STRING NOT NULL,
  doctor_id STRING NOT NULL,
  ts TIMESTAMP NOT NULL,
  hospital_id STRING NOT NULL,
  hospital_name STRING,
  city STRING NOT NULL,
  lat FLOAT64 NOT NULL,
  lng FLOAT64 NOT NULL,
  claim_id STRING
)
PARTITION BY DATE(ts)
CLUSTER BY doctor_id;

-- Table 4: ext_provider_fraud (Real Kaggle Medicare evaluation data)
-- Evaluation only; amounts in USD
CREATE TABLE IF NOT EXISTS `finshield.ext_provider_fraud` (
  provider_id STRING NOT NULL,
  claim_count INT64 NOT NULL,
  avg_reimbursement FLOAT64 NOT NULL,
  distinct_physicians INT64 NOT NULL,
  avg_length_of_stay FLOAT64 NOT NULL,
  distinct_diagnosis_codes INT64 NOT NULL,
  inpatient_mix FLOAT64 NOT NULL,
  is_fraud INT64 NOT NULL, -- 1 = PotentialFraud='Yes', 0 = 'No'
  source STRING DEFAULT 'US Medicare, evaluation only'
)
CLUSTER BY provider_id;

-- Table 5: learned_patterns (For F6 Dueling AI feedback loop)
CREATE TABLE IF NOT EXISTS `finshield.learned_patterns` (
  pattern_id STRING NOT NULL,
  tactic STRING NOT NULL,
  feature_signatures STRING NOT NULL,
  evaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
