import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ClaimsList } from '../pages/ClaimsList';
import * as api from '../services/api';
import { ClaimSummary } from '../types';

vi.mock('../services/api', () => ({
  fetchClaims: vi.fn(),
}));

describe('Dashboard to Claims Queue Filter Integration', () => {
  const mockClaims: ClaimSummary[] = [
    {
      claim_id: 'CLM-001',
      policy_id: 'POL-100',
      insurer_id: 'INS-01',
      claimant_name: 'Jane Doe',
      hospital_name: 'Metro Hospital',
      city: 'Mumbai',
      total_claimed: 50000,
      admission_ts: '2026-03-01T10:00:00Z',
      discharge_ts: '2026-03-04T12:00:00Z',
      diagnosis_code: 'A09',
      doc_count: 2,
      created_at: '2026-03-01T10:00:00Z',
      verdict: 'reject',
      risk_score: 95,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchClaims).mockResolvedValue({
      claims: mockClaims,
      totalCount: 1,
    });
  });

  it('filters by verdict when navigated with ?verdict=reject', async () => {
    render(
      <MemoryRouter initialEntries={['/claims?verdict=reject']}>
        <ClaimsList />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(api.fetchClaims).toHaveBeenCalledWith(
        expect.objectContaining({
          verdict: 'reject',
        })
      );
    });

    // Check active filter badge
    expect(screen.getByText(/VERDICT: REJECT/i)).toBeInTheDocument();
  });

  it('filters by category when navigated with ?category=Arithmetic%20%26%20Math%20Mismatches', async () => {
    render(
      <MemoryRouter initialEntries={['/claims?category=Arithmetic%20%26%20Math%20Mismatches']}>
        <ClaimsList />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(api.fetchClaims).toHaveBeenCalledWith(
        expect.objectContaining({
          category: 'Arithmetic & Math Mismatches',
        })
      );
    });

    // Check active filter badge for category
    expect(screen.getByText(/Vector: Arithmetic & Math Mismatches/i)).toBeInTheDocument();
  });

  it('allows clearing the category filter via the clear button', async () => {
    render(
      <MemoryRouter initialEntries={['/claims?category=Arithmetic%20%26%20Math%20Mismatches']}>
        <ClaimsList />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Vector: Arithmetic & Math Mismatches/i)).toBeInTheDocument();
    });

    const clearBtn = screen.getByRole('button', { name: /clear vector filter/i });
    fireEvent.click(clearBtn);

    await waitFor(() => {
      expect(api.fetchClaims).toHaveBeenLastCalledWith(
        expect.objectContaining({
          category: undefined,
        })
      );
    });
  });
});

import { Dashboard } from '../pages/Dashboard';

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchClaims: vi.fn().mockResolvedValue({ claims: [], totalCount: 0 }),
    fetchAnalyticsSummary: vi.fn().mockResolvedValue({
      total_claims: 42,
      total_amount_claimed: 1500000,
      total_amount_protected: 450000,
      total_amount_review: 200000,
      verdicts: {
        approve: 25,
        review: 7,
        reject: 10,
        pending: 0,
      },
      fraud_categories: [
        { category: 'Arithmetic & Math Mismatches', count: 5, claims_count: 5 },
        { category: 'Spacetime & Teleportation Anomalies', count: 3, claims_count: 3 },
      ],
      time_series: [],
      recent_critical_claims: [],
      synthetic_count: 0,
      timestamp: new Date().toISOString(),
    }),
  };
});

const mockedNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mockedNavigate,
  };
});

describe('Dashboard KPI & Anomaly Vector Click Navigation', () => {
  beforeEach(() => {
    mockedNavigate.mockClear();
  });

  it('navigates to /claims?verdict=all when Claims Audited is clicked', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Claims Audited')).toBeInTheDocument();
    });

    const card = screen.getByText('Claims Audited').closest('div');
    if (card) fireEvent.click(card);

    expect(mockedNavigate).toHaveBeenCalledWith('/claims?verdict=all');
  });

  it('navigates to /claims?verdict=reject when Fraud Loss Prevented is clicked', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Fraud Loss Prevented')).toBeInTheDocument();
    });

    const card = screen.getByText('Fraud Loss Prevented').closest('div');
    if (card) fireEvent.click(card);

    expect(mockedNavigate).toHaveBeenCalledWith('/claims?verdict=reject');
  });

  it('navigates to /claims?verdict=review when Under Manual Review is clicked', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Under Manual Review')).toBeInTheDocument();
    });

    const card = screen.getByText('Under Manual Review').closest('div');
    if (card) fireEvent.click(card);

    expect(mockedNavigate).toHaveBeenCalledWith('/claims?verdict=review');
  });

  it('navigates to /claims?verdict=approve when Auto-Approved Rate is clicked', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Auto-Approved Rate')).toBeInTheDocument();
    });

    const card = screen.getByText('Auto-Approved Rate').closest('div');
    if (card) fireEvent.click(card);

    expect(mockedNavigate).toHaveBeenCalledWith('/claims?verdict=approve');
  });

  it('navigates to category when an anomaly vector is clicked', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Arithmetic & Math Mismatches')).toBeInTheDocument();
    });

    const itemBtn = screen.getByText('Arithmetic & Math Mismatches').closest('button');
    if (itemBtn) fireEvent.click(itemBtn);

    expect(mockedNavigate).toHaveBeenCalledWith(
      `/claims?category=${encodeURIComponent('Arithmetic & Math Mismatches')}`
    );
  });

  it('navigates to all_anomalies when Top 4 Anomaly Vectors title or View All is clicked', async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Top 4 Anomaly Vectors')).toBeInTheDocument();
    });

    const titleBtn = screen.getByRole('button', { name: /Top 4 Anomaly Vectors/i });
    fireEvent.click(titleBtn);

    expect(mockedNavigate).toHaveBeenCalledWith('/claims?category=all_anomalies');
  });
});
