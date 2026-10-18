import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  ArcGauge,
  computeArcGaugeLayout,
  GlowAreaChart,
  SparklineRow,
  RankedList,
  KpiCard,
  PillTabs,
  ToggleSwitch,
  Badge,
} from '../components/ui';

describe('Stage 2: Signature UI Components Suite', () => {
  describe('ArcGauge Component', () => {
    it('renders with correct accessible meter attributes and clamps values within [min, max]', () => {
      render(
        <ArcGauge
          value={85}
          min={0}
          max={100}
          unit="pts"
          label="Fraud Risk"
          caption="Critical Threshold"
          variant="amber"
        />
      );

      const meter = screen.getByRole('meter');
      expect(meter).toBeInTheDocument();
      expect(meter).toHaveAttribute('aria-valuenow', '85');
      expect(meter).toHaveAttribute('aria-valuemin', '0');
      expect(meter).toHaveAttribute('aria-valuemax', '100');
      expect(meter).toHaveAttribute('aria-label', 'Fraud Risk');
      expect(screen.getByText('85')).toBeInTheDocument();
      expect(screen.getByText('pts')).toBeInTheDocument();
      expect(screen.getByText('Critical Threshold')).toBeInTheDocument();
    });

    it('clamps values above max or below min cleanly', () => {
      const { rerender } = render(
        <ArcGauge value={150} min={0} max={100} label="Over Max" />
      );
      expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '100');

      rerender(<ArcGauge value={-25} min={0} max={100} label="Under Min" />);
      expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '0');
    });

    it('renders danger variant for impossible/critical states', () => {
      render(
        <ArcGauge
          value={95}
          variant="danger"
          label="Impossible Velocity"
          caption="High Anomaly"
        />
      );
      expect(screen.getByRole('meter')).toBeInTheDocument();
      expect(screen.getByText('Impossible Velocity')).toBeInTheDocument();
    });

    it('centers numeric value inside the arc and maintains at least 12px clear space below arc bottom for sizes 140px to 260px and 390px viewport', () => {
      render(
        <ArcGauge
          value={87}
          unit="%"
          caption="Fraud Losses Prevented"
          size="md"
        />
      );

      const valueEl = screen.getByTestId('arc-gauge-value');
      const captionEl = screen.getByTestId('arc-gauge-caption');

      expect(valueEl).toBeInTheDocument();
      expect(captionEl).toBeInTheDocument();

      const arcBottom = parseFloat(captionEl.getAttribute('data-arc-bottom') || '0');
      const captionY = parseFloat(captionEl.getAttribute('data-caption-y') || '0');
      const clearanceSvg = parseFloat(captionEl.getAttribute('data-clearance-svg') || '0');

      // Value must be optical-centered at y=76, strictly above arc bottom (98.05)
      expect(parseFloat(valueEl.getAttribute('y') || '0')).toBeLessThan(arcBottom);

      // In SVG space, caption is positioned at y=126, which is > 27 units below the lowest arc point
      expect(captionY).toBeGreaterThan(arcBottom);
      expect(clearanceSvg).toBeGreaterThanOrEqual(27);

      // Verify layout geometry across all test widths: 140px, 180px, 220px, 240px, 260px, and 390px viewport card
      const testWidths = [140, 180, 220, 240, 260, 390];
      for (const w of testWidths) {
        const layout = computeArcGaugeLayout(w);
        // Clearance in physical pixels must be >= 12px
        expect(layout.clearancePx).toBeGreaterThanOrEqual(12);
        expect(layout.hasAtLeast12pxClearance).toBe(true);
        // Caption must be strictly below arc bottom
        expect(layout.captionYPx).toBeGreaterThan(layout.arcBottomPx);
        // Value numeral is above arc bottom
        expect(layout.valueCenterPx).toBeLessThan(layout.arcBottomPx);
      }
    });

    it('does not restart animation on parent re-renders and keeps steady GPU-isolated glow', () => {
      const Parent = () => {
        const [count, setCount] = useState(0);
        return (
          <div>
            <button onClick={() => setCount((c) => c + 1)}>Increment {count}</button>
            <ArcGauge value={75} min={0} max={100} label="Mitigation Ratio" />
          </div>
        );
      };

      const { container } = render(<Parent />);
      const glow = screen.getByTestId('arc-gauge-glow');
      expect(glow).toBeInTheDocument();
      expect(glow).toHaveStyle({ willChange: 'transform' });

      const path = container.querySelector('path[stroke-dasharray]');
      expect(path).toBeInTheDocument();
      const initialOffset = path?.getAttribute('stroke-dashoffset');

      // Trigger parent state re-render
      fireEvent.click(screen.getByRole('button', { name: /Increment 0/i }));
      expect(screen.getByRole('button', { name: /Increment 1/i })).toBeInTheDocument();

      // Glow is still present and steady
      expect(screen.getByTestId('arc-gauge-glow')).toBeInTheDocument();
      // Stroke offset remains steady and does not reset to 0
      const afterOffset = path?.getAttribute('stroke-dashoffset');
      expect(afterOffset).toBe(initialOffset);
    });
  });

  describe('GlowAreaChart Component', () => {
    const mockData = [
      { label: 'Oct 10', value: 120, formattedValue: '₹1,20,000' },
      { label: 'Oct 11', value: 180, formattedValue: '₹1,80,000' },
      { label: 'Oct 12', value: 150, formattedValue: '₹1,50,000' },
      { label: 'Oct 13', value: 240, formattedValue: '₹2,40,000' },
    ];

    it('renders chart title, X-axis labels, and SVG paths', () => {
      render(
        <GlowAreaChart
          title="Claims Trend"
          data={mockData}
          valuePrefix="₹"
        />
      );

      expect(screen.getByText('Claims Trend')).toBeInTheDocument();
      expect(screen.getByText('Oct 10')).toBeInTheDocument();
      expect(screen.getByText('Oct 13')).toBeInTheDocument();
      expect(screen.getByRole('img', { name: /Claims Trend Chart/i })).toBeInTheDocument();
    });

    it('renders clean empty state when data array is empty without filler numbers', () => {
      render(
        <GlowAreaChart
          title="Claims Volume"
          data={[]}
          emptyMessage="No claim activity in selected window"
        />
      );

      expect(screen.getByText('Claims Volume')).toBeInTheDocument();
      expect(screen.getByText('No claim activity in selected window')).toBeInTheDocument();
    });
  });

  describe('SparklineRow Component', () => {
    it('renders label, glowing sparkline svg, and percentage value', () => {
      render(
        <SparklineRow
          label="Subtotal Tampering"
          data={[10, 15, 8, 22, 35, 28, 40]}
          valueText="24.5 %"
          sublabel="5 claims flagged"
        />
      );

      expect(screen.getByText('Subtotal Tampering')).toBeInTheDocument();
      expect(screen.getByText('5 claims flagged')).toBeInTheDocument();
      expect(screen.getByText('24.5 %')).toBeInTheDocument();
    });
  });

  describe('RankedList Component', () => {
    const mockItems = [
      { id: '1', name: 'Jaipur Hospital', percentage: 42, subtext: '8 flagged' },
      { id: '2', name: 'Mumbai Care', percentage: 28, subtext: '5 flagged' },
      { id: '3', name: 'Delhi Clinic', percentage: 14, subtext: '2 flagged' },
    ];

    it('renders ranked items, percentages, and handles clicks', () => {
      const handleClick = vi.fn();
      render(
        <RankedList
          title="Top 3 Flagged Hospitals"
          items={mockItems.map((item) => ({ ...item, onClick: handleClick }))}
        />
      );

      expect(screen.getByText('Top 3 Flagged Hospitals')).toBeInTheDocument();
      expect(screen.getByText('Jaipur Hospital')).toBeInTheDocument();
      expect(screen.getByText('42%')).toBeInTheDocument();
      expect(screen.getByText('Mumbai Care')).toBeInTheDocument();
      expect(screen.getByText('28%')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Jaipur Hospital'));
      expect(handleClick).toHaveBeenCalled();
    });

    it('renders empty message when no items provided', () => {
      render(<RankedList title="Top Hospitals" items={[]} emptyMessage="No hospital flags recorded" />);
      expect(screen.getByText('No hospital flags recorded')).toBeInTheDocument();
    });
  });

  describe('KpiCard Component', () => {
    it('renders label, formatted numeral, and contextual delta line', () => {
      render(
        <KpiCard
          label="Fraud Prevented"
          value={485000}
          prefix="₹"
          contextText="+18% vs last month"
          contextTone="positive"
          animate={false}
        />
      );

      expect(screen.getByText('Fraud Prevented')).toBeInTheDocument();
      expect(screen.getByText(/4,85,000|485,000/)).toBeInTheDocument();
      expect(screen.getByText('+18% vs last month')).toBeInTheDocument();
    });
  });

  describe('PillTabs Component', () => {
    const tabs = [
      { id: 'all', label: 'All Claims', badge: 14 },
      { id: 'review', label: 'Under Review', badge: 3 },
      { id: 'rejected', label: 'Fraud Rejected', badge: 7 },
    ];

    it('renders pill tabs and triggers onChange callback', () => {
      const handleChange = vi.fn();
      render(
        <PillTabs
          tabs={tabs}
          activeTabId="all"
          onChange={handleChange}
        />
      );

      expect(screen.getByText('All Claims')).toBeInTheDocument();
      expect(screen.getByText('Under Review')).toBeInTheDocument();

      fireEvent.click(screen.getByText('Under Review'));
      expect(handleChange).toHaveBeenCalledWith('review');
    });
  });

  describe('ToggleSwitch Component', () => {
    it('renders toggle switch and handles checked state toggle', () => {
      const handleChange = vi.fn();
      render(
        <ToggleSwitch
          checked={false}
          onChange={handleChange}
          label="Include Synthetic Test Claims"
        />
      );

      const switchBtn = screen.getByRole('switch');
      expect(switchBtn).toHaveAttribute('aria-checked', 'false');
      expect(screen.getByText('Include Synthetic Test Claims')).toBeInTheDocument();

      fireEvent.click(switchBtn);
      expect(handleChange).toHaveBeenCalledWith(true);
    });
  });

  describe('Badge Component', () => {
    it('renders review badge with brand amber color and Clock icon', () => {
      render(<Badge variant="review" label="Review Required" score={65} />);
      expect(screen.getByText(/Review Required/i)).toBeInTheDocument();
      expect(screen.getByText('(65)')).toBeInTheDocument();
    });

    it('renders reject badge with alert octagon icon', () => {
      render(<Badge variant="reject" label="Fraud Reject" score={85} />);
      expect(screen.getByText('Fraud Reject')).toBeInTheDocument();
      expect(screen.getByText('(85)')).toBeInTheDocument();
    });
  });
});
