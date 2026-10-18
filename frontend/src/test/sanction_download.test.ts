import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchAuthenticatedBlob, downloadAuthenticatedFile } from '../services/api';

describe('fetchAuthenticatedBlob URL resolution & Sanction Download Fix', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('does not duplicate /api prefix when path already starts with /api/', async () => {
    const mockBlob = new Blob(['sample pdf content'], { type: 'application/pdf' });
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      blob: async () => mockBlob,
    } as Response);

    const blob = await fetchAuthenticatedBlob('/api/claims/CLM-123/documents/SANCTION-ABC');

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const calledUrl = fetchSpy.mock.calls[0][0];
    expect(calledUrl).toBe('/api/claims/CLM-123/documents/SANCTION-ABC');
    expect(calledUrl).not.toContain('/api/api/');
    expect(blob).toBe(mockBlob);
  });

  it('correctly adds /api prefix when path does not contain /api', async () => {
    const mockBlob = new Blob(['image bytes'], { type: 'image/png' });
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      blob: async () => mockBlob,
    } as Response);

    const blob = await fetchAuthenticatedBlob('/claims/CLM-123/pages/1');

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const calledUrl = fetchSpy.mock.calls[0][0];
    expect(calledUrl).toBe('/api/claims/CLM-123/pages/1');
    expect(calledUrl).not.toContain('/api/api/');
    expect(blob).toBe(mockBlob);
  });

  it('preserves full http/https URLs without modification', async () => {
    const mockBlob = new Blob(['remote bytes'], { type: 'application/pdf' });
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      blob: async () => mockBlob,
    } as Response);

    await fetchAuthenticatedBlob('https://storage.googleapis.com/bucket/doc.pdf');

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const calledUrl = fetchSpy.mock.calls[0][0];
    expect(calledUrl).toBe('https://storage.googleapis.com/bucket/doc.pdf');
  });

  it('triggers link click and download with objectUrl for sanction note', async () => {
    const mockBlob = new Blob(['pdf-data'], { type: 'application/pdf' });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      blob: async () => mockBlob,
    } as Response);

    const createObjectURLSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:http://localhost/mock-uuid');
    const revokeObjectURLSpy = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    await downloadAuthenticatedFile('/api/claims/CLM-123/documents/SANCTION-999', 'Sanction_SANCTION-999.pdf');

    expect(createObjectURLSpy).toHaveBeenCalledWith(mockBlob);
    createObjectURLSpy.mockRestore();
    revokeObjectURLSpy.mockRestore();
  });
});
