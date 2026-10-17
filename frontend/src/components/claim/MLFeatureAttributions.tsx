import React from 'react';
import { BarChart3 } from 'lucide-react';
import { MlFeature } from '../../types';

interface MLFeatureAttributionsProps {
  features?: MlFeature[];
  mlScore?: number | null;
  baselineScore?: number | null;
  errorReason?: string;
}

const FEATURE_LABELS: Record<string, string> = {
  amount_vs_diagnosis_median_ratio: 'Claim vs Diagnosis Median Ratio',
  doctor_distinct_cities_24h: 'Doctor 24h Distinct Cities',
  room_rent_vs_cap_ratio: 'Room Rent vs Policy Cap Ratio',
  line_item_math_mismatch_pct: 'Line Item Math Mismatch %',
  historical_duplicate_count: 'Historical Duplicate Submissions',
  claimant_prior_claims_90d: 'Claimant Prior Claims (90d)',
  prior_claim_count_365d: 'Prior Claims (365d)',
  length_of_stay: 'Length of Stay (Days)',
  length_of_stay_days: 'Length of Stay (Days)',
  claim_amount: 'Total Claim Amount',
  total_claimed: 'Total Claim Amount',
  provider_claims_per_day: 'Provider Daily Claim Velocity',
  shared_bank_account_count: 'Shared Bank Account Count',
  days_policy_start_to_claim: 'Days Policy Start to Claim',
  line_item_count: 'Number of Line Items',
  total_percentile_vs_diagnosis: 'Diagnosis Cost Percentile',
  max_line_item_price_ratio: 'Max Line Item Price vs Benchmark',
  ancillary_share_of_total: 'Ancillary / Consumables Share',
};

export const MLFeatureAttributions: React.FC<MLFeatureAttributionsProps> = ({
  features,
  mlScore,
  baselineScore,
  errorReason,
}) => {
  // Hide features with zero or negligible attribution (threshold |attr| < 0.001)
  const significantFeatures = (features || []).filter(
    (f) => Math.abs(f.attribution) >= 0.001
  );

  const baselinePct = ((baselineScore ?? 0.122) * 100).toFixed(1);
  const modelPct = mlScore !== undefined && mlScore !== null ? (mlScore * 100).toFixed(1) : undefined;

  const maxAttr = significantFeatures.length > 0
    ? Math.max(...significantFeatures.map((f) => Math.abs(f.attribution)), 0.05)
    : 0.05;

  return (
    <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 shadow-2xs backdrop-blur-md space-y-4">
      <div className="flex items-center justify-between border-b border-white/8 pb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted flex items-center gap-1.5">
          <BarChart3 className="w-3.5 h-3.5 text-amber-primary" />
          <span>BigQuery ML Explainability (Top Attributions)</span>
        </h3>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
          ML.EXPLAIN_PREDICT
        </span>
      </div>

      {modelPct !== undefined && (
        <div className="flex items-center justify-between text-xs font-mono bg-surface-elevated/70 px-4 py-2.5 rounded-xl border border-white/8">
          <span className="text-text-secondary">
            Baseline prior: <strong className="text-text-primary">{baselinePct}%</strong>
          </span>
          <span className="text-muted">→</span>
          <span className="text-text-secondary">
            Model: <strong className="text-amber-primary">{modelPct}%</strong>
          </span>
        </div>
      )}

      {significantFeatures.length === 0 ? (
        <div className="p-4 rounded-xl border border-dashed border-white/10 text-center space-y-1 bg-surface-elevated/30">
          <p className="text-xs font-medium text-text-primary">
            No attribution available ({errorReason || 'model not trained / explain failed'})
          </p>
          <p className="text-[11px] text-muted">
            No feature attributions exceeded the significance threshold (|attr| ≥ 0.001) for this claim.
          </p>
        </div>
      ) : (
        <>
          <p className="text-xs text-text-secondary">
            Feature attributions driving the boosted-tree model&apos;s fraud probability prediction:
          </p>

          <div className="space-y-3 bg-surface-elevated/50 p-4 rounded-xl border border-white/6">
            {significantFeatures.map((feat) => {
              const widthPct = Math.min(
                100,
                Math.max(8, Math.round((Math.abs(feat.attribution) / maxAttr) * 100))
              );
              const isRiskDriver = feat.direction
                ? feat.direction === 'raises risk'
                : feat.attribution > 0;
              const directionLabel = isRiskDriver ? 'raises risk' : 'lowers risk';
              const label = FEATURE_LABELS[feat.feature] || feat.feature.replace(/_/g, ' ');

              return (
                <div key={feat.feature} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-text-primary font-medium">{label}</span>
                    <div className="flex items-center gap-2 font-mono text-[11px] tabular-nums">
                      <span
                        className={
                          isRiskDriver
                            ? 'text-amber-primary font-bold'
                            : 'text-muted font-bold'
                        }
                      >
                        {feat.attribution > 0 ? `+${feat.attribution.toFixed(4)}` : feat.attribution.toFixed(4)}
                      </span>
                      <span
                        className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                          isRiskDriver
                            ? 'bg-amber-primary/10 text-amber-primary border border-amber-primary/25'
                            : 'bg-white/5 text-muted border border-white/10'
                        }`}
                      >
                        {directionLabel}
                      </span>
                    </div>
                  </div>
                  {/* Amber bar for raises risk, neutral grey for lowers risk */}
                  <div className="w-full bg-surface rounded-full h-2 overflow-hidden flex border border-white/5">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        isRiskDriver
                          ? 'bg-amber-primary shadow-xs shadow-amber-primary/50'
                          : 'bg-muted/40'
                      }`}
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};
