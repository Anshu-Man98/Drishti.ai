export type DocType = 'bill' | 'prescription' | 'discharge_summary' | 'lab_report' | 'photo';
export type AgentName = 'forensics' | 'policy' | 'crossref' | 'spacetime' | 'ml' | 'injection' | 'provenance' | 'rag';
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

export interface ExtractedEntity {
  field_name: string;
  text: string;
  bbox?: [number, number, number, number] | null;
  page: number;
  confidence: number;
  source: 'docai' | 'gemini';
}

export interface LineItem {
  description: string;
  qty: number;
  unit_price: number;
  amount: number;
  bbox?: [number, number, number, number] | null;
  page?: number;
  source?: string;
}

export interface Document {
  doc_id: string;
  gcs_uri: string;
  doc_type: DocType;
  sha256: string;
  filename?: string;
  page_count?: number;
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
  extracted_entities?: ExtractedEntity[];
  field_sources?: Record<string, string>;
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
  layer?: 'visible' | 'hidden' | 'metadata' | 'retrieved' | null;
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
  category?: string;
  computed_chip?: string | null;
  computed_details?: Record<string, any> | null;
}

export interface MlFeature {
  feature: string;
  attribution: number;
  direction?: 'raises risk' | 'lowers risk';
}

export interface TimelineEvent {
  ts: string;
  lat: number;
  lng: number;
  place: string;
  doc_id?: string;
  actor: string;
  description?: string;
}

export interface RetrievedContext {
  source: 'policy' | 'pattern';
  ref_id: string;
  title: string;
  snippet: string;
  score: number;
}

export interface Provenance {
  status: 'verified' | 'tampered' | 'unmarked' | 'not_applicable';
  issued_doc_id?: string | null;
  detail?: string | null;
  diff?: {
    field?: string;
    issued?: number | string;
    presented?: number | string;
    issued_display?: string;
    presented_display?: string;
  } | null;
  carrier?: string | null;
}

export interface Dossier {
  claim_id: string;
  risk_score: number;
  ml_score?: number | null;
  baseline_ml_score?: number | null;
  verdict: Verdict;
  status?: 'complete' | 'incomplete';
  summary: string;
  findings: Finding[];
  top_ml_features?: MlFeature[];
  timeline?: TimelineEvent[];
  retrieved_context?: RetrievedContext[] | null;
  provenance?: Provenance | null;
  created_at: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  cited_finding_ids?: string[];
  cited_evidence?: Evidence[];
  created_at?: string;
}

export interface ChatResponse {
  answer: string;
  cited_finding_ids: string[];
  cited_evidence: Evidence[];
}

export interface IssueApprovalResponse {
  download_url: string;
  doc_id: string;
  amount_paise: number;
  payload: Record<string, any>;
}

export interface ProvenanceVerifyResponse {
  status: 'verified' | 'tampered' | 'unmarked' | 'not_applicable' | 'disabled' | string;
  detail?: string | null;
  payload?: Record<string, any> | null;
  carrier?: string | null;
  diff?: {
    field: string;
    issued: any;
    presented: any;
    issued_display?: string;
    presented_display?: string;
  } | null;
  issued_doc_id?: string | null;
}

export interface FraudCategoryStat {
  category: string;
  count: number;
  claims_count?: number;
}

export interface RecentCriticalClaim {
  claim_id: string;
  policy_id: string;
  insurer_id: string;
  claimant_name: string;
  hospital_name: string;
  city: string;
  diagnosis_code: string;
  total_claimed: number;
  verdict: Verdict | string;
  status?: string;
  risk_score: number;
  top_finding_title: string;
  incomplete_reason?: string | null;
  created_at: string;
}

export interface AnalyticsSummary {
  total_claims: number;
  total_amount_claimed: number;
  total_amount_protected: number;
  total_amount_review: number;
  verdicts: {
    approve: number;
    review: number;
    reject: number;
    pending: number;
  };
  fraud_categories: FraudCategoryStat[];
  agent_breakdown: Record<string, number>;
  agent_claims_breakdown?: Record<string, number>;
  recent_critical_claims: RecentCriticalClaim[];
  time_series?: Array<{
    date: string;
    claims_count: number;
    amount_claimed: number;
    avg_risk: number;
  }>;
  synthetic_count?: number;
  timestamp: string;
}

export interface NetworkNode {
  id: string;
  label: string;
  type: 'claimant' | 'doctor' | 'hospital' | 'bank_account';
  ring_id: string;
  risk_score?: number;
  metadata?: Record<string, any>;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

export interface NetworkEdge {
  source: string;
  target: string;
  type: string;
  label?: string;
  claim_id?: string;
  amount?: number;
}

export interface FraudRingSummary {
  ring_id: string;
  title: string;
  type: string;
  claim_count: number;
  claimant_count: number;
  total_amount: number;
  primary_entity: string;
  risk_level: 'critical' | 'high' | 'medium';
  description: string;
  sample_cities: string[];
}

export interface RingClaimRecord {
  claim_id: string;
  policy_id: string;
  insurer_id: string;
  claimant_id: string;
  claimant_name: string;
  claimant_phone: string;
  bank_account_hash: string;
  hospital_id: string;
  hospital_name: string;
  city: string;
  doctor_id: string;
  admission_ts: string;
  discharge_ts: string;
  diagnosis_code: string;
  total_claimed: number;
  is_fraud: number;
  fraud_type: string;
}

export interface RingDetailResponse {
  ring: FraudRingSummary;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  claims: RingClaimRecord[];
}

export interface GraphRingsResponse {
  rings: FraudRingSummary[];
  selected_ring?: RingDetailResponse | null;
}

export interface DuelRound {
  round_number: number;
  tactic: string;
  rationale: string;
  claim_id: string;
  baseline_amount: number;
  total_claimed: number;
  inflation_ratio: number;
  verdict: string;
  risk_score: number;
  caught: boolean;
  evaded: boolean;
  catching_finding_ids: string[];
  catching_check_ids: string[];
  timestamp: string;
}

export interface LearnedPattern {
  pattern_id: string;
  title: string;
  tactic: string;
  signature?: string;
  feature_signatures?: string;
  typical_severity?: string;
  narrative?: string;
  fraud_type?: string;
  evaded_at: string;
}

export interface DuelResult {
  duel_id: string;
  base_claim_id: string;
  baseline_amount: number;
  max_rounds: number;
  rounds: DuelRound[];
  status: string; // 'running' | 'completed' | 'failed' | 'evaded' | 'caught' | 'max_rounds_reached'
  winning_side: string; // 'fraudster' | 'defender' | 'running'
  learned_pattern?: LearnedPattern | null;
}

export interface DuelStatusResponse {
  duel_id: string;
  status: 'running' | 'completed' | 'failed' | string;
  current_round: number;
  max_rounds: number;
  base_claim_id?: string | null;
  baseline_amount?: number | null;
  winning_side?: string | null;
  error?: string | null;
  rounds: DuelRound[];
  learned_pattern?: LearnedPattern | null;
}



