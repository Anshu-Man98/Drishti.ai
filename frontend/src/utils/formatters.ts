/**
 * FinShield Formatting and Translation Utilities
 * Provides human-readable translations for ICD-10 codes, insurers, policies,
 * and Indian currency/date formatting for adjuster workflows.
 */

// ICD-10 Clinical Terminology Map
export const ICD10_MAP: Record<string, string> = {
  // Musculoskeletal & Connective
  'M54': 'Dorsalgia (Spinal Pain)',
  'M54.5': 'Low Back Pain (Lumbago)',
  'M54.50': 'Low Back Pain, Unspecified',
  'M54.2': 'Cervicalgia (Neck Pain)',

  // Circulatory & Cardiac
  'I10': 'Essential (Primary) Hypertension',
  'I20': 'Angina Pectoris',
  'I20.9': 'Angina Pectoris, Unspecified',
  'I21.9': 'Acute Myocardial Infarction',
  'I25.10': 'Atherosclerotic Heart Disease',

  // Endocrine & Metabolic
  'E11': 'Type 2 Diabetes Mellitus',
  'E11.9': 'Type 2 Diabetes Without Complications',
  'E11.65': 'Type 2 Diabetes with Hyperglycemia',

  // Respiratory
  'J18': 'Pneumonia',
  'J18.9': 'Pneumonia, Unspecified Organism',
  'J06.9': 'Acute Upper Respiratory Infection',
  'J45.909': 'Unspecified Asthma, Uncomplicated',

  // Digestive
  'K35': 'Acute Appendicitis',
  'K35.8': 'Acute Appendicitis, Other & Unspecified',
  'K35.80': 'Acute Appendicitis',
  'K80': 'Cholelithiasis (Gallstones)',
  'K80.0': 'Calculus of Gallbladder with Acute Cholecystitis',
  'K80.2': 'Calculus of Gallbladder Without Cholecystitis',
  'K80.20': 'Calculus of Gallbladder (Gallstones)',
  'K29.70': 'Gastritis, Unspecified',

  // Infectious
  'A09': 'Infectious Gastroenteritis & Colitis',

  // Genitourinary
  'N39': 'Disorders of Urinary System',
  'N39.0': 'Urinary Tract Infection',
  'N20.0': 'Calculus of Kidney (Kidney Stones)',

  // Injury & Trauma
  'S82': 'Fracture of Lower Leg',
  'S82.2': 'Fracture of Shaft of Tibia',
  'S82.201A': 'Fracture of Right Tibia Shaft',
  'S82.202A': 'Fracture of Left Tibia Shaft',
  'S82.8': 'Fracture of Other Parts of Lower Leg',

  // General / Symptoms / Other
  'Z00.00': 'General Adult Medical Examination',
  'H26.9': 'Unspecified Cataract',
  'R10.9': 'Abdominal Pain, Unspecified',
  'R50.9': 'Fever, Unspecified',
};

// Insurer Entity Map
export const INSURER_MAP: Record<string, { name: string; short: string }> = {
  'INS-HDFC': { name: 'HDFC ERGO General Insurance', short: 'HDFC ERGO' },
  'INS-STAR': { name: 'Star Health & Allied Insurance', short: 'Star Health' },
  'INS-ICICI': { name: 'ICICI Lombard General Insurance', short: 'ICICI Lombard' },
  'INS-MAX': { name: 'Niva Bupa (Max Bupa) Health', short: 'Niva Bupa' },
  'INS-NIVA': { name: 'Niva Bupa Health Insurance', short: 'Niva Bupa' },
  'INS-CARE': { name: 'Care Health Insurance', short: 'Care Health' },
  'INS-FINSHIELD': { name: 'FinShield Underwriting (Internal)', short: 'FinShield' },
  'INS-SBI': { name: 'SBI General Insurance', short: 'SBI General' },
  'INS-BAJAJ': { name: 'Bajaj Allianz General Insurance', short: 'Bajaj Allianz' },
  'INS-TATA': { name: 'Tata AIG General Insurance', short: 'Tata AIG' },
  'INS-REL': { name: 'Reliance General Insurance', short: 'Reliance Gen' },
  'INS-DIGIT': { name: 'Go Digit General Insurance', short: 'Digit' },
  'INS-NIACL': { name: 'New India Assurance Co.', short: 'New India' },
  'INS-UIIC': { name: 'United India Insurance Co.', short: 'United India' },
  'INS-OICL': { name: 'Oriental Insurance Co.', short: 'Oriental' },
  'INS-NICL': { name: 'National Insurance Co.', short: 'National' },
};

// Policy Product Map
export const POLICY_PREFIX_MAP: Record<string, string> = {
  'POL-AROGYA': 'Arogya Sanjeevani Plan',
  'POL-CARE': 'Care Comprehensive Health Plan',
  'POL-OPTIMA': 'Optima Secure & Restore',
  'POL-STAR': 'Star Comprehensive Health',
  'POL-FAMILY': 'Family Health Optima',
  'POL-MEDICLAIM': 'Individual Comprehensive Mediclaim',
  'POL-SUPER': 'Super Top-up Floater',
  'POL-SENIOR': 'Senior Citizens Red Carpet',
  'POL-CRITICAL': 'Critical Illness Protection',
  'POL-CORONA': 'Corona Kavach Plan',
};

// Centralized Specialist Agent Metadata
export const AGENT_METADATA: Record<string, { label: string; description: string }> = {
  forensics: { label: 'Forensics', description: 'Document forgery & tampering inspection' },
  policy: { label: 'Policy Engine', description: 'Adjudication limits & benchmark verification' },
  crossref: { label: 'Cross-Insurer', description: 'Multi-insurer collision & syndicate detection' },
  spacetime: { label: 'Spacetime', description: 'Geographic feasibility & travel physics' },
  ml: { label: 'BQ ML', description: 'BigQuery machine learning fraud scoring' },
  injection: { label: 'Prompt Shield', description: 'Adversarial prompt injection defense' },
  provenance: { label: 'Provenance', description: 'Image & document origin tracking' },
  rag: { label: 'Pattern retrieval', description: 'Historical fraud pattern embedding lookup' },
};

export function formatAgentName(agentKey?: string | null): string {
  if (!agentKey) return 'Specialist';
  const clean = agentKey.trim().toLowerCase();
  return AGENT_METADATA[clean]?.label || agentKey;
}

// Centralized Fraud Typology Map
export const FRAUD_TYPE_MAP: Record<string, string> = {
  LINE_ITEM_ARITHMETIC_TOTAL: 'Arithmetic Discrepancy',
  GEOGRAPHIC_IMPOSSIBILITY_VELOCITY: 'Impossible Spacetime Velocity',
  UNBUNDLED_OR_PADDED_ANCILLARY: 'Padded / Unbundled Ancillary Services',
  SHARED_BANK_ACCOUNT: 'Shared Bank Account Ring',
  DISCHARGE_DATE_BEFORE_ADMISSION: 'Inverted Admission Timeline',
  PROMPT_INJECTION_DETECTED: 'Adversarial Prompt Injection',
  DOCUMENT_TAMPERING_FORGERY: 'Document Tampering / Forgery',
  DUPLICATE_CLAIM_SUBMISSION: 'Multi-Insurer Duplicate Submission',
  BENCHMARK_EXCEEDED: 'Diagnosis Price Benchmark Breach',
  POLICY_LIMIT_EXCEEDED: 'Policy Coverage Limit Exceeded',
};

export function formatFraudType(checkId?: string | null): string {
  if (!checkId) return 'Unclassified Anomaly';
  const clean = checkId.trim();
  if (FRAUD_TYPE_MAP[clean]) return FRAUD_TYPE_MAP[clean];
  // Fallback: Convert SCREAMING_SNAKE_CASE to Title Case
  return clean
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Format currency in Indian numbering system (e.g., ₹1,12,500)
 */
export function formatIndianCurrency(amountInRupees: number | null | undefined): string {
  if (amountInRupees === null || amountInRupees === undefined || isNaN(amountInRupees)) {
    return '₹0';
  }
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  }).format(amountInRupees);
}

export const formatINR = formatIndianCurrency;

/**
 * Format diagnosis code to human-readable clinical label with code badge.
 * Normalizes code: exact match -> trailing-zero adjustment -> 3-char parent block.
 * For unknown codes, returns 'description not in reference table' (never duplicates code).
 */
export function formatDiagnosis(code?: string | null): { label: string; code: string; full: string } {
  if (!code) {
    return { label: 'Not Specified', code: 'N/A', full: 'Not Specified' };
  }
  const cleanCode = code.trim().toUpperCase();

  // 1. Direct match
  if (ICD10_MAP[cleanCode]) {
    const human = ICD10_MAP[cleanCode];
    return {
      label: human,
      code: cleanCode,
      full: `${human} (${cleanCode})`,
    };
  }

  // 2. Trailing zero normalization (e.g. K35.8 <-> K35.80)
  if (cleanCode.endsWith('0') && ICD10_MAP[cleanCode.slice(0, -1)]) {
    const human = ICD10_MAP[cleanCode.slice(0, -1)];
    return {
      label: human,
      code: cleanCode,
      full: `${human} (${cleanCode})`,
    };
  }
  if (ICD10_MAP[`${cleanCode}0`]) {
    const human = ICD10_MAP[`${cleanCode}0`];
    return {
      label: human,
      code: cleanCode,
      full: `${human} (${cleanCode})`,
    };
  }

  // 3. Parent 3-character block fallback (e.g. K35 from K35.8)
  const parent = cleanCode.split('.')[0];
  if (ICD10_MAP[parent]) {
    const human = ICD10_MAP[parent];
    return {
      label: human,
      code: cleanCode,
      full: `${human} (${cleanCode})`,
    };
  }

  // 4. Truly unknown code: report that description is not in reference table
  return {
    label: 'description not in reference table',
    code: cleanCode,
    full: `${cleanCode} (description not in reference table)`,
  };
}

/**
 * Format insurer identifier to full corporate name
 */
export function formatInsurer(insurerId?: string | null): { name: string; short: string; id: string } {
  if (!insurerId) {
    return { name: 'Unassigned Insurer', short: 'N/A', id: 'N/A' };
  }
  const cleanId = insurerId.trim().toUpperCase();
  const entry = INSURER_MAP[cleanId];
  if (entry) {
    return { name: entry.name, short: entry.short, id: cleanId };
  }
  // Try partial prefix match
  const foundKey = Object.keys(INSURER_MAP).find((k) => cleanId.startsWith(k));
  if (foundKey) {
    return { name: INSURER_MAP[foundKey].name, short: INSURER_MAP[foundKey].short, id: cleanId };
  }
  return { name: cleanId, short: cleanId, id: cleanId };
}

/**
 * Format policy identifier to readable insurance policy name
 */
export function formatPolicy(policyId?: string | null): { name: string; id: string } {
  if (!policyId) {
    return { name: 'Unspecified Policy', id: 'N/A' };
  }
  const cleanId = policyId.trim();
  const matchingPrefix = Object.keys(POLICY_PREFIX_MAP).find((prefix) => cleanId.toUpperCase().startsWith(prefix));
  if (matchingPrefix) {
    const planName = POLICY_PREFIX_MAP[matchingPrefix];
    return { name: planName, id: cleanId };
  }
  return { name: 'Comprehensive Health Plan', id: cleanId };
}

/**
 * Format ISO timestamp to Indian Standard Time (IST) display
 */
export function formatDateTime(isoString?: string | null): string {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
      timeZone: 'Asia/Kolkata',
    }).format(date);
  } catch {
    return isoString;
  }
}

/**
 * Format date only (e.g., 14 Oct 2026)
 */
export function formatDateOnly(isoString?: string | null): string {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return isoString;
    return new Intl.DateTimeFormat('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      timeZone: 'Asia/Kolkata',
    }).format(date);
  } catch {
    return isoString;
  }
}

/**
 * Format doctor identifier
 */
export function formatDoctor(doctorId?: string | null): string {
  if (!doctorId) return 'Unassigned';
  const clean = doctorId.trim();
  if (clean.startsWith('DOC-')) {
    return `Dr. ${clean.substring(4)} (${clean})`;
  }
  return clean;
}
