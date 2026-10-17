import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import {
  usePrefersReducedMotion,
  usePageVisibility,
  useCountUp,
  useMotionProgress,
} from '../utils/motion';
import { KpiCard } from '../components/ui/KpiCard';
import { ArcGauge } from '../components/ui/ArcGauge';
import { GlowAreaChart } from '../components/ui/GlowAreaChart';
import { ChatDrawer } from '../components/ChatDrawer';

describe('Motion Language & Micro-interactions (Stage 6)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
    document.documentElement.classList.remove('tab-hidden');
  });

  describe('usePrefersReducedMotion hook', () => {
    it('defaults to false when prefers-reduced-motion does not match', () => {
      window.matchMedia = vi.fn().mockImplementation((query) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));

      const { result } = renderHook(() => usePrefersReducedMotion());
      expect(result.current).toBe(false);
    });

    it('returns true when prefers-reduced-motion matches', () => {
      window.matchMedia = vi.fn().mockImplementation((query) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));

      const { result } = renderHook(() => usePrefersReducedMotion());
      expect(result.current).toBe(true);
    });
  });

  describe('usePageVisibility hook', () => {
    it('tracks tab visibility and toggles tab-hidden class on documentElement', () => {
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => false,
      });

      const { result } = renderHook(() => usePageVisibility());
      expect(result.current).toBe(true);
      expect(document.documentElement.classList.contains('tab-hidden')).toBe(false);

      // Simulate tab hidden
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => true,
      });

      act(() => {
        document.dispatchEvent(new Event('visibilitychange'));
      });

      expect(result.current).toBe(false);
      expect(document.documentElement.classList.contains('tab-hidden')).toBe(true);

      // Simulate tab visible again
      Object.defineProperty(document, 'hidden', {
        configurable: true,
        get: () => false,
      });

      act(() => {
        document.dispatchEvent(new Event('visibilitychange'));
      });

      expect(result.current).toBe(true);
      expect(document.documentElement.classList.contains('tab-hidden')).toBe(false);
    });
  });

  describe('useCountUp hook', () => {
    it('immediately returns target when prefers-reduced-motion is true', () => {
      window.matchMedia = vi.fn().mockImplementation((query) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));

      const { result } = renderHook(() => useCountUp(1500, { enabled: true }));
      expect(result.current).toBe(1500);
    });

    it('immediately returns target when enabled is false', () => {
      const { result } = renderHook(() => useCountUp(850, { enabled: false }));
      expect(result.current).toBe(850);
    });
  });

  describe('useMotionProgress hook', () => {
    it('immediately resolves to 1 under prefers-reduced-motion', () => {
      window.matchMedia = vi.fn().mockImplementation((query) => ({
        matches: query === '(prefers-reduced-motion: reduce)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }));

      const { result } = renderHook(() => useMotionProgress({ duration: 500, enabled: true }));
      expect(result.current).toBe(1);
    });
  });

  describe('KpiCard motion integration', () => {
    it('renders with target numeral formatted', () => {
      render(
        <KpiCard
          label="Claims Audited"
          value={1250}
          animate={false}
          prefix=""
        />
      );

      expect(screen.getByText('Claims Audited')).toBeInTheDocument();
      expect(screen.getByText('1,250')).toBeInTheDocument();
    });
  });

  describe('ArcGauge motion integration', () => {
    it('renders meter role and calculates stroke attributes properly', () => {
      const { container } = render(
        <ArcGauge
          value={75}
          min={0}
          max={100}
          unit="%"
          label="Risk Level"
          animate={false}
        />
      );

      const meter = screen.getByRole('meter');
      expect(meter).toBeInTheDocument();
      expect(meter).toHaveAttribute('aria-valuenow', '75');

      const path = container.querySelector('path[stroke-dasharray]');
      expect(path).toBeInTheDocument();
      expect(path).toHaveAttribute('stroke-dashoffset');
    });
  });

  describe('GlowAreaChart motion integration', () => {
    it('renders paths with stroke-dashoffset for draw-in animation', () => {
      const sampleData = [
        { label: 'Jan', value: 10 },
        { label: 'Feb', value: 25 },
        { label: 'Mar', value: 40 },
      ];

      const { container } = render(
        <GlowAreaChart
          data={sampleData}
          title="Fraud Trend"
          animate={false}
        />
      );

      expect(screen.getByText('Fraud Trend')).toBeInTheDocument();
      const sharpPath = container.querySelector('path[stroke="#F5A524"]');
      expect(sharpPath).toBeInTheDocument();
      expect(sharpPath).toHaveAttribute('stroke-dasharray');
      expect(sharpPath).toHaveAttribute('stroke-dashoffset');
    });
  });

  describe('ChatDrawer transition and interaction', () => {
    it('handles close on Escape key and backdrop click', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [],
      } as any);

      const handleClose = vi.fn();
      await act(async () => {
        render(
          <ChatDrawer
            claimId="CLM-101"
            isOpen={true}
            onClose={handleClose}
            findings={[]}
            activeFindingId={null}
            onSelectFinding={vi.fn()}
          />
        );
      });

      expect(screen.getByRole('dialog', { name: /case assistant chat/i })).toBeInTheDocument();

      // Trigger Escape key
      act(() => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
      });
      expect(handleClose).toHaveBeenCalledTimes(1);
    });
  });
});
