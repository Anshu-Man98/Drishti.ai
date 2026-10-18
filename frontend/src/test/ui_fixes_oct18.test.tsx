import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { UploadClaim } from '../pages/UploadClaim';
import { SparklineRow } from '../components/ui/SparklineRow';
import { ChatDrawer } from '../components/ChatDrawer';

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    uploadClaim: vi.fn(),
    fetchChatHistory: vi.fn().mockResolvedValue([]),
    streamClaimChat: vi.fn(),
  };
});

describe('UI Updates: Upload Presets, SparklineRow trend n/a, ChatDrawer backdrop', () => {
  describe('UploadClaim page', () => {
    it('does NOT render Quick Benchmark Presets or preset buttons', () => {
      render(
        <MemoryRouter>
          <UploadClaim />
        </MemoryRouter>
      );

      // Verify the preset section is absent
      expect(screen.queryByText(/Quick Benchmark Presets/i)).toBeNull();
      expect(screen.queryByText(/Golden Benchmark Claims/i)).toBeNull();
      expect(screen.queryByText(/G1: Clean Claim/i)).toBeNull();
      expect(screen.queryByText(/G2: Arithmetic Mismatch/i)).toBeNull();

      // Verify direct file upload and metadata inputs are present
      expect(screen.getByText(/Hospital Invoice PDF \/ Bill Document/i)).toBeInTheDocument();
      expect(screen.getByText(/Select or drag hospital invoice PDF here/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Policy ID/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Claimant Full Name/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Submit Claim for Multi-Agent Scrutiny/i })).toBeInTheDocument();
    });
  });

  describe('SparklineRow component', () => {
    it('does not render trend n/a text when data is empty or insufficient', () => {
      const { container } = render(
        <SparklineRow
          label="Forged Invoice"
          valueText="45%"
          data={[]}
        />
      );

      expect(screen.getByText('Forged Invoice')).toBeInTheDocument();
      expect(screen.getByText('45%')).toBeInTheDocument();
      expect(screen.queryByText(/trend n\/a/i)).toBeNull();
      expect(container.textContent).not.toContain('trend n/a');
    });
  });

  describe('ChatDrawer backdrop & scroll lock', () => {
    beforeEach(() => {
      document.body.style.overflow = '';
    });

    afterEach(() => {
      document.body.style.overflow = '';
    });

    it('portals to document.body, locks scroll, and renders full-screen backdrop', async () => {
      await act(async () => {
        render(
          <ChatDrawer
            claimId="CLM-101"
            isOpen={true}
            onClose={vi.fn()}
            findings={[]}
            activeFindingId={null}
            onSelectFinding={vi.fn()}
          />
        );
      });

      // Assert body scroll lock
      expect(document.body.style.overflow).toBe('hidden');

      // Assert dialog is rendered
      const dialog = screen.getByRole('dialog', { name: /case assistant chat/i });
      expect(dialog).toBeInTheDocument();
      expect(document.body.contains(dialog)).toBe(true);

      // Assert backdrop exists in document.body and has full-screen coverage
      const backdrop = document.querySelector('.bg-black\\/70');
      expect(backdrop).toBeInTheDocument();
      expect(backdrop?.classList.contains('fixed')).toBe(true);
      expect(backdrop?.classList.contains('inset-0')).toBe(true);
      expect(backdrop?.classList.contains('backdrop-blur-sm')).toBe(true);
    });
  });
});
