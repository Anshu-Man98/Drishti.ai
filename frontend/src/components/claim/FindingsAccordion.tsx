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
        return 'bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/30';
      case 'high':
        return 'bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-500/30';
      case 'medium':
        return 'bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30';
      default:
        return 'bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/30';
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
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 sm:p-6 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
              Flagged Anomalies ({realFindings.length})
            </h3>
          </div>
          <span className="text-[11px] text-slate-400">
            Click any card to highlight on document
          </span>
        </div>

        {realFindings.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">
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
                  className={`p-4 rounded-xl border transition-all cursor-pointer flex items-start gap-3.5 ${
                    isSelected
                      ? 'bg-blue-50/60 dark:bg-sky-950/40 border-blue-500 dark:border-sky-500 shadow-md ring-1 ring-blue-500 dark:ring-sky-500'
                      : 'bg-slate-50/50 dark:bg-slate-950 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700'
                  }`}
                >
                  <AlertTriangle
                    className={`w-4 h-4 shrink-0 mt-0.5 ${
                      f.severity === 'critical'
                        ? 'text-rose-500 dark:text-rose-400'
                        : f.severity === 'high'
                        ? 'text-orange-500 dark:text-orange-400'
                        : 'text-amber-500 dark:text-amber-400'
                    }`}
                  />
                  <div className="space-y-2 flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-bold text-slate-900 dark:text-slate-100 font-mono">
                        {f.title}
                      </span>
                      <div className="flex items-center gap-1.5 shrink-0 flex-wrap justify-end">
                        {f.agent === 'injection' && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-fuchsia-500/10 text-fuchsia-700 dark:text-fuchsia-300 border border-fuchsia-500/30 flex items-center gap-1">
                            <ShieldAlert className="w-3 h-3 text-fuchsia-500" />
                            <span>AI Attack Quarantined</span>
                          </span>
                        )}
                        {f.agent === 'rag' && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30 flex items-center gap-1">
                            <BookOpen className="w-3 h-3 text-amber-500" />
                            <span>Corroborating Pattern</span>
                          </span>
                        )}
                        {f.agent === 'policy' &&
                          f.evidence?.some((e) => e.layer === 'retrieved') && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-500/30 flex items-center gap-1">
                              <BookOpen className="w-3 h-3 text-sky-500" />
                              <span>Clause Grounded</span>
                            </span>
                          )}
                        <span
                          className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border shrink-0 ${getSeverityBadgeClass(
                            f.severity
                          )}`}
                        >
                          {f.severity}
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                      {f.explanation}
                    </p>

                    {f.agent === 'injection' && (
                      <div className="p-3 rounded-lg bg-fuchsia-50 dark:bg-fuchsia-950/40 border border-fuchsia-200 dark:border-fuchsia-800/50 text-[11px] text-fuchsia-800 dark:text-fuchsia-200 flex items-center gap-2">
                        <ShieldAlert className="w-3.5 h-3.5 text-fuchsia-600 dark:text-fuchsia-400 shrink-0" />
                        <span className="font-medium">
                          This payload was quarantined before reaching downstream analysis agents.
                        </span>
                      </div>
                    )}

                    {f.computed_chip && (
                      <div className="pt-0.5">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono bg-white dark:bg-slate-900 text-amber-700 dark:text-amber-300 border border-slate-200 dark:border-slate-700/80 shadow-2xs">
                          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                          <span>{f.computed_chip}</span>
                        </span>
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-1 text-[11px] gap-2 flex-wrap border-t border-slate-200/60 dark:border-slate-800/60 mt-1">
                      <span className="font-mono text-slate-400 text-[10px] uppercase">
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
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/10 text-purple-700 dark:text-purple-300 border border-purple-500/30 hover:bg-purple-500/20 transition-colors"
                          >
                            <Compass className="w-3 h-3 text-purple-500" />
                            <span>View on Map</span>
                          </button>
                        )}
                        {hasEvidenceBbox && (
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                              isSelected
                                ? 'bg-blue-500/10 dark:bg-sky-500/20 text-blue-700 dark:text-sky-300 border border-blue-500/30 dark:border-sky-500/40'
                                : 'bg-slate-100 dark:bg-slate-900 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-800'
                            }`}
                          >
                            <Crosshair className="w-3 h-3 text-blue-500 dark:text-sky-400" />
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
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 sm:p-6 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-sky-500" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300">
              Evidence & Grounding (Two-Corpus RAG)
            </h3>
          </div>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-700 dark:text-sky-400 border border-sky-500/20">
            Policy Clauses & Historical Patterns
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Corpus 1: Policy Basis */}
          <div className="bg-slate-50 dark:bg-slate-950 p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-900 dark:text-slate-200">
                <FileCheck className="w-3.5 h-3.5 text-blue-500" />
                <span>Corpus 1: Policy Basis</span>
              </div>
              <span className="text-[10px] font-mono text-emerald-700 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                Clause Grounded
              </span>
            </div>

            {policyContext.length > 0 ? (
              <div className="space-y-2.5">
                {policyContext.map((item, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold font-mono text-sky-600 dark:text-sky-300">
                        {item.ref_id}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">
                        {policyId.includes('IRDAI') || policyId.includes('AROGYA')
                          ? 'IRDAI Arogya Sanjeevani'
                          : 'Policy Schedule'}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-slate-800 dark:text-slate-200">
                      {item.title}
                    </p>
                    <blockquote className="text-[11px] text-slate-600 dark:text-slate-400 italic bg-slate-50 dark:bg-slate-950/70 p-2.5 rounded border-l-2 border-sky-500">
                      "{item.snippet}"
                    </blockquote>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-400">
                No policy caps or statutory clause breaches identified.
              </div>
            )}
          </div>

          {/* Corpus 2: Historical Fraud Patterns */}
          <div className="bg-slate-50 dark:bg-slate-950 p-4 rounded-xl border border-slate-200 dark:border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-900 dark:text-slate-200">
                <Search className="w-3.5 h-3.5 text-amber-500" />
                <span>Corpus 2: Similar Past Patterns</span>
              </div>
              <span className="text-[10px] font-mono text-amber-700 dark:text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                Corroboration Only
              </span>
            </div>

            {patternContext.length > 0 ? (
              <div className="space-y-2.5">
                {patternContext.map((p, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold font-mono text-amber-600 dark:text-amber-300">
                        {p.ref_id}
                      </span>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                        {Math.round(p.score * 100)}% match
                      </span>
                    </div>
                    <p className="text-xs font-medium text-slate-800 dark:text-slate-200">
                      {p.title}
                    </p>
                    <p className="text-[11px] text-slate-600 dark:text-slate-400 leading-relaxed">
                      {p.snippet}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-400">
                No matching historical patterns found above similarity threshold (≥0.50).
              </div>
            )}

            <div className="p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/20 text-[10px] text-amber-800 dark:text-amber-400/90 flex items-start gap-2">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-500" />
              <span className="leading-relaxed">
                <strong className="font-semibold text-amber-900 dark:text-amber-300">Notice:</strong> Pattern cards are generated from synthetic data only. Retrieved patterns provide investigative corroboration and cannot by themselves reject a claim.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
