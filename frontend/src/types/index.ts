export type DocType = 'bill' | 'prescription' | 'discharge_summary' | 'lab_report' | 'photo';
export type AgentName = 'forensics' | 'policy' | 'crossref' | 'spacetime' | 'ml';
export type Severity = 'info' | 'low' | 'medium' | 'high' | 'critical';
export type Verdict = 'approve' | 'review' | 'reject';

export interface Claimant {
  claimant_id: string;
  name: string;
  phone: string;
  bank_account_hash: string;
}

export interface Provider {
  hospital_id: string;
  name: string;
  city: string;
  lat: number;
  lng: number;
}

export interface LineItem {
  description: string;
  qty: number;
  unit_price: number;
  amount: number;
}

export interface Document {
  doc_id: string;
  gcs_uri: string;
  doc_type: DocType;
  sha256: string;
  filename?: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  insurer_id: string;
  claimant: Claimant;
  provider: Provider;
  doctor_id: string;
  admission_ts: string;
  discharge_ts: string;
  diagnosis_code: string;
  line_items: LineItem[];
  subtotal: number;
  tax: number;
  total_claimed: number;
  documents: Document[];
  created_at?: string;
}

export interface ClaimSummary {
  claim_id: string;
  policy_id: string;
  insurer_id: string;
  claimant_name: string;
  hospital_name: string;
  city: string;
  total_claimed: number;
  admission_ts: string;
  discharge_ts: string;
  diagnosis_code: string;
  doc_count: number;
  created_at: string;
  verdict?: Verdict;
  risk_score?: number;
}

export interface Evidence {
  doc_id: string;
  page: number;
  bbox?: [number, number, number, number] | null;
  quote?: string;
}

export interface Finding {
  finding_id: string;
  agent: AgentName;
  check_id: string;
  severity: Severity;
  title: string;
  explanation: string;
  evidence: Evidence[];
  confidence: number;
}

export interface MlFeature {
  feature: string;
  attribution: number;
}

export interface TimelineEvent {
  ts: string;
  lat: number;
  lng: number;
  place: string;
  doc_id?: string;
  actor: string;
}

export interface Dossier {
  claim_id: string;
  risk_score: number;
  ml_score?: number | null;
  verdict: Verdict;
  summary: string;
  findings: Finding[];
  top_ml_features?: MlFeature[];
  timeline?: TimelineEvent[];
  created_at: string;
}
