import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';
import { ThemeProvider, useTheme } from '../context/ThemeContext';

describe('Stage 1: Design Tokens & Theme Context', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.className = '';
    document.documentElement.removeAttribute('data-theme');
  });

  it('defaults to dark theme with data-theme="dark" and .dark class', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      React.createElement(ThemeProvider, null, children)
    );

    const { result } = renderHook(() => useTheme(), { wrapper });

    expect(result.current.theme).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('toggles cleanly between dark and light themes and persists in localStorage', () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      React.createElement(ThemeProvider, null, children)
    );

    const { result } = renderHook(() => useTheme(), { wrapper });

    act(() => {
      result.current.toggleTheme();
    });

    expect(result.current.theme).toBe('light');
    expect(document.documentElement.classList.contains('light')).toBe(true);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('finshield-theme')).toBe('light');

    act(() => {
      result.current.toggleTheme();
    });

    expect(result.current.theme).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem('finshield-theme')).toBe('dark');
  });

  it('validates WCAG AA contrast for text and amber brand tokens', () => {
    // Helper function to calculate relative luminance
    const luminance = (hex: string) => {
      const cleanHex = hex.replace('#', '');
      const rgb = [
        parseInt(cleanHex.substring(0, 2), 16) / 255,
        parseInt(cleanHex.substring(2, 4), 16) / 255,
        parseInt(cleanHex.substring(4, 6), 16) / 255,
      ].map((val) =>
        val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4)
      );
      return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
    };

    const contrast = (hex1: string, hex2: string) => {
      const lum1 = luminance(hex1);
      const lum2 = luminance(hex2);
      const brightest = Math.max(lum1, lum2);
      const darkest = Math.min(lum1, lum2);
      return (brightest + 0.05) / (darkest + 0.05);
    };

    // Dark theme tests against near-black (#060605)
    const darkBg = '#060605';
    const darkTextPrimary = '#F3EFE6';
    const darkTextMuted = '#8F8A7E';
    const darkAmber = '#F5A524';

    expect(contrast(darkTextPrimary, darkBg)).toBeGreaterThan(7.0); // Passes AAA (> 7.0)
    expect(contrast(darkTextMuted, darkBg)).toBeGreaterThan(4.5); // Passes AA (> 4.5)
    expect(contrast(darkAmber, darkBg)).toBeGreaterThan(4.5); // Amber on black passes AA

    // Light theme tests against warm paper (#FAF7F0)
    const lightBg = '#FAF7F0';
    const lightTextPrimary = '#1C1A16';
    const lightTextMuted = '#736C5E';
    const lightAmberText = '#9A5B0B';
    const lightAmberControl = '#B7791F';

    expect(contrast(lightTextPrimary, lightBg)).toBeGreaterThan(7.0); // Passes AAA (> 7.0)
    expect(contrast(lightTextMuted, lightBg)).toBeGreaterThan(4.5); // Passes AA (> 4.5)
    expect(contrast(lightAmberText, lightBg)).toBeGreaterThan(4.5); // Text amber passes AA (> 4.5)
    expect(contrast(lightAmberControl, lightBg)).toBeGreaterThan(3.0); // UI control amber passes WCAG AA Non-text (> 3.0)
  });
});
