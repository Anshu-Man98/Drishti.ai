import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '../context/ThemeContext';
import { AppShell } from '../components/layout/AppShell';

describe('Stage 3: AppShell & Nexa Layout Suite', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  const renderShell = (children: React.ReactNode = <div>Test Dashboard Page</div>) => {
    return render(
      <ThemeProvider>
        <BrowserRouter>
          <AppShell>{children}</AppShell>
        </BrowserRouter>
      </ThemeProvider>
    );
  };

  it('renders AppShell with navigation links, brand logo, and content', () => {
    renderShell();

    // Brand
    expect(screen.getAllByText('Drishti').length).toBeGreaterThan(0);

    // Nav items
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Claims Queue')).toBeInTheDocument();
    expect(screen.getByText('Fraud Network')).toBeInTheDocument();
    expect(screen.getByText('Upload Claim')).toBeInTheDocument();
    expect(screen.getByText('Duel Arena')).toBeInTheDocument();

    // Children
    expect(screen.getByText('Test Dashboard Page')).toBeInTheDocument();
  });

  it('renders status card at bottom of sidebar and opens ScoringModal', async () => {
    renderShell();

    const scoringBtn = screen.getByRole('button', { name: /How scoring works/i });
    expect(scoringBtn).toBeInTheDocument();

    // Click to open modal
    fireEvent.click(scoringBtn);

    await waitFor(() => {
      expect(screen.getByText('How Drishti Scoring Works')).toBeInTheDocument();
      expect(screen.getByText(/0.6 × Agent Score \+ 40 × ML Probability/i)).toBeInTheDocument();
    });

    // Close modal
    const closeBtn = screen.getByRole('button', { name: /Close scoring guide modal/i });
    fireEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByText('How Drishti Scoring Works')).not.toBeInTheDocument();
    });
  });

  it('renders segmented sun/moon theme pill toggle in TopBar and toggles theme', () => {
    renderShell();

    const lightRadio = screen.getByRole('radio', { name: /Light Theme/i });
    const darkRadio = screen.getByRole('radio', { name: /Dark Theme/i });

    expect(lightRadio).toBeInTheDocument();
    expect(darkRadio).toBeInTheDocument();

    // Initial is dark
    expect(darkRadio).toHaveAttribute('aria-checked', 'true');

    // Click light mode
    fireEvent.click(lightRadio);
    expect(lightRadio).toHaveAttribute('aria-checked', 'true');
    expect(darkRadio).toHaveAttribute('aria-checked', 'false');

    // Click back to dark mode
    fireEvent.click(darkRadio);
    expect(darkRadio).toHaveAttribute('aria-checked', 'true');
  });

  it('toggles sidebar collapse state on desktop button click', () => {
    renderShell();

    const collapseBtn = screen.getByRole('button', { name: /Collapse sidebar/i });
    expect(collapseBtn).toBeInTheDocument();

    fireEvent.click(collapseBtn);
    expect(localStorage.getItem('finshield-sidebar-collapsed')).toBe('true');

    const expandBtn = screen.getByRole('button', { name: /Expand sidebar/i });
    expect(expandBtn).toBeInTheDocument();

    fireEvent.click(expandBtn);
    expect(localStorage.getItem('finshield-sidebar-collapsed')).toBe('false');
  });
});
