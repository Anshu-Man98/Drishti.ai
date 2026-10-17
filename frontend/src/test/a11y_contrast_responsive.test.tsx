import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Badge } from '../components/ui/Badge';
import { TopBar } from '../components/layout/TopBar';
import { ThemeProvider } from '../context/ThemeContext';

/**
 * Standard relative luminance according to WCAG 2.1 formula
 */
function sRGBtoLinear(c: number): number {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function calculateLuminance(hex: string): number {
  const cleanHex = hex.replace('#', '');
  const r = parseInt(cleanHex.slice(0, 2), 16) / 255;
  const g = parseInt(cleanHex.slice(2, 4), 16) / 255;
  const b = parseInt(cleanHex.slice(4, 6), 16) / 255;
  return 0.2126 * sRGBtoLinear(r) + 0.7152 * sRGBtoLinear(g) + 0.0722 * sRGBtoLinear(b);
}

function calculateContrast(hex1: string, hex2: string): number {
  const l1 = calculateLuminance(hex1);
  const l2 = calculateLuminance(hex2);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

describe('Stage 7: Contrast, Accessibility & Responsive Polish', () => {
  describe('WCAG 2.1 Contrast Ratio Verification', () => {
    const darkBase = '#060605';
    const darkSurface = '#131312';
    const lightPaper = '#FAF7F0';

    it('verifies Dark Theme text and brand colors exceed WCAG AA (>= 4.5:1)', () => {
      // Primary Text
      const textPrimaryContrast = calculateContrast('#F3EFE6', darkBase);
      expect(textPrimaryContrast).toBeGreaterThanOrEqual(7.0); // Exceeds AAA

      // Muted Text
      const textMutedContrast = calculateContrast('#8F8A7E', darkBase);
      expect(textMutedContrast).toBeGreaterThanOrEqual(4.5); // Passes AA

      // Brand Amber Primary
      const brandAmberContrast = calculateContrast('#F5A524', darkBase);
      expect(brandAmberContrast).toBeGreaterThanOrEqual(4.5); // Passes AA (approx 9.9:1)

      // Brand Bright Amber
      const brandBrightContrast = calculateContrast('#FFC15A', darkBase);
      expect(brandBrightContrast).toBeGreaterThanOrEqual(7.0); // Exceeds AAA

      // Semantic Emerald Approve
      const approveContrast = calculateContrast('#10B981', darkBase);
      expect(approveContrast).toBeGreaterThanOrEqual(4.5); // Passes AA (approx 8:1)

      // Semantic Crimson Reject
      const rejectContrast = calculateContrast('#F43F5E', darkBase);
      expect(rejectContrast).toBeGreaterThanOrEqual(4.5); // Passes AA (approx 5.5:1)

      // Contrast against elevated surface #131312
      const surfaceAmberContrast = calculateContrast('#F5A524', darkSurface);
      expect(surfaceAmberContrast).toBeGreaterThanOrEqual(4.5);
    });

    it('verifies Light Theme warm paper palette exceeds WCAG AA (>= 4.5:1)', () => {
      // Primary Ink Text
      const inkContrast = calculateContrast('#1C1A16', lightPaper);
      expect(inkContrast).toBeGreaterThanOrEqual(7.0); // Exceeds AAA (approx 16:1)

      // Muted Secondary Text
      const mutedInkContrast = calculateContrast('#736C5E', lightPaper);
      expect(mutedInkContrast).toBeGreaterThanOrEqual(4.5); // Passes AA

      // Deeper Amber Brand Primary for Paper
      const paperAmberContrast = calculateContrast('#9A5B0B', lightPaper);
      expect(paperAmberContrast).toBeGreaterThanOrEqual(4.5); // Passes AA (approx 5.1:1)

      // Light Theme Semantic Emerald
      const lightApproveContrast = calculateContrast('#047857', lightPaper);
      expect(lightApproveContrast).toBeGreaterThanOrEqual(4.5); // Passes AA (approx 5.1:1)

      // Light Theme Semantic Crimson
      const lightRejectContrast = calculateContrast('#BE123C', lightPaper);
      expect(lightRejectContrast).toBeGreaterThanOrEqual(4.5); // Passes AA (approx 5.8:1)
    });
  });

  describe('Color-blind Safety on Verdict & Severity Badges', () => {
    it('always pairs color with an icon AND a descriptive text label for Approve', () => {
      const { container } = render(<Badge variant="approve" />);
      expect(screen.getByText('Approve')).toBeInTheDocument();
      // SVG icon must be rendered inside the badge
      const svgIcon = container.querySelector('svg');
      expect(svgIcon).toBeInTheDocument();
    });

    it('always pairs color with an icon AND explicit "Review" text label', () => {
      const { container } = render(<Badge variant="review" label="Requires Senior Audit" />);
      // Must contain "Review" in label for color-blind safety
      expect(screen.getByText(/Review/i)).toBeInTheDocument();
      const svgIcon = container.querySelector('svg');
      expect(svgIcon).toBeInTheDocument();
      // Must have filled tinted pill styling and border
      const pill = container.querySelector('span');
      expect(pill?.className).toContain('rounded-full');
      expect(pill?.className).toContain('border');
    });

    it('always pairs color with an icon AND a descriptive text label for Reject', () => {
      const { container } = render(<Badge variant="reject" />);
      expect(screen.getByText('Reject')).toBeInTheDocument();
      const svgIcon = container.querySelector('svg');
      expect(svgIcon).toBeInTheDocument();
    });

    it('always pairs color with an icon AND text for Critical finding severity', () => {
      const { container } = render(<Badge variant="critical" />);
      expect(screen.getByText('Critical')).toBeInTheDocument();
      const svgIcon = container.querySelector('svg');
      expect(svgIcon).toBeInTheDocument();
    });
  });

  describe('Responsive Navigation & Mobile Accessibility (375px & 1440px)', () => {
    it('provides accessible hamburger button with aria-label on mobile', () => {
      render(
        <ThemeProvider>
          <BrowserRouter>
            <TopBar onOpenMobile={() => {}} />
          </BrowserRouter>
        </ThemeProvider>
      );

      const mobileButton = screen.getByRole('button', { name: /open mobile navigation/i });
      expect(mobileButton).toBeInTheDocument();
      expect(mobileButton.className).toContain('lg:hidden');
    });

    it('provides accessible breadcrumb navigation with aria-label', () => {
      render(
        <ThemeProvider>
          <BrowserRouter>
            <TopBar onOpenMobile={() => {}} />
          </BrowserRouter>
        </ThemeProvider>
      );

      const breadcrumbNav = screen.getByRole('navigation', { name: /breadcrumb/i });
      expect(breadcrumbNav).toBeInTheDocument();
    });
  });
});
