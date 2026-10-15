-- BigQuery ML Models for FinShield Claims-Fraud Copilot
-- Dataset: finshield

-- 1. Primary Claim Fraud Model: Boosted Tree Classifier with Global Explanations
CREATE OR REPLACE MODEL `finshield.fraud_model`
OPTIONS(
  model_type = 'BOOSTED_TREE_CLASSIFIER',
  input_label_cols = ['is_fraud'],
  enable_global_explain = TRUE,
  data_split_method = 'AUTO_SPLIT',
  max_iterations = 50,
  learn_rate = 0.1
) AS
SELECT
  claim_amount,
  amount_vs_diagnosis_median_ratio,
  length_of_stay,
  claimant_prior_claims_90d,
  provider_claims_per_day,
  doctor_distinct_cities_24h,
  shared_bank_account_count,
  days_policy_start_to_claim,
  line_item_count,
  room_rent_vs_cap_ratio,
  is_fraud
FROM
  `finshield.claims`;

-- Evaluate Primary Claim Fraud Model
SELECT
  *
FROM
  ML.EVALUATE(MODEL `finshield.fraud_model`);

-- Inspect Global Feature Importance
SELECT
  *
FROM
  ML.GLOBAL_EXPLAIN(MODEL `finshield.fraud_model`);

-- Single Claim Prediction with Top-5 Feature Explanations
-- Query pattern executed by backend/tools/bq.py:
/*
SELECT
  predicted_is_fraud,
  prob.prob AS fraud_probability,
  top_feature_attributions
FROM
  ML.EXPLAIN_PREDICT(
    MODEL `finshield.fraud_model`,
    (SELECT @claim_amount AS claim_amount,
            @amount_vs_median AS amount_vs_diagnosis_median_ratio,
            @length_of_stay AS length_of_stay,
            @prior_claims AS claimant_prior_claims_90d,
            @provider_claims_day AS provider_claims_per_day,
            @doctor_cities_24h AS doctor_distinct_cities_24h,
            @shared_bank_count AS shared_bank_account_count,
            @days_policy_to_claim AS days_policy_start_to_claim,
            @line_item_count AS line_item_count,
            @room_rent_vs_cap AS room_rent_vs_cap_ratio),
    STRUCT(5 AS top_k_features)
  ),
  UNNEST(predicted_is_fraud_probs) AS prob
WHERE prob.label = 1;
*/

-- 2. External Validation Model on Real Kaggle Healthcare Provider Fraud Data (US Medicare)
-- Validated on real claims data for evaluation & pitch metrics
CREATE OR REPLACE MODEL `finshield.provider_fraud_model`
OPTIONS(
  model_type = 'BOOSTED_TREE_CLASSIFIER',
  input_label_cols = ['is_fraud'],
  enable_global_explain = TRUE,
  data_split_method = 'AUTO_SPLIT',
  max_iterations = 50,
  learn_rate = 0.1
) AS
SELECT
  claim_count,
  avg_reimbursement,
  distinct_physicians,
  avg_length_of_stay,
  distinct_diagnosis_codes,
  inpatient_mix,
  is_fraud
FROM
  `finshield.ext_provider_fraud`;

-- Evaluate Real-World Provider Model
SELECT
  *
FROM
  ML.EVALUATE(MODEL `finshield.provider_fraud_model`);
