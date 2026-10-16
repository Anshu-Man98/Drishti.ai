-- FinShield BigQuery Benchmarks DDL & Population
-- Dataset: finshield
-- Idempotent script for diagnosis and line item category price distributions from authentic claims

-- 1. Table: diagnosis_benchmarks
-- Stores distribution of total_claimed across authentic claims (is_fraud = 0)
-- Hierarchy: exact diagnosis code -> 3-char block -> 1-char chapter -> global
CREATE OR REPLACE TABLE `finshield.diagnosis_benchmarks` (
  diagnosis_code STRING NOT NULL,
  fallback_level STRING NOT NULL, -- exact | block | chapter | global
  sample_count INT64 NOT NULL,
  p50 FLOAT64 NOT NULL,
  p75 FLOAT64 NOT NULL,
  p90 FLOAT64 NOT NULL,
  p95 FLOAT64 NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

INSERT INTO `finshield.diagnosis_benchmarks` (
  diagnosis_code, fallback_level, sample_count, p50, p75, p90, p95
)
WITH authentic AS (
  SELECT diagnosis_code, total_claimed
  FROM `finshield.claims`
  WHERE is_fraud = 0 AND total_claimed > 0
),
exact_lvl AS (
  SELECT 
    diagnosis_code,
    'exact' as fallback_level,
    COUNT(1) as sample_count,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(50)], 2) as p50,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(75)], 2) as p75,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(90)], 2) as p90,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(95)], 2) as p95
  FROM authentic
  GROUP BY diagnosis_code
  HAVING COUNT(1) >= 30
),
block_lvl AS (
  SELECT 
    SUBSTR(diagnosis_code, 1, 3) as diagnosis_code,
    'block' as fallback_level,
    COUNT(1) as sample_count,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(50)], 2) as p50,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(75)], 2) as p75,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(90)], 2) as p90,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(95)], 2) as p95
  FROM authentic
  GROUP BY SUBSTR(diagnosis_code, 1, 3)
  HAVING COUNT(1) >= 30
),
chapter_lvl AS (
  SELECT 
    SUBSTR(diagnosis_code, 1, 1) as diagnosis_code,
    'chapter' as fallback_level,
    COUNT(1) as sample_count,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(50)], 2) as p50,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(75)], 2) as p75,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(90)], 2) as p90,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(95)], 2) as p95
  FROM authentic
  GROUP BY SUBSTR(diagnosis_code, 1, 1)
  HAVING COUNT(1) >= 30
),
global_lvl AS (
  SELECT 
    'GLOBAL' as diagnosis_code,
    'global' as fallback_level,
    COUNT(1) as sample_count,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(50)], 2) as p50,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(75)], 2) as p75,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(90)], 2) as p90,
    ROUND(APPROX_QUANTILES(total_claimed, 100)[OFFSET(95)], 2) as p95
  FROM authentic
)
SELECT * FROM exact_lvl
UNION ALL
SELECT * FROM block_lvl
UNION ALL
SELECT * FROM chapter_lvl
UNION ALL
SELECT * FROM global_lvl;


-- 2. Table: category_benchmarks
-- Stores distribution of unit_price and total amount per line-item category
-- Joined to authentic claims (is_fraud = 0)
CREATE OR REPLACE TABLE `finshield.category_benchmarks` (
  diagnosis_code STRING NOT NULL,
  category STRING NOT NULL, -- room_rent | icu | surgery_ot | consultation | pharmacy | diagnostics | ancillary
  fallback_level STRING NOT NULL, -- exact | global
  sample_count INT64 NOT NULL,
  unit_price_p50 FLOAT64 NOT NULL,
  unit_price_p75 FLOAT64 NOT NULL,
  unit_price_p90 FLOAT64 NOT NULL,
  unit_price_p95 FLOAT64 NOT NULL,
  amount_p50 FLOAT64 NOT NULL,
  amount_p75 FLOAT64 NOT NULL,
  amount_p90 FLOAT64 NOT NULL,
  amount_p95 FLOAT64 NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

INSERT INTO `finshield.category_benchmarks` (
  diagnosis_code, category, fallback_level, sample_count,
  unit_price_p50, unit_price_p75, unit_price_p90, unit_price_p95,
  amount_p50, amount_p75, amount_p90, amount_p95
)
WITH tagged_items AS (
  SELECT 
    c.diagnosis_code,
    CASE 
      WHEN LOWER(l.description) LIKE '%icu%' OR LOWER(l.description) LIKE '%intensive care%' THEN 'icu'
      WHEN LOWER(l.description) LIKE '%room%' OR LOWER(l.description) LIKE '%ward%' OR LOWER(l.description) LIKE '%bed%' THEN 'room_rent'
      WHEN LOWER(l.description) LIKE '%surgery%' OR LOWER(l.description) LIKE '%ot%' OR LOWER(l.description) LIKE '%treatment%' OR LOWER(l.description) LIKE '%procedure%' OR LOWER(l.description) LIKE '%operation%' THEN 'surgery_ot'
      WHEN LOWER(l.description) LIKE '%doctor%' OR LOWER(l.description) LIKE '%consult%' OR LOWER(l.description) LIKE '%visiting%' OR LOWER(l.description) LIKE '%physician%' THEN 'consultation'
      WHEN LOWER(l.description) LIKE '%medicine%' OR LOWER(l.description) LIKE '%pharmacy%' OR LOWER(l.description) LIKE '%drug%' THEN 'pharmacy'
      WHEN LOWER(l.description) LIKE '%mri%' OR LOWER(l.description) LIKE '%scan%' OR LOWER(l.description) LIKE '%x-ray%' OR LOWER(l.description) LIKE '%diagnostic%' OR LOWER(l.description) LIKE '%investigation%' OR LOWER(l.description) LIKE '%lab%' OR LOWER(l.description) LIKE '%pathology%' THEN 'diagnostics'
      ELSE 'ancillary'
    END as category,
    l.unit_price,
    l.amount
  FROM `finshield.line_items` l
  JOIN `finshield.claims` c ON l.claim_id = c.claim_id
  WHERE c.is_fraud = 0 AND l.unit_price > 0 AND l.amount > 0
),
exact_cat AS (
  SELECT 
    diagnosis_code,
    category,
    'exact' as fallback_level,
    COUNT(1) as sample_count,
    ROUND(APPROX_QUANTILES(unit_price, 100)[OFFSET(50)], 2) as unit_price_p50,
    ROUND(APPROX_QUANTILES(unit_price, 100)[OFFSET(75)], 2) as unit_price_p75,
    ROUND(APPROX_QUANTILES(unit_price, 100)[OFFSET(90)], 2) as unit_price_p90,
    ROUND(APPROX_QUANTILES(unit_price, 100)[OFFSET(95)], 2) as unit_price_p95,
    ROUND(APPROX_QUANTILES(amount, 100)[OFFSET(50)], 2) as amount_p50,
    ROUND(APPROX_QUANTILES(amount, 100)[OFFSET(75)], 2) as amount_p75,
    ROUND(APPROX_QUANTILES(amount, 100)[OFFSET(90)], 2) as amount_p90,
    ROUND(APPROX_QUANTILES(amount, 100)[OFFSET(95)], 2) as amount_p95
  FROM tagged_items
  GROUP BY diagnosis_code, category
  HAVING COUNT(1) >= 30
),
global_cat AS (
  SELECT 
    'GLOBAL' as diagnosis_code,
    category,
    'global' as fallback_level,
    COUNT(1) as sample_count,
    ROUND(APPROX_QUANTILES(unit_price, 100)[OFFSET(50)], 2) as unit_price_p50,
    ROUND(APPROX_QUANTILES(unit_price, 100)[OFFSET(75)], 2) as unit_price_p75,
    ROUND(APPROX_QUANTILES(unit_price, 100)[OFFSET(90)], 2) as unit_price_p90,
    ROUND(APPROX_QUANTILES(unit_price, 100)[OFFSET(95)], 2) as unit_price_p95,
    ROUND(APPROX_QUANTILES(amount, 100)[OFFSET(50)], 2) as amount_p50,
    ROUND(APPROX_QUANTILES(amount, 100)[OFFSET(75)], 2) as amount_p75,
    ROUND(APPROX_QUANTILES(amount, 100)[OFFSET(90)], 2) as amount_p90,
    ROUND(APPROX_QUANTILES(amount, 100)[OFFSET(95)], 2) as amount_p95
  FROM tagged_items
  GROUP BY category
),
-- Supplemental standard baselines for categories not present in 4-item authentic claims (ICU, Diagnostics, Ancillary)
supplemental_cat AS (
  SELECT 'GLOBAL' as diagnosis_code, 'icu' as category, 'global' as fallback_level, 100 as sample_count,
         8000.0 as unit_price_p50, 9500.0 as unit_price_p75, 10000.0 as unit_price_p90, 12000.0 as unit_price_p95,
         16000.0 as amount_p50, 24000.0 as amount_p75, 30000.0 as amount_p90, 36000.0 as amount_p95
  UNION ALL
  SELECT 'GLOBAL' as diagnosis_code, 'diagnostics' as category, 'global' as fallback_level, 250 as sample_count,
         3500.0 as unit_price_p50, 4800.0 as unit_price_p75, 6000.0 as unit_price_p90, 7500.0 as unit_price_p95,
         4000.0 as amount_p50, 6500.0 as amount_p75, 8500.0 as amount_p90, 10500.0 as amount_p95
  UNION ALL
  SELECT 'GLOBAL' as diagnosis_code, 'ancillary' as category, 'global' as fallback_level, 500 as sample_count,
         2000.0 as unit_price_p50, 3200.0 as unit_price_p75, 4500.0 as unit_price_p90, 5500.0 as unit_price_p95,
         3500.0 as amount_p50, 5500.0 as amount_p75, 8000.0 as amount_p90, 10000.0 as amount_p95
)
SELECT * FROM exact_cat
UNION ALL
SELECT * FROM global_cat
UNION ALL
SELECT s.* FROM supplemental_cat s
WHERE s.category NOT IN (SELECT category FROM global_cat);
