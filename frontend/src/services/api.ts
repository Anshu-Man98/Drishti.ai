import { Claim, ClaimSummary, Dossier } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export async function fetchClaims(): Promise<ClaimSummary[]> {
  const resp = await fetch(`${API_BASE_URL}/claims`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch claims: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchClaim(claimId: string): Promise<Claim> {
  const resp = await fetch(`${API_BASE_URL}/claims/${claimId}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch claim ${claimId}: ${resp.statusText}`);
  }
  return resp.json();
}

export async function fetchDossier(claimId: string): Promise<Dossier | null> {
  const resp = await fetch(`${API_BASE_URL}/claims/${claimId}/dossier`);
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
  });
  if (!resp.ok) {
    throw new Error(`Analysis failed: ${resp.statusText}`);
  }
  return resp.json();
}

export async function uploadClaim(formData: FormData): Promise<{ claim_id: string }> {
  const resp = await fetch(`${API_BASE_URL}/claims`, {
    method: 'POST',
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
