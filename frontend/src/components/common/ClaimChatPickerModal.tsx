import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  X,
  Bot,
  ArrowRight,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Building2,
  User,
  Sparkles,
} from 'lucide-react';
import { ClaimSummary } from '../../types';
import { fetchClaims } from '../../services/api';
import { formatCurrencyINR } from '../../utils/formatters';

interface ClaimChatPickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectClaim: (claimId: string) => void;
  currentClaimId?: string | null;
}

export const ClaimChatPickerModal: React.FC<ClaimChatPickerModalProps> = ({
  isOpen,
  onClose,
  onSelectClaim,
  currentClaimId,
}) => {
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const lastFocusedRef = useRef<HTMLElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Track opener focus and manage focus trap
  useEffect(() => {
    if (isOpen) {
      lastFocusedRef.current = document.activeElement as HTMLElement | null;
      setSearch('');
      setLoading(true);
      setError(null);

      fetchClaims({ limit: 15, sortBy: 'created_at', sortOrder: 'desc' })
        .then((res) => {
          setClaims(res.claims || []);
          setLoading(false);
        })
        .catch((err) => {
          setError(err.message || 'Failed to load claims');
          setLoading(false);
        });

      // Focus input on open
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 50);
    } else if (lastFocusedRef.current) {
      lastFocusedRef.current.focus?.();
    }
  }, [isOpen]);

  // Handle Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Filter claims based on search input
  const query = search.trim().toLowerCase();
  const filteredClaims = claims.filter((c) => {
    if (!query) return true;
    return (
      c.claim_id.toLowerCase().includes(query) ||
      (c.claimant_name && c.claimant_name.toLowerCase().includes(query)) ||
      (c.hospital_name && c.hospital_name.toLowerCase().includes(query)) ||
      (c.diagnosis_code && c.diagnosis_code.toLowerCase().includes(query)) ||
      (c.verdict && c.verdict.toLowerCase().includes(query))
    );
  });

  // Sort: prioritize currentClaimId if present
  const sortedClaims = [...filteredClaims].sort((a, b) => {
    if (currentClaimId) {
      if (a.claim_id === currentClaimId) return -1;
      if (b.claim_id === currentClaimId) return 1;
    }
    return 0;
  });

  const getVerdictBadge = (verdict?: string) => {
    const v = (verdict || 'PENDING').toUpperCase();
    if (v === 'APPROVE') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
          <ShieldCheck className="w-3 h-3" />
          <span>APPROVE</span>
        </span>
      );
    }
    if (v === 'REJECT') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
          <ShieldAlert className="w-3 h-3" />
          <span>REJECT</span>
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
        <AlertTriangle className="w-3 h-3" />
        <span>REVIEW</span>
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/75 backdrop-blur-sm transition-all"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Which claim do you want to ask about?"
        className="relative z-10 w-full max-w-xl max-h-[85vh] flex flex-col rounded-2xl bg-app-surface border border-white/10 shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200"
      >
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-white/[0.08] flex items-center justify-between gap-3 bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-amber-primary/14 border border-amber-primary/30 flex items-center justify-center text-amber-primary shadow-[0_0_12px_rgba(245,165,36,0.3)]">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm sm:text-base font-semibold text-app-primary flex items-center gap-2">
                <span>Which claim do you want to ask about?</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
                  Case Assistant
                </span>
              </h2>
              <p className="text-xs text-app-muted">
                Select a claim to open the grounded Gemini 3.5 Case Assistant.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <kbd className="hidden sm:inline-flex text-[10px] font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-app-muted border border-white/[0.08]">
              ESC
            </kbd>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close claim picker"
              className="p-1.5 rounded-lg text-app-muted hover:text-app-primary hover:bg-white/[0.06] transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="p-3 sm:p-4 border-b border-white/[0.06] bg-app-base/40">
          <div className="relative flex items-center">
            <Search className="w-4 h-4 text-app-muted absolute left-3 pointer-events-none" />
            <input
              ref={searchInputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by Claim ID (e.g. CLM-G1), hospital, claimant, or diagnosis..."
              className="w-full bg-app-surface/90 border border-white/10 rounded-xl pl-9 pr-4 py-2.5 text-xs sm:text-sm text-app-primary placeholder-app-muted focus:outline-none focus:border-amber-primary/60 transition-colors shadow-inner"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-3 text-app-muted hover:text-app-primary text-xs"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Claims List */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-2">
          {loading && (
            <div className="py-12 text-center text-app-muted space-y-2">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto text-amber-primary" />
              <p className="text-xs">Fetching claims from warehouse...</p>
            </div>
          )}

          {error && !loading && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs text-center space-y-2">
              <p>{error}</p>
              <button
                type="button"
                onClick={() => {
                  setLoading(true);
                  setError(null);
                  fetchClaims({ limit: 15, sortBy: 'created_at', sortOrder: 'desc' })
                    .then((res) => {
                      setClaims(res.claims || []);
                      setLoading(false);
                    })
                    .catch((err) => {
                      setError(err.message);
                      setLoading(false);
                    });
                }}
                className="px-3 py-1.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-xs font-medium transition-colors"
              >
                Retry
              </button>
            </div>
          )}

          {!loading && !error && sortedClaims.length === 0 && (
            <div className="py-12 text-center text-app-muted space-y-2">
              <Sparkles className="w-8 h-8 mx-auto text-app-muted/40" />
              <p className="text-sm font-medium text-app-primary">No matching claims found</p>
              <p className="text-xs">Try searching by hospital, claim ID, or diagnosis code.</p>
            </div>
          )}

          {!loading &&
            !error &&
            sortedClaims.map((claim) => {
              const isCurrent = currentClaimId === claim.claim_id;
              return (
                <button
                  key={claim.claim_id}
                  type="button"
                  onClick={() => onSelectClaim(claim.claim_id)}
                  className={`w-full p-3 sm:p-3.5 rounded-xl border text-left transition-all flex items-center justify-between gap-3 group cursor-pointer ${
                    isCurrent
                      ? 'bg-amber-primary/10 border-amber-primary/40 shadow-sm'
                      : 'bg-white/[0.02] hover:bg-white/[0.05] border-white/[0.06] hover:border-amber-primary/30'
                  }`}
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs sm:text-sm font-bold text-app-primary group-hover:text-amber-primary transition-colors">
                        {claim.claim_id}
                      </span>
                      {isCurrent && (
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-primary/20 text-amber-primary font-semibold">
                          Active Claim
                        </span>
                      )}
                      {getVerdictBadge(claim.verdict)}
                      <span className="text-[11px] font-mono text-app-muted">
                        Risk: <span className="font-bold text-app-primary">{claim.risk_score ?? '—'}</span>
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-app-muted truncate">
                      {claim.claimant_name && (
                        <span className="inline-flex items-center gap-1 truncate text-app-primary">
                          <User className="w-3 h-3 text-app-muted shrink-0" />
                          <span className="truncate">{claim.claimant_name}</span>
                        </span>
                      )}
                      {claim.hospital_name && (
                        <span className="inline-flex items-center gap-1 truncate">
                          <Building2 className="w-3 h-3 text-app-muted shrink-0" />
                          <span className="truncate">{claim.hospital_name}</span>
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0">
                    <div className="text-right">
                      <div className="text-xs sm:text-sm font-mono font-bold text-app-primary">
                        {formatCurrencyINR(claim.total_claimed || 0)}
                      </div>
                      <div className="text-[10px] text-app-muted">Claimed</div>
                    </div>
                    <div className="w-7 h-7 rounded-lg bg-white/[0.04] group-hover:bg-amber-primary group-hover:text-black flex items-center justify-center text-app-muted transition-colors">
                      <ArrowRight className="w-4 h-4" />
                    </div>
                  </div>
                </button>
              );
            })}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-white/[0.06] bg-white/[0.01] flex items-center justify-between text-xs text-app-muted">
          <span>Tip: Press <kbd className="px-1 py-0.5 rounded bg-white/10 font-mono text-[10px]">ESC</kbd> to dismiss</span>
          <span className="font-mono text-[11px]">Drishti Grounded AI</span>
        </div>
      </div>
    </div>
  );
};
