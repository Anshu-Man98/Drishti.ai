import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { SearchBar } from '../components/ui/SearchBar';
import { FilterButton } from '../components/ui/FilterButton';
import { ToggleSwitch } from '../components/ui/ToggleSwitch';
import { GlowCard } from '../components/ui/GlowCard';
import { Dashboard } from '../pages/Dashboard';
import { NetworkGraph } from '../pages/NetworkGraph';
import { vi } from 'vitest';

vi.mock('../services/api', () => ({
  fetchFraudRings: vi.fn().mockResolvedValue({
    rings: [
      {
        ring_id: 'RING-9999',
        title: 'Syndicate 9999: Shared Bank Account Ring',
        risk_level: 'critical',
        total_amount: 10292124,
        claim_count: 181,
        claimant_count: 97,
        description: 'Test description',
        sample_cities: ['Mumbai']
      },
      {
        ring_id: 'RING-8888',
        title: 'Syndicate 8888: Shared Bank Account Ring',
        risk_level: 'high',
        total_amount: 1898034,
        claim_count: 26,
        claimant_count: 16,
        description: 'Test description 2',
        sample_cities: ['Delhi']
      }
    ],
    selected_ring: {
      ring: {
        ring_id: 'RING-9999',
        title: 'Syndicate 9999: Shared Bank Account Ring',
        risk_level: 'critical',
        total_amount: 10292124,
        claim_count: 181,
        claimant_count: 97,
        description: 'Test description',
        sample_cities: ['Mumbai']
      },
      nodes: [],
      edges: [],
      claims: [
        {
          claim_id: 'CLM-100618',
          claimant_name: 'Aadhya Bhat',
          claimant_id: 'CLMNT-5600',
          hospital_name: 'Metro Hospital',
          city: 'Bengaluru',
          admission_ts: '2026-06-20T14:30:00Z',
          total_claimed: 152326,
          fraud_type: 'clean',
          doctor_id: 'DOC-2027'
        }
      ]
    }
  }),
  fetchAnalyticsSummary: vi.fn().mockResolvedValue({
    total_claims: 10,
    total_amount: 100000,
    loss_mitigation_ratio: 0.8,
    verdicts: { approve: 8, review: 1, reject: 1 },
    tat_seconds_p50: 2,
    tat_seconds_p95: 5,
    recent_critical_claims: []
  })
}));

describe('Light Theme Frame Visibility & Contrast Verification', () => {
  it('verifies SearchBar has border-app-border and bg-app-surface classes', () => {
    render(<SearchBar value="" onChange={() => {}} placeholder="Search test" />);
    const input = screen.getByPlaceholderText('Search test');
    expect(input.className).toContain('border-app-border');
    expect(input.className).toContain('bg-app-surface');
  });

  it('verifies FilterButton has border-app-border and bg-app-surface classes when inactive', () => {
    render(<FilterButton onClick={() => {}} label="Filter" isOpen={false} />);
    const btn = screen.getByRole('button', { name: /Filter/i });
    expect(btn.className).toContain('border-app-border');
    expect(btn.className).toContain('bg-app-surface');
  });

  it('verifies ToggleSwitch has visible light mode track and thumb styling', () => {
    render(<ToggleSwitch checked={false} onChange={() => {}} label="Include demo" />);
    const toggle = screen.getByRole('switch', { name: /Include demo/i });
    expect(toggle.className).toContain('border-stone-300');
    expect(toggle.className).toContain('bg-stone-200');
  });

  it('verifies GlowCard uses border-app-border for crisp light mode contrast', () => {
    const { container } = render(<GlowCard>Content</GlowCard>);
    const card = container.firstChild as HTMLElement;
    expect(card.className).toContain('border-app-border');
    expect(card.className).not.toContain('light:');
  });

  it('renders Dashboard controls row in a framed container', () => {
    render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );
    const searchInput = screen.getByPlaceholderText(/Filter claims, claimants/i);
    // The controls container wrapping the row
    const controlsRow = searchInput.closest('.p-3') || searchInput.closest('.p-3\\.5') || searchInput.closest('.rounded-2xl');
    expect(controlsRow).toBeTruthy();
    expect(controlsRow?.className).toContain('border-app-border');
    expect(controlsRow?.className).toContain('bg-app-surface');
  });

  it('renders NetworkGraph detected syndicate cards with visible frames', async () => {
    const { container } = render(
      <BrowserRouter>
        <NetworkGraph />
      </BrowserRouter>
    );
    // Wait for the rings to be rendered
    const matches = await screen.findAllByText(/Syndicate 9999/i);
    expect(matches.length).toBeGreaterThan(0);
    const buttons = container.querySelectorAll('button');
    const ringButton = Array.from(buttons).find(b => b.className.includes('border-app-border') || b.className.includes('border-amber-primary'));
    expect(ringButton).toBeTruthy();
  });
});
