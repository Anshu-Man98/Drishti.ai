import React from 'react';
import { Layers, Cpu, FileText } from 'lucide-react';
import { Dossier } from '../../types';
import { Badge } from '../ui/Badge';
import { ArcGauge } from '../ui/ArcGauge';
import { GlowCard } from '../ui/GlowCard';

interface VerdictSummaryCardProps {
  dossier: Dossier | null;
}

export const VerdictSummaryCard: React.FC<VerdictSummaryCardProps> = ({ dossier }) => {
  const agentScore = dossier
    ? Math.min(
        100,
        dossier.findings
          .filter((f) => f.agent.toLowerCase() !== 'ml')
          .reduce((sum, f) => {
            const w =
              f.severity === 'critical'
                ? 50
                : f.severity === 'high'
                ? 30
                : f.severity === 'medium'
                ? 15
                : f.severity === 'low'
                ? 5
                : 0;
            return sum + w;
          }, 0)
      )
    : 0;

  const isReject = dossier?.verdict === 'reject' || (dossier?.risk_score ?? 0) >= 70;

  return (
    <GlowCard className="p-5 sm:p-6 space-y-5" glow={isReject ? 'none' : 'amber'}>
      {/* Risk Gauge & Verdict Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6 pb-5 border-b border-white/8">
        <div className="flex items-center gap-5">
          {/* ArcGauge for Risk Score */}
          <div className="shrink-0 flex items-center justify-center">
            <ArcGauge
              value={dossier ? dossier.risk_score : 0}
              max={100}
              label={dossier ? 'Risk Score' : 'Unassessed'}
              size="md"
              variant={isReject ? 'danger' : 'amber'}
            />
          </div>

          <div>
            <span className="text-[10px] font-mono uppercase tracking-wider text-muted font-semibold block">
              Adjudication Status
            </span>
            <h2 className="text-lg font-bold text-text-primary tracking-tight">
              Audit Verdict
            </h2>
            <div className="mt-2">
              {dossier ? (
                <Badge
                  variant={
                    dossier.verdict === 'approve'
                      ? 'approve'
                      : dossier.verdict === 'review'
                      ? 'review'
                      : 'reject'
                  }
                  label={
                    dossier.verdict === 'approve'
                      ? 'CLAIM APPROVED'
                      : dossier.verdict === 'review'
                      ? 'NEEDS MANUAL REVIEW'
                      : 'REJECT FRAUDULENT CLAIM'
                  }
                  size="md"
                />
              ) : (
                <span className="text-xs text-muted">
                  Click &quot;Analyze Claim&quot; to trigger multi-agent audit
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Side-by-side Score Attribution Breakdown */}
        {dossier && (
          <div className="flex items-center gap-3">
            <div className="px-4 py-2.5 rounded-xl bg-surface-elevated/70 border border-white/8 text-right shadow-2xs">
              <div className="flex items-center justify-end gap-1.5 text-[10px] uppercase tracking-wider text-muted font-semibold">
                <Layers className="w-3 h-3 text-amber-primary" />
                <span>Agent Score</span>
              </div>
              <div className="mt-0.5 flex items-baseline justify-end gap-1">
                <span className="text-base font-mono font-bold text-text-primary tabular-nums">
                  {agentScore}
                </span>
                <span className="text-[10px] text-muted">/ 100</span>
              </div>
            </div>

            <div className="px-4 py-2.5 rounded-xl bg-surface-elevated/70 border border-white/8 text-right shadow-2xs">
              <div className="flex items-center justify-end gap-1.5 text-[10px] uppercase tracking-wider text-muted font-semibold">
                <Cpu className="w-3 h-3 text-amber-bright" />
                <span>BigQuery ML</span>
              </div>
              <div className="mt-0.5 flex items-baseline justify-end gap-1">
                <span className="text-base font-mono font-bold text-amber-primary tabular-nums">
                  {dossier.ml_score !== null && dossier.ml_score !== undefined
                    ? `${(dossier.ml_score * 100).toFixed(1)}%`
                    : '--'}
                </span>
                <span className="text-[10px] text-muted">prob</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Synthesis & Adjuster Summary */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5 text-amber-primary" />
          <span>Synthesis & Adjuster Summary</span>
        </h3>
        <p className="text-xs sm:text-sm text-text-primary leading-relaxed bg-surface-elevated/50 p-4 rounded-xl border border-white/6">
          {dossier?.summary ||
            'No audit findings generated yet. Run the multi-agent pipeline to examine document forensics, policy limits, cross-insurer submissions, and trajectory spacetime feasibility.'}
        </p>
      </div>
    </GlowCard>
  );
};
