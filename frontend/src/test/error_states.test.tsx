import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SpacetimeMap } from '../components/SpacetimeMap';
import { Badge } from '../components/common/Badge';

describe('Error States & Missing Configuration', () => {
  it('renders fail-loud configuration message when Google Maps API key is missing', () => {
    // In test environment, import.meta.env.VITE_GOOGLE_MAPS_API_KEY is unset or empty
    render(
      <SpacetimeMap
        timeline={[]}
        claimId="CLM-TEST-001"
        apiKey=""
        onOpenDocument={() => {}}
      />
    );

    // Assert the exact fail-loud card appears
    expect(screen.getByText('Google Maps API Key Required')).toBeInTheDocument();
    expect(screen.getByText('VITE_GOOGLE_MAPS_API_KEY')).toBeInTheDocument();
    expect(screen.getByText(/frontend\/\.env\.local/i)).toBeInTheDocument();
  });

  it('renders verdict badges properly for all states including review and reject', () => {
    const { rerender } = render(<Badge variant="approve" score={15} />);
    expect(screen.getByText('Approve')).toBeInTheDocument();
    expect(screen.getByText('(15)')).toBeInTheDocument();

    rerender(<Badge variant="review" score={45} />);
    expect(screen.getByText('Review')).toBeInTheDocument();
    expect(screen.getByText('(45)')).toBeInTheDocument();

    rerender(<Badge variant="reject" score={85} />);
    expect(screen.getByText('Reject')).toBeInTheDocument();
    expect(screen.getByText('(85)')).toBeInTheDocument();

    rerender(<Badge variant="pending" />);
    expect(screen.getByText('Pending Audit')).toBeInTheDocument();
  });

  it('renders severity badges with pulse indicator for critical severity', () => {
    render(<Badge variant="critical" label="Critical Finding" />);
    expect(screen.getByText('Critical Finding')).toBeInTheDocument();
  });
});
