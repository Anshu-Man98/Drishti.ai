import { Claim, ClaimSummary, Dossier } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

function getAuthHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
  const token = localStorage.getItem('token') || 'adjuster-token';
  return {
    'Authorization': `Bearer ${token}`,
    ...customHeaders,
  };
}

export interface FetchClaimsParams {
  limit?: number;
  offset?: number;
  verdict?: string;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
  search?: string;
  excludeSynthetic?: boolean;
}

export interface FetchClaimsResult {
  claims: ClaimSummary[];
  totalCount: number;
}

export async function fetchClaims(params?: FetchClaimsParams): Promise<FetchClaimsResult> {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.set('limit', String(params.limit));
  if (params?.offset !== undefined) query.set('offset', String(params.offset));
  if (params?.verdict && params.verdict !== 'all') query.set('verdict', params.verdict);
  if (params?.sortBy) query.set('sort_by', params.sortBy);
  if (params?.sortOrder) query.set('sort_order', params.sortOrder);
  if (params?.search) query.set('search', params.search);
  if (params?.excludeSynthetic !== undefined) {
    query.set('include_synthetic', String(!params.excludeSynthetic));
  }

  const qs = query.toString();
  const url = `${API_BASE_URL}/claims${qs ? `?${qs}` : ''}`;
  const resp = await fetch(url, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch claims: ${resp.statusText}`);
  }

  const totalHeader = resp.headers.get('X-Total-Count');
  const claims = await resp.json();
  const totalCount = totalHeader ? parseInt(totalHeader, 10) : claims.length;

  return { claims, totalCount };
}

export async function fetchClaim(claimId: string): Promise<Claim> {
  const resp = await fetch(`${API_BASE_URL}/claims/${claimId}`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch claim ${claimId}: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchDossier(claimId: string): Promise<Dossier | null> {
  const resp = await fetch(`${API_BASE_URL}/claims/${claimId}/dossier`, {
    headers: getAuthHeaders(),
  });
  if (resp.status === 404) {
    return null;
  }
  if (!resp.ok) {
    throw new Error(`Failed to fetch dossier: ${resp.statusText}`);
  }
  return resp.json();
}

export async function analyzeClaim(claimId: string): Promise<Dossier> {
  const resp = await fetch(`${API_BASE_URL}/claims/${claimId}/analyze`, {
    method: 'POST',
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Analysis failed: ${resp.statusText}`);
  }
  return resp.json();
}

export async function uploadClaim(formData: FormData): Promise<{ claim_id: string }> {
  const resp = await fetch(`${API_BASE_URL}/claims`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`Upload failed: ${errText || resp.statusText}`);
  }
  return resp.json();
}

export function getDocumentUrl(claimId: string, docId: string): string {
  return `${API_BASE_URL}/claims/${claimId}/documents/${docId}`;
}

export function getClaimPageImageUrl(claimId: string, pageNum: number = 1): string {
  return `${API_BASE_URL}/claims/${claimId}/pages/${pageNum}`;
}

export async function fetchAuthenticatedBlob(urlOrPath: string): Promise<Blob> {
  const fullUrl = urlOrPath.startsWith('http')
    ? urlOrPath
    : `${API_BASE_URL}${urlOrPath.startsWith('/') ? '' : '/'}${urlOrPath}`;
  const resp = await fetch(fullUrl, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    const errText = await resp.text().catch(() => resp.statusText);
    throw new Error(`Failed to fetch file (${resp.status}): ${errText || resp.statusText}`);
  }
  return resp.blob();
}

export async function fetchClaimPageBlob(claimId: string, pageNum: number = 1): Promise<Blob> {
  return fetchAuthenticatedBlob(`/claims/${claimId}/pages/${pageNum}`);
}

export async function downloadAuthenticatedFile(urlOrPath: string, filename: string): Promise<void> {
  const blob = await fetchAuthenticatedBlob(urlOrPath);
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
}

export async function openAuthenticatedFile(urlOrPath: string): Promise<void> {
  const blob = await fetchAuthenticatedBlob(urlOrPath);
  const objectUrl = URL.createObjectURL(blob);
  window.open(objectUrl, '_blank');
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
}

export async function fetchClaimEntities(claimId: string): Promise<{
  claim_id: string;
  entities: import('../types').ExtractedEntity[];
  field_sources: Record<string, string>;
}> {
  const resp = await fetch(`${API_BASE_URL}/claims/${claimId}/entities`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch entities: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchChatHistory(claimId: string): Promise<import('../types').ChatMessage[]> {
  const resp = await fetch(`${API_BASE_URL}/claims/${claimId}/chat`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    let errDetail = '';
    try {
      const errJson = await resp.json();
      errDetail = errJson.detail || '';
    } catch {
      errDetail = await resp.text().catch(() => '');
    }
    const err: any = new Error(errDetail || `Failed to fetch chat history: ${resp.status} ${resp.statusText}`);
    err.status = resp.status;
    throw err;
  }
  return resp.json();
}

export async function streamClaimChat(
  claimId: string,
  message: string,
  onChunk: (chunk: string) => void,
  onComplete: (res: import('../types').ChatResponse) => void,
  onError: (err: any) => void
): Promise<void> {
  try {
    const resp = await fetch(`${API_BASE_URL}/claims/${claimId}/chat`, {
      method: 'POST',
      headers: getAuthHeaders({
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      }),
      body: JSON.stringify({ message }),
    });

    if (!resp.ok) {
      let errDetail = '';
      try {
        const errJson = await resp.json();
        errDetail = errJson.detail || '';
      } catch {
        errDetail = await resp.text().catch(() => '');
      }
      const err: any = new Error(errDetail || `Chat error: ${resp.status} ${resp.statusText}`);
      err.status = resp.status;
      throw err;
    }

    if (!resp.body) {
      throw new Error('ReadableStream not supported on this browser.');
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let accumulatedChunks = '';
    let completed = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('data:')) {
          const jsonStr = trimmed.slice(5).trim();
          if (!jsonStr) continue;
          try {
            const data = JSON.parse(jsonStr);
            if (data.chunk) {
              accumulatedChunks += data.chunk;
              onChunk(data.chunk);
            }
            if (data.done) {
              completed = true;
              onComplete({
                answer: data.answer || accumulatedChunks,
                cited_finding_ids: data.cited_finding_ids || [],
                cited_evidence: data.cited_evidence || [],
              });
            }
          } catch (e) {
            console.error('Error parsing SSE event:', e, jsonStr);
          }
        }
      }
    }

    // Safety fallback: if stream finished without an explicit done event, finalize cleanly
    if (!completed) {
      onComplete({
        answer: accumulatedChunks || (buffer.startsWith('data:') ? '' : buffer.trim()),
        cited_finding_ids: [],
        cited_evidence: [],
      });
    }
  } catch (err) {
    onError(err);
  }
}

export async function issueApprovalLetter(
  claimId: string,
  amountPaise: number,
  notes?: string
): Promise<import('../types').IssueApprovalResponse> {
  const resp = await fetch(`${API_BASE_URL}/claims/${claimId}/issue-approval`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ amount_paise: amountPaise, notes }),
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`Failed to issue approval letter: ${errText || resp.statusText}`);
  }
  return resp.json();
}

export async function verifyDocument(
  file: File,
  claimId?: string
): Promise<import('../types').ProvenanceVerifyResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (claimId) {
    formData.append('claim_id', claimId);
  }
  const resp = await fetch(`${API_BASE_URL}/provenance/verify`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData,
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`Failed to verify document provenance: ${errText || resp.statusText}`);
  }
  return resp.json();
}

export function getProvenancePubkeyUrl(): string {
  return `${API_BASE_URL}/provenance/pubkey`;
}

export interface HealthStatus {
  status: string;
  service: string;
  environment: string;
  cloud_mode: string;
  all_healthy: boolean;
  dependencies?: Record<string, { ok: boolean; status: string; detail?: string }>;
  models?: {
    pro: string;
    flash: string;
  };
}

export async function fetchHealthStatus(): Promise<HealthStatus> {
  const resp = await fetch(`${API_BASE_URL}/health`);
  if (!resp.ok && resp.status !== 503) {
    throw new Error(`Health check failed: ${resp.status}`);
  }
  return resp.json();
}

export async function fetchAnalyticsSummary(excludeSynthetic: boolean = false): Promise<import('../types').AnalyticsSummary> {
  const includeSynthetic = !excludeSynthetic;
  const url = `${API_BASE_URL}/analytics/summary?include_synthetic=${includeSynthetic}`;
  const resp = await fetch(url, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch analytics summary: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchFraudRings(ringId?: string): Promise<import('../types').GraphRingsResponse> {
  const url = ringId
    ? `${API_BASE_URL}/graph/rings?ring_id=${encodeURIComponent(ringId)}`
    : `${API_BASE_URL}/graph/rings`;
  const resp = await fetch(url, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch fraud rings: ${resp.statusText}`);
  }
  return resp.json();
}

export async function startDuel(
  claimId?: string,
  rounds: number = 3
): Promise<import('../types').DuelResult> {
  const resp = await fetch(`${API_BASE_URL}/duel/start`, {
    method: 'POST',
    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ claim_id: claimId || null, rounds }),
  });
  if (!resp.ok) {
    const errText = await resp.text();
    throw new Error(`Failed to start adversarial duel: ${errText || resp.statusText}`);
  }
  return resp.json();
}

export async function fetchDuelStatus(duelId: string): Promise<import('../types').DuelStatusResponse> {
  const resp = await fetch(`${API_BASE_URL}/duel/${encodeURIComponent(duelId)}/status`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch duel status: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchDuelRounds(duelId: string): Promise<import('../types').DuelRound[]> {
  const resp = await fetch(`${API_BASE_URL}/duel/${encodeURIComponent(duelId)}/rounds`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch duel rounds: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchLearnedPatterns(): Promise<import('../types').LearnedPattern[]> {
  const resp = await fetch(`${API_BASE_URL}/duel/patterns/learned`, {
    headers: getAuthHeaders(),
  });
  if (!resp.ok) {
    throw new Error(`Failed to fetch learned evasion patterns: ${resp.statusText}`);
  }
  return resp.json();
}
