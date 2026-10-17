import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MLFeatureAttributions } from '../components/claim/MLFeatureAttributions';
import { MlFeature } from '../types';

describe('MLFeatureAttributions Component', () => {
  it('renders explicit empty state when features array is empty or undefined', () => {
    const { rerender } = render(<MLFeatureAttributions features={[]} />);
    expect(screen.getByText(/No attribution available \(model not trained \/ explain failed\)/i)).toBeInTheDocument();
    expect(screen.getByText(/No feature attributions exceeded the significance threshold/i)).toBeInTheDocument();

    rerender(<MLFeatureAttributions features={undefined} />);
    expect(screen.getByText(/No attribution available \(model not trained \/ explain failed\)/i)).toBeInTheDocument();
  });

  it('renders explicit empty state when all features are below significance threshold (< 0.001)', () => {
    const negligibleFeatures: MlFeature[] = [
      { feature: 'claim_amount', attribution: 0.0000 },
      { feature: 'length_of_stay', attribution: 0.0005 },
      { feature: 'line_item_count', attribution: -0.0002 },
    ];
    render(<MLFeatureAttributions features={negligibleFeatures} />);
    expect(screen.getByText(/No attribution available/i)).toBeInTheDocument();
    expect(screen.getByText(/No feature attributions exceeded the significance threshold/i)).toBeInTheDocument();
    // Verify none of the feature labels are rendered as rows
    expect(screen.queryByText('Total Claim Amount')).not.toBeInTheDocument();
  });

  it('displays custom error reason in the empty state card', () => {
    render(
      <MLFeatureAttributions
        features={[]}
        errorReason="ML.EXPLAIN_PREDICT timed out on warehouse cluster"
      />
    );
    expect(
      screen.getByText(/No attribution available \(ML\.EXPLAIN_PREDICT timed out on warehouse cluster\)/i)
    ).toBeInTheDocument();
  });

  it('renders baseline probability prior and model probability in the header', () => {
    render(
      <MLFeatureAttributions
        features={[{ feature: 'room_rent_vs_cap_ratio', attribution: 0.45, direction: 'raises risk' }]}
        mlScore={0.784}
        baselineScore={0.122}
      />
    );
    expect(screen.getByText(/Baseline prior:/i)).toBeInTheDocument();
    expect(screen.getByText('12.2%')).toBeInTheDocument();
    expect(screen.getByText('78.4%')).toBeInTheDocument();
  });

  it('renders direction labels and signs correctly: raises risk vs lowers risk', () => {
    const features: MlFeature[] = [
      { feature: 'room_rent_vs_cap_ratio', attribution: 0.6378, direction: 'raises risk' },
      { feature: 'claimant_prior_claims_90d', attribution: -0.0647, direction: 'lowers risk' },
    ];
    render(<MLFeatureAttributions features={features} mlScore={0.65} />);

    // Verify feature labels
    expect(screen.getByText('Room Rent vs Policy Cap Ratio')).toBeInTheDocument();
    expect(screen.getByText('Claimant Prior Claims (90d)')).toBeInTheDocument();

    // Verify direction badges
    expect(screen.getByText('raises risk')).toBeInTheDocument();
    expect(screen.getByText('lowers risk')).toBeInTheDocument();

    // Verify formatted values with correct signs
    expect(screen.getByText('+0.6378')).toBeInTheDocument();
    expect(screen.getByText('-0.0647')).toBeInTheDocument();
  });

  it('filters out negligible features while retaining significant ones', () => {
    const mixedFeatures: MlFeature[] = [
      { feature: 'amount_vs_diagnosis_median_ratio', attribution: 0.4624, direction: 'raises risk' },
      { feature: 'shared_bank_account_count', attribution: 0.0001, direction: 'raises risk' }, // negligible
      { feature: 'doctor_distinct_cities_24h', attribution: -0.152, direction: 'lowers risk' },
    ];
    render(<MLFeatureAttributions features={mixedFeatures} />);

    expect(screen.getByText('Claim vs Diagnosis Median Ratio')).toBeInTheDocument();
    expect(screen.getByText('Doctor 24h Distinct Cities')).toBeInTheDocument();
    // Negligible feature must NOT appear
    expect(screen.queryByText('Shared Bank Account Count')).not.toBeInTheDocument();
  });
});
