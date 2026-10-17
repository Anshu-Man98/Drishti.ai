import { describe, it, expect } from 'vitest';
import {
  formatDiagnosis,
  formatInsurer,
  formatPolicy,
  formatIndianCurrency,
  formatIndianNumber,
  formatClaimRef,
  formatAgentName,
} from '../utils/formatters';

describe('ICD-10 Clinical Terminology Formatter', () => {
  it('formats exact matches correctly', () => {
    const res = formatDiagnosis('A09');
    expect(res.code).toBe('A09');
    expect(res.label).toBe('Infectious Gastroenteritis & Colitis');
    expect(res.full).toBe('Infectious Gastroenteritis & Colitis (A09)');
  });

  it('covers all app codes identified in QA pass', () => {
    const requiredCodes = ['K35.8', 'K80.2', 'I20.9', 'S82.8', 'M54.5', 'A09', 'N39.0', 'E11.9', 'J18.9', 'K80.0', 'S82.2'];
    for (const code of requiredCodes) {
      const res = formatDiagnosis(code);
      expect(res.label).not.toBe('description not in reference table');
      expect(res.label.length).toBeGreaterThan(0);
      expect(res.code).toBe(code);
    }
  });

  it('normalizes trailing zeros (e.g. K35.8 vs K35.80, M54.5 vs M54.50)', () => {
    const res1 = formatDiagnosis('K35.80');
    expect(res1.label).toMatch(/Acute Appendicitis/i);

    const res2 = formatDiagnosis('M54.5');
    expect(res2.label).toMatch(/Low Back Pain/i);
  });

  it('normalizes whitespace and case', () => {
    const res = formatDiagnosis('  k35.8  ');
    expect(res.code).toBe('K35.8');
    expect(res.label).toBe('Acute Appendicitis, Other & Unspecified');
  });

  it('falls back to parent 3-character block for unknown sub-codes', () => {
    // K35 is Acute Appendicitis. K35.999 is not in table, should fall back to K35 parent
    const res = formatDiagnosis('K35.999');
    expect(res.code).toBe('K35.999');
    expect(res.label).toBe('Acute Appendicitis');
    expect(res.full).toBe('Acute Appendicitis (K35.999)');
  });

  it('strictly adheres to: never show the code twice for unknown codes', () => {
    const unknownCode = 'Z99.999';
    const res = formatDiagnosis(unknownCode);
    expect(res.code).toBe('Z99.999');
    expect(res.label).toBe('description not in reference table');
    // Must never render "Z99.999 Z99.999"
    expect(res.label).not.toContain(unknownCode);
    expect(res.full).toBe('Z99.999 (description not in reference table)');
  });

  it('handles null, undefined, and empty string safely', () => {
    expect(formatDiagnosis(null).label).toBe('Not Specified');
    expect(formatDiagnosis(undefined).label).toBe('Not Specified');
    expect(formatDiagnosis('').label).toBe('Not Specified');
  });
});

describe('Insurer and Policy Formatting', () => {
  it('maps all distinct data insurers to full corporate names', () => {
    const requiredInsurers = ['INS-NIVA', 'INS-FINSHIELD', 'INS-CARE', 'INS-HDFC', 'INS-ICICI', 'INS-STAR', 'INS-MAX'];
    for (const id of requiredInsurers) {
      const res = formatInsurer(id);
      expect(res.name).not.toBe(id);
      expect(res.short).not.toBe(id);
      expect(res.id).toBe(id);
    }
  });

  it('correctly maps INS-NIVA to Niva Bupa Health Insurance', () => {
    const res = formatInsurer('INS-NIVA');
    expect(res.name).toBe('Niva Bupa Health Insurance');
    expect(res.short).toBe('Niva Bupa');
  });

  it('correctly maps INS-FINSHIELD to internal underwriting display', () => {
    const res = formatInsurer('INS-FINSHIELD');
    expect(res.name).toBe('FinShield Underwriting (Internal)');
    expect(res.short).toBe('FinShield');
  });

  it('maps known policy prefixes to readable plan titles', () => {
    expect(formatPolicy('POL-AROGYA-88124').name).toBe('Arogya Sanjeevani Plan');
    expect(formatPolicy('POL-CARE-99812').name).toBe('Care Comprehensive Health Plan');
    expect(formatPolicy('POL-OPTIMA-RESTORE-101').name).toBe('Optima Secure & Restore');
    expect(formatPolicy('POL-STAR-COMPREHENSIVE-402').name).toBe('Star Comprehensive Health');
  });

  it('handles unassigned insurer or null policy safely', () => {
    expect(formatInsurer(null).name).toBe('Unassigned Insurer');
    expect(formatPolicy(null).name).toBe('Unspecified Policy');
  });
});

describe('Currency and Agent Formatting', () => {
  it('formats Indian rupees properly with symbol and separators', () => {
    const formatted = formatIndianCurrency(112500);
    // Non-breaking space or standard space before or after ₹
    expect(formatted).toMatch(/₹\s?1,12,500/);
    expect(formatIndianCurrency(0)).toMatch(/₹\s?0/);
    expect(formatIndianCurrency(null)).toBe('₹0');
  });

  it('maps rag agent key to Pattern retrieval', () => {
    expect(formatAgentName('rag')).toBe('Pattern retrieval');
    expect(formatAgentName('RAG')).toBe('Pattern retrieval');
    expect(formatAgentName('  rag  ')).toBe('Pattern retrieval');
  });

  it('maps all specialist agent keys to proper titles', () => {
    expect(formatAgentName('forensics')).toBe('Forensics');
    expect(formatAgentName('policy')).toBe('Policy Engine');
    expect(formatAgentName('crossref')).toBe('Cross-Insurer');
    expect(formatAgentName('spacetime')).toBe('Spacetime');
    expect(formatAgentName('ml')).toBe('BQ ML');
    expect(formatAgentName('injection')).toBe('Prompt Shield');
    expect(formatAgentName('provenance')).toBe('Provenance');
  });

  describe('formatIndianNumber', () => {
    it('formats numbers with Indian digit grouping (lakh and crore boundaries)', () => {
      expect(formatIndianNumber(1000)).toBe('1,000');
      expect(formatIndianNumber(100000)).toBe('1,00,000');
      expect(formatIndianNumber(1295940)).toBe('12,95,940');
      expect(formatIndianNumber(10292124)).toBe('1,02,92,124');
    });

    it('handles zero, negative, null, and NaN gracefully', () => {
      expect(formatIndianNumber(0)).toBe('0');
      expect(formatIndianNumber(null)).toBe('0');
      expect(formatIndianNumber(undefined)).toBe('0');
      expect(formatIndianNumber(NaN)).toBe('0');
    });

    it('respects decimal places argument', () => {
      expect(formatIndianNumber(123456.789, 2)).toBe('1,23,456.79');
      expect(formatIndianNumber(1000.5, 0)).toBe('1,001');
    });
  });

  describe('formatClaimRef', () => {
    it('extracts readable suffix in short mode', () => {
      expect(formatClaimRef('CLM-2024-G582')).toBe('Claim #G582');
      expect(formatClaimRef('CLM-2024-99812')).toBe('Claim #99812');
    });

    it('truncates raw long ids without dashes', () => {
      expect(formatClaimRef('08341982')).toBe('Claim #1982');
    });

    it('supports full mode', () => {
      expect(formatClaimRef('CLM-2024-G582', 'full')).toBe('CLM-2024-G582');
    });

    it('handles null and undefined safely', () => {
      expect(formatClaimRef(null)).toBe('Claim #—');
      expect(formatClaimRef(undefined)).toBe('Claim #—');
      expect(formatClaimRef('')).toBe('Claim #—');
    });
  });
});
