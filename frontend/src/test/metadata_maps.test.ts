import { describe, it, expect } from 'vitest';
import {
  AGENT_METADATA,
  formatAgentName,
  FRAUD_TYPE_MAP,
  formatFraudType,
} from '../utils/formatters';

describe('Specialist Agent Metadata & Label Maps', () => {
  it('includes all 8 specialist agents in the metadata dictionary', () => {
    const requiredAgents = [
      'forensics',
      'policy',
      'crossref',
      'spacetime',
      'ml',
      'injection',
      'provenance',
      'rag',
    ];

    for (const key of requiredAgents) {
      expect(AGENT_METADATA[key]).toBeDefined();
      expect(AGENT_METADATA[key].label.length).toBeGreaterThan(0);
      expect(AGENT_METADATA[key].description.length).toBeGreaterThan(0);
    }
  });

  it('guarantees "rag" maps strictly to "Pattern retrieval" (A4 Requirement)', () => {
    expect(AGENT_METADATA['rag'].label).toBe('Pattern retrieval');
    expect(formatAgentName('rag')).toBe('Pattern retrieval');
    expect(formatAgentName('RAG')).toBe('Pattern retrieval');
  });

  it('returns formatted agent labels with case and whitespace resilience', () => {
    expect(formatAgentName('  forensics  ')).toBe('Forensics');
    expect(formatAgentName('SPACETIME')).toBe('Spacetime');
    expect(formatAgentName('ml')).toBe('BQ ML');
    expect(formatAgentName('injection')).toBe('Prompt Shield');
    expect(formatAgentName('unknown_agent')).toBe('unknown_agent');
    expect(formatAgentName(null)).toBe('Specialist');
  });
});

describe('Fraud Typology Maps & Formatters', () => {
  it('contains expected core fraud classification keys in FRAUD_TYPE_MAP', () => {
    expect(Object.keys(FRAUD_TYPE_MAP).length).toBeGreaterThanOrEqual(10);
    expect(FRAUD_TYPE_MAP['SHARED_BANK_ACCOUNT']).toBe('Shared Bank Account Ring');
  });

  it('correctly maps known fraud check IDs to readable descriptions', () => {
    expect(formatFraudType('LINE_ITEM_ARITHMETIC_TOTAL')).toBe('Arithmetic Discrepancy');
    expect(formatFraudType('GEOGRAPHIC_IMPOSSIBILITY_VELOCITY')).toBe('Impossible Spacetime Velocity');
    expect(formatFraudType('UNBUNDLED_OR_PADDED_ANCILLARY')).toBe('Padded / Unbundled Ancillary Services');
    expect(formatFraudType('SHARED_BANK_ACCOUNT')).toBe('Shared Bank Account Ring');
    expect(formatFraudType('DISCHARGE_DATE_BEFORE_ADMISSION')).toBe('Inverted Admission Timeline');
    expect(formatFraudType('PROMPT_INJECTION_DETECTED')).toBe('Adversarial Prompt Injection');
    expect(formatFraudType('BENCHMARK_EXCEEDED')).toBe('Diagnosis Price Benchmark Breach');
  });

  it('provides a clean Title Case fallback for unseen check IDs', () => {
    expect(formatFraudType('SUSPICIOUS_PHARMACY_SURCHARGE')).toBe('Suspicious Pharmacy Surcharge');
    expect(formatFraudType(null)).toBe('Unclassified Anomaly');
  });
});
