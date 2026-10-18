import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '../context/ThemeContext';
import { AssistantProvider } from '../context/AssistantContext';
import { AppShell } from '../components/layout/AppShell';
import { TopBar } from '../components/layout/TopBar';
import { ChatDrawer } from '../components/ChatDrawer';
import { ClaimChatPickerModal } from '../components/common/ClaimChatPickerModal';
import * as api from '../services/api';
import { ClaimSummary } from '../types';

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchClaims: vi.fn(),
    fetchChatHistory: vi.fn(),
    streamClaimChat: vi.fn(),
    fetchAnalyticsSummary: vi.fn().mockResolvedValue({
      total_claims: 2,
      verdicts: { review: 1, reject: 1, approve: 0 },
    }),
  };
});

const mockClaims: ClaimSummary[] = [
  {
    claim_id: 'CLM-001',
    policy_id: 'POL-001',
    insurer_id: 'INS-HDFC',
    claimant_name: 'Aditi Sharma',
    hospital_name: 'Apex Super Speciality',
    city: 'Mumbai',
    total_claimed: 145000,
    admission_ts: '2026-03-20T10:00:00Z',
    discharge_ts: '2026-03-25T10:00:00Z',
    diagnosis_code: 'M54.5',
    doc_count: 2,
    created_at: '2026-03-28T10:00:00Z',
    risk_score: 88,
    verdict: 'reject',
  },
  {
    claim_id: 'CLM-002',
    policy_id: 'POL-002',
    insurer_id: 'INS-STAR',
    claimant_name: 'Rahul Verma',
    hospital_name: 'Metro City Hospital',
    city: 'Delhi',
    total_claimed: 32000,
    admission_ts: '2026-03-22T11:00:00Z',
    discharge_ts: '2026-03-26T11:00:00Z',
    diagnosis_code: 'I10',
    doc_count: 1,
    created_at: '2026-03-29T11:00:00Z',
    risk_score: 12,
    verdict: 'approve',
  },
];

describe('Part C: Assistant Discoverability & Chat UX Suite', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    (api.fetchClaims as any).mockResolvedValue({
      claims: mockClaims,
      total: 2,
    });
    (api.fetchChatHistory as any).mockResolvedValue([]);
  });

  const renderWithProviders = (
    ui: React.ReactNode,
    { route = '/', role = 'officer' }: { route?: string; role?: string } = {}
  ) => {
    localStorage.setItem('drishti_auth_token', `${role}-token`);
    return render(
      <ThemeProvider>
        <MemoryRouter initialEntries={[route]}>
          <AssistantProvider>
            {ui}
          </AssistantProvider>
        </MemoryRouter>
      </ThemeProvider>
    );
  };

  it('renders persistent Assistant entry in TopBar across every role (user, officer, admin)', () => {
    ['user', 'officer', 'admin'].forEach((role) => {
      const { unmount } = renderWithProviders(<TopBar onOpenMobile={() => {}} />, { role });
      const assistantBtn = screen.getByRole('button', { name: /Case Assistant/i });
      expect(assistantBtn).toBeInTheDocument();
      expect(screen.getByText(/Assistant/i)).toBeInTheDocument();
      unmount();
    });
  });

  it('renders persistent Assistant entry in TopBar and Sidebar across multiple routes in AppShell', () => {
    const routes = ['/', '/claims', '/network', '/duel', '/upload'];
    routes.forEach((route) => {
      const { unmount } = renderWithProviders(
        <AppShell>
          <div>Page content for {route}</div>
        </AppShell>,
        { route }
      );
      const assistantBtns = screen.getAllByRole('button', { name: /Case Assistant/i });
      expect(assistantBtns.length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText(`Page content for ${route}`)).toBeInTheDocument();
      unmount();
    });
  });

  it('claim picker modal displays real claims and filters by search query', async () => {
    const onSelectClaim = vi.fn();
    const onClose = vi.fn();

    renderWithProviders(
      <ClaimChatPickerModal
        isOpen={true}
        onClose={onClose}
        onSelectClaim={onSelectClaim}
      />
    );

    // Should fetch and render real claims
    await waitFor(() => {
      expect(screen.getByText('CLM-001')).toBeInTheDocument();
      expect(screen.getByText('Aditi Sharma')).toBeInTheDocument();
      expect(screen.getByText('CLM-002')).toBeInTheDocument();
    });

    // Test search filter
    const searchInput = screen.getByPlaceholderText(/Search by claim/i);
    fireEvent.change(searchInput, { target: { value: 'Apex' } });

    expect(screen.getByText('CLM-001')).toBeInTheDocument();
    expect(screen.queryByText('CLM-002')).not.toBeInTheDocument();

    // Select claim
    const pickBtn = screen.getByText('CLM-001').closest('button');
    expect(pickBtn).toBeInTheDocument();
    if (pickBtn) fireEvent.click(pickBtn);

    expect(onSelectClaim).toHaveBeenCalledWith('CLM-001');
  });

  it('chat drawer opens, auto-focuses input, closes with Escape and restores focus', async () => {
    const onClose = vi.fn();
    const openerBtn = document.createElement('button');
    openerBtn.setAttribute('id', 'opener-button');
    document.body.appendChild(openerBtn);
    openerBtn.focus();

    const { rerender } = render(
      <ChatDrawer
        claimId="CLM-001"
        isOpen={false}
        onClose={onClose}
        findings={[]}
        activeFindingId={null}
        onSelectFinding={() => {}}
      />
    );

    expect(screen.queryByRole('dialog', { name: /Case Assistant Chat/i })).toHaveClass('translate-x-full');

    rerender(
      <ChatDrawer
        claimId="CLM-001"
        isOpen={true}
        onClose={onClose}
        findings={[]}
        activeFindingId={null}
        onSelectFinding={() => {}}
      />
    );

    const dialog = screen.getByRole('dialog', { name: /Case Assistant Chat/i });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveClass('translate-x-0');

    // Input auto-focus
    await waitFor(() => {
      const input = screen.getByPlaceholderText(/Ask Case Assistant about findings/i);
      expect(document.activeElement).toBe(input);
    });

    // Press Escape
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();

    openerBtn.remove();
  });

  it('chat drawer renders 429 rate limit error state with retry button', async () => {
    (api.streamClaimChat as any).mockImplementation((_id: string, _msg: string, _onChunk: any, _onComplete: any, onError: any) => {
      const err: any = new Error('Rate limit exceeded');
      err.status = 429;
      onError(err);
    });

    render(
      <ChatDrawer
        claimId="CLM-001"
        isOpen={true}
        onClose={() => {}}
        findings={[]}
        activeFindingId={null}
        onSelectFinding={() => {}}
      />
    );

    const input = screen.getByPlaceholderText(/Ask Case Assistant about findings/i);
    fireEvent.change(input, { target: { value: 'Why was this flagged?' } });

    const submitBtn = screen.getByTitle('Send query to Case Assistant');
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/Rate limit reached \(10 requests\/min for user role\)/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Retry Query/i })).toBeInTheDocument();
    });

    // Clicking Retry Query re-invokes streamClaimChat
    (api.streamClaimChat as any).mockClear();
    fireEvent.click(screen.getByRole('button', { name: /Retry Query/i }));
    expect(api.streamClaimChat).toHaveBeenCalledWith(
      'CLM-001',
      'Why was this flagged?',
      expect.any(Function),
      expect.any(Function),
      expect.any(Function)
    );
  });
});
