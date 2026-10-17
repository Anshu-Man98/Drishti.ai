import React from 'react';
import { ShieldCheck, Key, Upload, RefreshCw } from 'lucide-react';
import { Dossier, ProvenanceVerifyResponse } from '../../types';
import { getProvenancePubkeyUrl } from '../../services/api';

interface ProvenanceCardProps {
  provenance?: Dossier['provenance'];
  onVerifyFile: (file: File) => void;
  verifying: boolean;
  verificationResult: ProvenanceVerifyResponse | null;
  verifyError: string | null;
}

export const ProvenanceCard: React.FC<ProvenanceCardProps> = ({
  provenance,
  onVerifyFile,
  verifying,
  verificationResult,
  verifyError,
}) => {
  return (
    <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 sm:p-6 shadow-2xs backdrop-blur-md space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-primary">
            Document Provenance (Ed25519 & Dual Watermark)
          </h3>
        </div>
        <a
          href={getProvenancePubkeyUrl()}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 text-[10px] font-mono px-2.5 py-1 rounded-full bg-surface-elevated text-amber-primary hover:text-amber-bright border border-white/10 hover:border-amber-primary/40 transition-colors"
          title="Inspect Ed25519 Public Key PEM"
        >
          <Key className="w-3 h-3 text-amber-primary" />
          <span>Public Key PEM</span>
        </a>
      </div>

      {/* Case File Document Provenance Status */}
      {provenance ? (
        <div
          className={`p-4 rounded-xl border ${
            provenance.status === 'tampered'
              ? 'bg-rose-500/10 border-rose-500/30 shadow-sm'
              : provenance.status === 'verified'
              ? 'bg-emerald-500/10 border-emerald-500/30'
              : provenance.status === 'unmarked'
              ? 'bg-amber-primary/10 border-amber-primary/30'
              : 'bg-surface-elevated/70 border-white/8'
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`text-xs font-bold uppercase tracking-wider font-mono px-2.5 py-0.5 rounded-full ${
                    provenance.status === 'tampered'
                      ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                      : provenance.status === 'verified'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : provenance.status === 'unmarked'
                      ? 'bg-amber-primary/20 text-amber-primary border border-amber-primary/30'
                      : 'bg-white/10 text-muted border border-white/10'
                  }`}
                >
                  {provenance.status === 'tampered'
                    ? 'Tampered Post-Issuance'
                    : provenance.status === 'verified'
                    ? 'Authentic Outbound Document'
                    : provenance.status === 'unmarked'
                    ? 'Unmarked Expected Issuance'
                    : 'Third-Party Document'}
                </span>
                {provenance.issued_doc_id && (
                  <span className="text-[11px] font-mono text-muted">
                    Ref: {provenance.issued_doc_id}
                  </span>
                )}
              </div>
              <p className="text-xs text-text-secondary leading-relaxed pt-1">
                {provenance.detail}
              </p>
            </div>
          </div>

          {/* Tamper diff comparison */}
          {provenance.status === 'tampered' && (
            <div className="mt-3 p-3 rounded-xl bg-rose-500/15 border border-rose-500/30 space-y-2">
              <div className="text-[11px] font-semibold text-rose-300 uppercase tracking-wide">
                Cryptographic Semantic Content Hash Mismatch
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-2.5 rounded-lg bg-surface border border-white/10">
                  <span className="text-[10px] uppercase text-emerald-400 block font-sans font-semibold">
                    Digitally Signed at Issuance
                  </span>
                  <span className="text-emerald-400 text-sm font-bold">
                    {provenance.diff?.issued_display || '₹50,000.00'}
                  </span>
                  <p className="text-[10px] text-muted mt-0.5">Signed in Ed25519 payload</p>
                </div>
                <div className="p-2.5 rounded-lg bg-surface border border-rose-500/40">
                  <span className="text-[10px] uppercase text-rose-400 block font-sans font-semibold">
                    Altered Rendered Page
                  </span>
                  <span className="text-rose-400 text-sm font-bold">
                    {provenance.diff?.presented_display || 'Altered Value'}
                  </span>
                  <p className="text-[10px] text-rose-400/80 mt-0.5">
                    Forged visible text (Post-issuance alteration)
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="p-4 rounded-xl border border-dashed border-white/10 bg-surface-elevated/40 text-center text-xs text-muted">
          No outbound provenance record attached to this claim.
        </div>
      )}

      {/* Live In-Browser Verification Dropzone */}
      <div className="space-y-3 pt-2 border-t border-white/6">
        <h4 className="text-xs font-bold uppercase tracking-wider text-muted flex items-center gap-1.5">
          <Upload className="w-3.5 h-3.5 text-amber-primary" />
          <span>On-The-Fly Document Verification</span>
        </h4>
        <p className="text-xs text-text-secondary leading-relaxed">
          Upload any PDF or PNG invoice to extract forensic carriers (XMP metadata + LSB pixel watermark) and verify against the public key.
        </p>

        <div className="relative border-2 border-dashed border-white/15 hover:border-amber-primary/50 rounded-xl p-4 text-center transition-colors bg-surface-elevated/30">
          <input
            type="file"
            accept=".pdf,.png"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                onVerifyFile(e.target.files[0]);
              }
            }}
            disabled={verifying}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
          />
          <div className="flex flex-col items-center justify-center gap-1.5">
            {verifying ? (
              <>
                <RefreshCw className="w-5 h-5 text-amber-primary animate-spin" />
                <span className="text-xs text-text-primary font-medium">Extracting cryptographic carriers...</span>
              </>
            ) : (
              <>
                <Upload className="w-5 h-5 text-muted" />
                <span className="text-xs text-text-primary font-medium">Drop document or click to verify</span>
                <span className="text-[10px] text-muted">PDF or PNG (Max 15MB)</span>
              </>
            )}
          </div>
        </div>

        {/* Verification Result Callout */}
        {verificationResult && (
          <div
            className={`p-3.5 rounded-xl border text-xs space-y-1 ${
              verificationResult.status === 'verified'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            }`}
          >
            <div className="flex items-center justify-between font-bold">
              <span>{verificationResult.status === 'verified' ? 'Signature Valid (Authentic)' : 'Signature Invalid / Tampered'}</span>
              <span className="font-mono text-[10px]">{verificationResult.status}</span>
            </div>
            <p className="text-[11px] leading-relaxed opacity-90">{verificationResult.detail}</p>
          </div>
        )}

        {verifyError && (
          <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-300">
            {verifyError}
          </div>
        )}
      </div>
    </div>
  );
};
