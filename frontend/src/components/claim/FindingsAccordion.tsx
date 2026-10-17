import React from 'react';
import {
  AlertTriangle,
  ShieldAlert,
  Crosshair,
  Compass,
  BookOpen,
  FileCheck,
  Search,
} from 'lucide-react';
import { Finding, RetrievedContext } from '../../types';

interface FindingsAccordionProps {
  findings: Finding[];
  retrievedContext?: RetrievedContext[] | null;
  policyId: string;
  activeFindingId: string | null;
  onSelectFinding: (findingId: string | null) => void;
  onSwitchToSpacetime?: () => void;
}

export const FindingsAccordion: React.FC<FindingsAccordionProps> = ({
  findings,
  retrievedContext,
  policyId,
  activeFindingId,
  onSelectFinding,
  onSwitchToSpacetime,
}) => {
  const getSeverityBadgeClass = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      case 'high':
        return 'bg-rose-500/10 text-rose-300 border-rose-500/20';
      case 'medium':
        return 'bg-amber-primary/10 text-amber-primary border-amber-primary/30';
      default:
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
    }
  };

  const getSeverityEdgeClass = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
      case 'high':
        return 'border-l-4 border-l-rose-500';
      case 'medium':
        return 'border-l-4 border-l-amber-primary';
      case 'low':
        return 'border-l-4 border-l-emerald-500';
      default:
        return 'border-l-4 border-l-muted';
    }
  };

  const policyContext = retrievedContext?.filter((c) => c.source === 'policy') || [];
  const patternContext = retrievedContext?.filter((c) => c.source === 'pattern') || [];

  const realFindings = (findings || []).filter(
    (f) =>
      f.severity?.toLowerCase() !== 'info' &&
      !f.check_id?.toLowerCase().includes('ungrounded')
  );

  return (
    <div className="space-y-6">
      {/* Findings Section */}
      <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 sm:p-6 shadow-2xs backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between border-b border-white/8 pb-3">
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
              Flagged Anomalies ({realFindings.length})
            </h3>
          </div>
          <span className="text-[11px] text-muted">
            Click any card to highlight on document
          </span>
        </div>

        {realFindings.length === 0 ? (
          <div className="py-8 text-center text-xs text-muted">
            No audit findings or anomalies detected on this claim.
          </div>
        ) : (
          <div className="space-y-3">
            {realFindings.map((f) => {
              const isSelected = f.finding_id === activeFindingId;
              const hasEvidenceBbox = f.evidence?.some((ev) => ev.bbox && ev.bbox.length === 4);
              const isSpacetime =
                f.agent === 'spacetime' ||
                f.check_id?.includes('SPACETIME') ||
                f.category?.includes('SPACETIME');

              return (
                <div
                  key={f.finding_id}
                  role="button"
                  tabIndex={0}
                  aria-expanded={isSelected}
                  onClick={() => onSelectFinding(isSelected ? null : f.finding_id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelectFinding(isSelected ? null : f.finding_id);
                    }
                  }}
                  className={`p-4 rounded-xl border transition-all cursor-pointer flex items-start gap-3.5 ${getSeverityEdgeClass(
                    f.severity
                  )} ${
                    isSelected
                      ? 'bg-surface-elevated/90 border-amber-primary/50 shadow-md ring-1 ring-amber-primary/40'
                      : 'bg-surface-elevated/50 border-white/8 hover:border-amber-primary/30'
                  }`}
                >
                  <AlertTriangle
                    className={`w-4 h-4 shrink-0 mt-0.5 ${
                      f.severity === 'critical' || f.severity === 'high'
                        ? 'text-rose-400'
                        : 'text-amber-primary'
                    }`}
                  />
                  <div className="space-y-2 flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-bold text-text-primary font-mono">
                        {f.title}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">
                        {f.agent === 'injection' && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center gap-1">
                            <ShieldAlert className="w-3 h-3 text-rose-400" />
                            <span>AI Attack Quarantined</span>
                          </span>
                        )}
                        {f.agent === 'rag' && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/30 flex items-center gap-1">
                            <BookOpen className="w-3 h-3 text-amber-primary" />
                            <span>Corroborating Pattern</span>
                          </span>
                        )}
                        {f.agent === 'policy' &&
                          f.evidence?.some((e) => e.layer === 'retrieved') && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                              <BookOpen className="w-3 h-3 text-emerald-400" />
                              <span>Clause Grounded</span>
                            </span>
                          )}
                        <span
                          className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full border shrink-0 ${getSeverityBadgeClass(
                            f.severity
                          )}`}
                        >
                          {f.severity}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-text-secondary leading-relaxed">
                      {f.explanation}
                    </p>

                    {f.agent === 'injection' && (
                      <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-[11px] text-rose-300 flex items-center gap-2">
                        <ShieldAlert className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                        <span className="font-medium">
                          This payload was quarantined: not used as instructions.
                        </span>
                      </div>
                    )}

                    {f.computed_chip && (
                      <div className="pt-0.5">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono bg-surface text-amber-primary border border-amber-primary/30 shadow-2xs">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-primary animate-pulse" />
                          <span>{f.computed_chip}</span>
                        </span>
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-1 text-[11px] gap-2 flex-wrap border-t border-white/6 mt-1">
                      <span className="font-mono text-muted text-[10px] uppercase">
                        {f.check_id}
                      </span>
                      <div className="flex items-center gap-2">
                        {isSpacetime && onSwitchToSpacetime && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onSwitchToSpacetime();
                            }}
                            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-amber-primary/10 text-amber-primary border border-amber-primary/30 hover:bg-amber-primary hover:text-black transition-colors"
                          >
                            <Compass className="w-3 h-3 text-amber-primary" />
                            <span>View on Map</span>
                          </button>
                        )}
                        {hasEvidenceBbox && (
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                              isSelected
                                ? 'bg-amber-primary/15 text-amber-primary border border-amber-primary/40'
                                : 'bg-surface text-muted border border-white/10'
                            }`}
                          >
                            <Crosshair className="w-3 h-3 text-amber-primary" />
                            <span>{isSelected ? 'Focused on Doc' : 'Document Citation'}</span>
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Evidence & Grounding (Two-Corpus RAG) Panel */}
      <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 sm:p-6 shadow-2xs backdrop-blur-md space-y-4">
        <div className="flex items-center justify-between border-b border-white/8 pb-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-amber-primary" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted">
              Evidence & Grounding (Two-Corpus RAG)
            </h3>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
            Policy Clauses & Historical Patterns
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Corpus 1: Policy Basis */}
          <div className="bg-surface-elevated/60 p-4 rounded-xl border border-white/8 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
                <FileCheck className="w-3.5 h-3.5 text-amber-primary" />
                <span>Corpus 1: Policy Basis</span>
              </div>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
                Clause Grounded
              </span>
            </div>

            {policyContext.length > 0 ? (
              <div className="space-y-2.5">
                {policyContext.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-surface border border-white/6 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold font-mono text-amber-primary">
                        {item.ref_id}
                      </span>
                      <span className="text-[10px] font-mono text-muted">
                        {policyId.includes('IRDAI') || policyId.includes('AROGYA')
                          ? 'IRDAI Arogya Sanjeevani'
                          : 'Policy Schedule'}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-text-primary">
                      {item.title}
                    </p>
                    <blockquote className="text-[11px] text-text-secondary italic bg-surface-elevated/40 p-2.5 rounded border-l-2 border-amber-primary">
                      &quot;{item.snippet}&quot;
                    </blockquote>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-muted">
                No policy caps or statutory clause breaches identified.
              </div>
            )}
          </div>

          {/* Corpus 2: Historical Fraud Patterns */}
          <div className="bg-surface-elevated/60 p-4 rounded-xl border border-white/8 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
                <Search className="w-3.5 h-3.5 text-amber-bright" />
                <span>Corpus 2: Similar Past Patterns</span>
              </div>
              <span className="text-[10px] font-mono text-amber-primary bg-amber-primary/10 px-2 py-0.5 rounded-full border border-amber-primary/25">
                Corroboration Only
              </span>
            </div>

            {patternContext.length > 0 ? (
              <div className="space-y-2.5">
                {patternContext.map((p, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-surface border border-white/6 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold font-mono text-amber-primary">
                        {p.ref_id}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
                        {Math.round(p.score * 100)}% match
                      </span>
                    </div>
                    <p className="text-xs font-medium text-text-primary">
                      {p.title}
                    </p>
                    <p className="text-[11px] text-text-secondary leading-relaxed">
                      {p.snippet}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-muted">
                No matching historical patterns found above similarity threshold (≥0.50).
              </div>
            )}

            <div className="p-2.5 rounded-lg bg-amber-primary/5 border border-amber-primary/20 text-[10px] text-text-secondary flex items-start gap-2">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-primary" />
              <span className="leading-relaxed">
                <strong className="font-semibold text-amber-primary">Notice:</strong> Pattern cards are generated from synthetic data only. Retrieved patterns provide investigative corroboration and cannot by themselves reject a claim.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
