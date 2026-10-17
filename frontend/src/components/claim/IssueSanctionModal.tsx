import React from 'react';
import { X, FileCheck, Key, Check } from 'lucide-react';
import { Claim } from '../../types';
import { formatINR } from '../../utils/formatters';

interface IssueSanctionModalProps {
  isOpen: boolean;
  onClose: () => void;
  claim: Claim;
  sanctionAmount: string;
  setSanctionAmount: (amt: string) => void;
  sanctionNotes: string;
  setSanctionNotes: (notes: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  issuing: boolean;
  issueSuccess: string | null;
}

export const IssueSanctionModal: React.FC<IssueSanctionModalProps> = ({
  isOpen,
  onClose,
  claim,
  sanctionAmount,
  setSanctionAmount,
  sanctionNotes,
  setSanctionNotes,
  onSubmit,
  issuing,
  issueSuccess,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-surface border border-white/10 rounded-[20px] w-full max-w-lg p-6 shadow-2xl space-y-5 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-muted hover:text-text-primary p-1.5 rounded-lg hover:bg-white/10 transition-colors"
          title="Close dialog"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <FileCheck className="w-5 h-5 text-emerald-400" />
            <h3 className="text-base font-bold text-text-primary">
              Issue Cryptographic Sanction Note
            </h3>
          </div>
          <p className="text-xs text-text-secondary">
            Digitally signs and marks outbound approval letter using Ed25519 & dual carriers (XMP + LSB letterhead).
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="sanction-amount" className="block text-xs font-semibold text-text-secondary mb-1.5">
              Sanctioned Disbursement Amount (₹ INR)
            </label>
            <div className="relative">
              <input
                id="sanction-amount"
                type="text"
                value={sanctionAmount}
                onChange={(e) => setSanctionAmount(e.target.value)}
                placeholder="e.g. 74550"
                className="w-full bg-surface-elevated border border-white/10 rounded-xl px-3.5 py-2 text-sm text-text-primary font-mono font-bold focus:outline-none focus:border-amber-primary focus:ring-1 focus:ring-amber-primary/40 transition-colors"
                required
              />
              <span className="absolute right-3 top-2 text-xs text-muted font-mono">
                Claimed: {formatINR(claim.total_claimed)}
              </span>
            </div>
          </div>

          <div>
            <label htmlFor="sanction-notes" className="block text-xs font-semibold text-text-secondary mb-1.5">
              Adjudication Rationale / Policy Endorsement Notes
            </label>
            <textarea
              id="sanction-notes"
              value={sanctionNotes}
              onChange={(e) => setSanctionNotes(e.target.value)}
              placeholder="e.g. Approved per Section 4.2 of Arogya Sanjeevani policy schedule. Deductible applied."
              rows={3}
              className="w-full bg-surface-elevated border border-white/10 rounded-xl p-3 text-xs text-text-primary placeholder-muted focus:outline-none focus:border-amber-primary focus:ring-1 focus:ring-amber-primary/40 transition-colors"
            />
          </div>

          <div className="p-3.5 rounded-xl bg-surface-elevated/70 border border-white/8 space-y-1.5 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-text-primary">
              <Key className="w-3.5 h-3.5 text-amber-primary" />
              <span>Outbound Cryptographic Attestation</span>
            </div>
            <ul className="text-[11px] text-muted space-y-1 list-disc pl-4">
              <li>Ed25519 digital signature embedded in XMP metadata</li>
              <li>Dual LSB pixel watermark encoded into header letterhead band</li>
              <li>Immutable SHA-256 integrity digest stored in ledger</li>
            </ul>
          </div>

          {issueSuccess && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
              <Check className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{issueSuccess}</span>
            </div>
          )}

          <div className="flex items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={issuing}
              className="px-4 py-2 rounded-xl border border-white/10 bg-surface-elevated hover:bg-surface text-text-secondary hover:text-text-primary text-xs font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={issuing}
              className="px-4 py-2 rounded-xl bg-amber-primary hover:bg-amber-bright text-black font-semibold text-xs shadow-md shadow-amber-primary/20 transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              <FileCheck className="w-3.5 h-3.5" />
              <span>{issuing ? 'Signing & Stamping...' : 'Sign & Issue Sanction Note'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
