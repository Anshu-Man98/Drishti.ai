-- BigQuery ML Models for FinShield Claims-Fraud Copilot
-- Dataset: finshield

-- 1. Feature Engineering View: Claims enriched with BigQuery benchmark distributions
CREATE OR REPLACE VIEW `finshield.claims_ml_features` AS
WITH tagged_items AS (
  SELECT 
    l.claim_id,
    c.diagnosis_code,
    c.total_claimed,
    l.unit_price,
    l.amount,
    CASE 
      WHEN LOWER(l.description) LIKE '%icu%' OR LOWER(l.description) LIKE '%intensive care%' THEN 'icu'
      WHEN LOWER(l.description) LIKE '%room%' OR LOWER(l.description) LIKE '%ward%' OR LOWER(l.description) LIKE '%bed%' THEN 'room_rent'
      WHEN LOWER(l.description) LIKE '%surgery%' OR LOWER(l.description) LIKE '%ot%' OR LOWER(l.description) LIKE '%procedure%' OR LOWER(l.description) LIKE '%operation%' THEN 'surgery_ot'
      WHEN LOWER(l.description) LIKE '%doctor%' OR LOWER(l.description) LIKE '%consult%' OR LOWER(l.description) LIKE '%visiting%' OR LOWER(l.description) LIKE '%physician%' THEN 'consultation'
      WHEN LOWER(l.description) LIKE '%medicine%' OR LOWER(l.description) LIKE '%pharmacy%' OR LOWER(l.description) LIKE '%drug%' THEN 'pharmacy'
      WHEN LOWER(l.description) LIKE '%mri%' OR LOWER(l.description) LIKE '%scan%' OR LOWER(l.description) LIKE '%x-ray%' OR LOWER(l.description) LIKE '%diagnostic%' OR LOWER(l.description) LIKE '%investigation%' OR LOWER(l.description) LIKE '%lab%' OR LOWER(l.description) LIKE '%pathology%' THEN 'diagnostics'
      ELSE 'ancillary'
    END as category
  FROM `finshield.line_items` l
  JOIN `finshield.claims` c ON l.claim_id = c.claim_id
),
item_with_bench AS (
  SELECT 
    t.claim_id,
    t.total_claimed,
    t.unit_price,
    t.amount,
    t.category,
    SAFE_DIVIDE(t.unit_price, COALESCE(cb.unit_price_p50, gb.unit_price_p50, 2000.0)) as price_ratio
  FROM tagged_items t
  LEFT JOIN `finshield.category_benchmarks` cb ON t.diagnosis_code = cb.diagnosis_code AND t.category = cb.category AND cb.fallback_level = 'exact'
  LEFT JOIN `finshield.category_benchmarks` gb ON t.category = gb.category AND gb.fallback_level = 'global'
),
item_aggregates AS (
  SELECT 
    claim_id,
    MAX(price_ratio) as max_line_item_price_ratio,
    SAFE_DIVIDE(
      SUM(CASE WHEN category = 'ancillary' THEN amount ELSE 0.0 END),
      MAX(total_claimed)
    ) as ancillary_share_of_total
  FROM item_with_bench
  GROUP BY claim_id
),
ranked_claims AS (
  SELECT 
    c.*,
    COALESCE(i.max_line_item_price_ratio, 1.0) as max_line_item_price_ratio,
    COALESCE(i.ancillary_share_of_total, 0.0) as ancillary_share_of_total,
    ROUND(PERCENT_RANK() OVER (PARTITION BY c.diagnosis_code ORDER BY c.total_claimed), 4) as total_percentile_vs_diagnosis,
    ROUND(SAFE_DIVIDE(c.total_claimed, COALESCE(b.p50, 49916.56)), 3) as benchmark_amount_vs_diagnosis_median_ratio,
    -- Provider-grouped train/test split (80/20) by hospital_id to eliminate data leakage
    CASE WHEN MOD(ABS(FARM_FINGERPRINT(c.hospital_id)), 10) >= 8 THEN TRUE ELSE FALSE END as is_eval
  FROM `finshield.claims` c
  LEFT JOIN `finshield.diagnosis_benchmarks` b ON c.diagnosis_code = b.diagnosis_code AND b.fallback_level = 'exact'
  LEFT JOIN item_aggregates i ON c.claim_id = i.claim_id
)
SELECT 
  claim_amount,
  benchmark_amount_vs_diagnosis_median_ratio AS amount_vs_diagnosis_median_ratio,
  total_percentile_vs_diagnosis,
  max_line_item_price_ratio,
  ancillary_share_of_total,
  length_of_stay,
  claimant_prior_claims_90d,
  provider_claims_per_day,
  doctor_distinct_cities_24h,
  shared_bank_account_count,
  days_policy_start_to_claim,
  line_item_count,
  room_rent_vs_cap_ratio,
  is_fraud,
  is_eval
FROM ranked_claims;


-- 2. Primary Claim Fraud Model: Boosted Tree Classifier with Global Explanations
-- Trained on benchmark-aware features with custom hold-out test set grouped by hospital
CREATE OR REPLACE MODEL `finshield.fraud_model`
OPTIONS(
  model_type = 'BOOSTED_TREE_CLASSIFIER',
  input_label_cols = ['is_fraud'],
  enable_global_explain = TRUE,
  data_split_method = 'CUSTOM',
  data_split_col = 'is_eval',
  max_iterations = 50,
  learn_rate = 0.1
) AS
SELECT
  claim_amount,
  amount_vs_diagnosis_median_ratio,
  total_percentile_vs_diagnosis,
  max_line_item_price_ratio,
  ancillary_share_of_total,
  length_of_stay,
  claimant_prior_claims_90d,
  provider_claims_per_day,
  doctor_distinct_cities_24h,
  shared_bank_account_count,
  days_policy_start_to_claim,
  line_item_count,
  room_rent_vs_cap_ratio,
  is_fraud,
  is_eval
FROM
  `finshield.claims_ml_features`;

-- Evaluate Primary Claim Fraud Model on Holdout Set
SELECT
  *
FROM
  ML.EVALUATE(MODEL `finshield.fraud_model`);

-- Inspect Global Feature Importance
SELECT
  *
FROM
  ML.GLOBAL_EXPLAIN(MODEL `finshield.fraud_model`);

-- Real-Time Inference with Top-5 Attributions
SELECT
  *
FROM
  ML.EXPLAIN_PREDICT(
    MODEL `finshield.fraud_model`,
    (SELECT * FROM `finshield.claims_ml_features` WHERE is_eval = TRUE LIMIT 5),
    STRUCT(5 AS top_k_features)
  );

-- 3. External Validation Model on Real Kaggle Healthcare Provider Fraud Data (US Medicare)
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
