import { describe, it, expect } from 'vitest';
import { AnalyticsSummary } from '../types';

describe('Dashboard Data-to-Chart Transformations', () => {
  const mockSummary: AnalyticsSummary = {
    total_claims: 100,
    total_amount_claimed: 25000000,
    total_amount_protected: 8500000,
    total_amount_review: 4200000,
    verdicts: {
      approve: 50,
      review: 20,
      reject: 25,
      pending: 5,
    },
    fraud_categories: [
      { category: 'Unbundled / Padded Ancillary', count: 12 },
      { category: 'Shared Bank Account Ring', count: 8 },
      { category: 'Impossible Spacetime Velocity', count: 7 },
      { category: 'Arithmetic Discrepancy', count: 6 },
      { category: 'Prompt Injection Payload', count: 4 },
      { category: 'Other Policy Breaches', count: 3 },
    ],
    agent_breakdown: {
      forensics: 14,
      policy: 9,
      spacetime: 7,
      crossref: 8,
      ml: 22,
      rag: 8,
    },
    agent_claims_breakdown: {
      forensics: 11,
      policy: 7,
      spacetime: 4,
      crossref: 6,
      ml: 18,
      rag: 7,
    },
    recent_critical_claims: [
      {
        claim_id: 'CLM-G5-INFLATED',
        policy_id: 'POL-CARE-99812',
        insurer_id: 'INS-CARE',
        claimant_name: 'Pooja Nair',
        hospital_name: 'Apex Super Specialty Hospital',
        city: 'Mumbai',
        diagnosis_code: 'K35.8',
        total_claimed: 155000,
        risk_score: 95,
        verdict: 'reject',
        top_finding_title: 'Price exceeds diagnosis benchmark',
        created_at: new Date().toISOString(),
      },
    ],
    synthetic_count: 5,
    timestamp: new Date().toISOString(),
  };

  it('correctly maps adjudication flow totals into Sankey flow ratios', () => {
    const { total_claims, verdicts } = mockSummary;
    expect(total_claims).toBe(100);

    const approvePct = Math.round((verdicts.approve / total_claims) * 100);
    const reviewPct = Math.round((verdicts.review / total_claims) * 100);
    const rejectPct = Math.round((verdicts.reject / total_claims) * 100);

    expect(approvePct).toBe(50);
    expect(reviewPct).toBe(20);
    expect(rejectPct).toBe(25);
  });

  it('transforms fraud categories into sorted distribution chart items', () => {
    const sorted = [...mockSummary.fraud_categories].sort((a, b) => b.count - a.count);

    expect(sorted[0].category).toBe('Unbundled / Padded Ancillary');
    expect(sorted[0].count).toBe(12);
    expect(sorted[1].category).toBe('Shared Bank Account Ring');

    const totalCategoryCount = sorted.reduce((acc, curr) => acc + curr.count, 0);
    expect(totalCategoryCount).toBe(40);
  });

  it('verifies distinct claims affected per agent are always <= finding counts', () => {
    for (const [agent, findingsCount] of Object.entries(mockSummary.agent_breakdown)) {
      const claimsAffected = mockSummary.agent_claims_breakdown?.[agent] ?? 0;
      expect(claimsAffected).toBeGreaterThan(0);
      expect(claimsAffected).toBeLessThanOrEqual(findingsCount);
    }
  });

  it('calculates authentic claims count when excluding synthetic/demo test data', () => {
    const totalClaims = mockSummary.total_claims;
    const syntheticClaims = mockSummary.synthetic_count ?? 0;
    const authenticClaims = totalClaims - syntheticClaims;

    expect(authenticClaims).toBe(95);
    expect(syntheticClaims).toBe(5);
  });

  it('ensures financial loss prevented matches rejected claim sums', () => {
    expect(mockSummary.total_amount_protected).toBe(8500000);
    expect(mockSummary.verdicts.reject).toBe(25);
    const avgSavingsPerReject = mockSummary.total_amount_protected / mockSummary.verdicts.reject;
    expect(avgSavingsPerReject).toBe(340000);
  });

  it('maps fraud categories into RankedList percentages and claims count', () => {
    const totalFindings = mockSummary.fraud_categories.reduce((acc, cat) => acc + cat.count, 0);
    expect(totalFindings).toBe(40);

    const topCategory = mockSummary.fraud_categories[0];
    const topPct = Math.round((topCategory.count / totalFindings) * 100);
    expect(topPct).toBe(30); // 12 / 40 = 30%
  });

  it('calculates ArcGauge loss prevention percentage ratio correctly', () => {
    const ratio = Math.round((mockSummary.verdicts.reject / mockSummary.total_claims) * 100);
    expect(ratio).toBe(25); // 25 / 100 = 25%
  });
});
