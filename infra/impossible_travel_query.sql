-- =====================================================================
-- FinShield Pitch Query: Doctors with Physically Impossible Spacetime Legs
-- =====================================================================
-- Detects systemic provider fraud where doctors bill simultaneous or
-- overlapping procedures across distant cities within a 24-hour window.
--
-- Travel Physics Model:
--   - Road travel: km / 80.0 km/h for distance <= 300 km
--   - Air travel: 2.5h (airport security/boarding) + km / 700.0 km/h for > 300 km

WITH doctor_claim_pairs AS (
  SELECT
    c1.doctor_id,
    c1.claim_id AS claim_id_1,
    c1.admission_ts AS event_time_1,
    c1.hospital_name AS hospital_1,
    c1.city AS city_1,
    c1.lat AS lat_1,
    c1.lng AS lng_1,
    c2.claim_id AS claim_id_2,
    c2.admission_ts AS event_time_2,
    c2.hospital_name AS hospital_2,
    c2.city AS city_2,
    c2.lat AS lat_2,
    c2.lng AS lng_2,
    -- Available elapsed time between events in hours
    TIMESTAMP_DIFF(c2.admission_ts, c1.admission_ts, MINUTE) / 60.0 AS available_hours,
    -- Haversine distance in kilometers via ST_DISTANCE
    ST_DISTANCE(ST_GEOGPOINT(c1.lng, c1.lat), ST_GEOGPOINT(c2.lng, c2.lat)) / 1000.0 AS distance_km
  FROM
    `finshield.claims` c1
  JOIN
    `finshield.claims` c2
  ON
    c1.doctor_id = c2.doctor_id
    AND c1.claim_id != c2.claim_id
    AND c2.admission_ts > c1.admission_ts
    AND TIMESTAMP_DIFF(c2.admission_ts, c1.admission_ts, HOUR) <= 24
),
feasibility_evaluation AS (
  SELECT
    *,
    CASE
      WHEN distance_km <= 300.0 THEN distance_km / 80.0
      ELSE 2.5 + (distance_km / 700.0)
    END AS min_required_travel_hours
  FROM
    doctor_claim_pairs
  WHERE
    distance_km >= 5.0 -- Exclude same campus/city hospital facilities
)
SELECT
  doctor_id,
  claim_id_1,
  event_time_1,
  city_1,
  hospital_1,
  claim_id_2,
  event_time_2,
  city_2,
  hospital_2,
  ROUND(distance_km, 1) AS distance_km,
  ROUND(available_hours * 60, 0) AS elapsed_minutes,
  ROUND(min_required_travel_hours, 2) AS min_required_hours,
  ROUND(min_required_travel_hours - available_hours, 2) AS impossible_time_deficit_hours,
  'CRITICAL_SPACETIME_IMPOSSIBILITY' AS audit_status
FROM
  feasibility_evaluation
WHERE
  available_hours < min_required_travel_hours
ORDER BY
  impossible_time_deficit_hours DESC;
