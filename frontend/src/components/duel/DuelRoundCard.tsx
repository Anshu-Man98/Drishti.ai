import React from 'react';
import { ShieldCheck, ShieldAlert, Zap } from 'lucide-react';
import { DuelRound } from '../../types';
import { formatINR } from '../../utils/formatters';
import { Badge } from '../ui/Badge';

interface DuelRoundCardProps {
  round: DuelRound;
  isSelected?: boolean;
  onSelect?: () => void;
  modelName?: string;
}

export const DuelRoundCard: React.FC<DuelRoundCardProps> = ({
  round,
  isSelected,
  onSelect,
  modelName = 'gemini-3.5-flash',
}) => {
  const inflationPct = Math.round((round.inflation_ratio - 1) * 100);

  return (
    <div
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
      aria-pressed={onSelect ? isSelected : undefined}
      onClick={onSelect}
      onKeyDown={
        onSelect
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelect();
              }
            }
          : undefined
      }
      className={`p-4 sm:p-5 rounded-xl border transition-all ${
        onSelect ? 'cursor-pointer' : ''
      } ${
        isSelected
          ? 'bg-amber-primary/10 border-amber-primary/50 shadow-xs ring-1 ring-amber-primary/40'
          : 'bg-surface-elevated/70 border-white/8 hover:border-amber-primary/30'
      }`}
    >
      {/* Top Header: Round Number & Outcome */}
      <div className="flex items-center justify-between gap-2 border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold font-mono px-2 py-0.5 rounded-full bg-white/10 text-text-primary border border-white/10">
            Round #{round.round_number}
          </span>
          <span className="text-xs font-semibold text-text-primary truncate max-w-[280px]">
            {round.tactic}
          </span>
        </div>

        {round.caught ? (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-50 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/20 shrink-0">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-800 dark:text-emerald-400" />
            <span>CAUGHT BY DEFENDER</span>
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-50 dark:bg-rose-500/10 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-500/20 shrink-0 animate-pulse">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-800 dark:text-rose-400" />
            <span>EVADED SHIELD (+{inflationPct}%)</span>
          </span>
        )}
      </div>

      {/* Duel Grid: Fraudster Mutation (Red-Team) vs Defender Detection (FinShield Amber) */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-3.5 text-xs">
        {/* Left: Fraudster Red-Team Move (Crimson) */}
        <div className="p-3.5 rounded-xl bg-surface border border-rose-500/20 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[11px] font-bold text-rose-400 uppercase tracking-wide">
              <Zap className="w-3.5 h-3.5 text-rose-400" />
              <span>Fraudster Mutation ({modelName})</span>
            </div>
            <span className="font-mono text-[11px] text-rose-400 font-bold">
              +{inflationPct}% Payout
            </span>
          </div>

          <p className="text-text-secondary leading-relaxed text-[11px]">
            {round.rationale}
          </p>

          <div className="flex items-center justify-between text-[11px] font-mono pt-1 text-muted border-t border-white/6">
            <span>Baseline: {formatINR(round.baseline_amount)}</span>
            <span className="font-bold text-text-primary">
              Claimed: {formatINR(round.total_claimed)}
            </span>
          </div>
        </div>

        {/* Right: Defender Multi-Agent Interception (Amber) */}
        <div className="p-3.5 rounded-xl bg-surface border border-amber-primary/25 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-[11px] font-bold text-amber-primary uppercase tracking-wide">
              <ShieldCheck className="w-3.5 h-3.5 text-amber-primary" />
              <span>FinShield Multi-Agent Response</span>
            </div>
            <Badge
              variant={
                round.verdict.toLowerCase().includes('reject')
                  ? 'reject'
                  : round.verdict.toLowerCase().includes('review')
                  ? 'review'
                  : 'approve'
              }
              label={round.verdict.toUpperCase()}
              size="sm"
            />
          </div>

          <div className="flex items-baseline justify-between text-[11px] text-muted">
            <span>Risk Score:</span>
            <span className="font-mono font-bold text-text-primary">
              {Math.round(round.risk_score)} / 100
            </span>
          </div>

          {/* Catching Check IDs Chips */}
          <div className="pt-1 border-t border-white/6">
            <span className="text-[10px] text-muted block mb-1">
              {round.caught ? 'Triggered Interception Checks:' : 'Defense Result:'}
            </span>
            {round.catching_check_ids.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {round.catching_check_ids.map((chk, i) => (
                  <span
                    key={i}
                    className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/20"
                  >
                    {chk}
                  </span>
                ))}
              </div>
            ) : (
              <span className="text-[11px] text-rose-800 dark:text-rose-400 font-medium">
                No deterministic checks triggered. Fraudster slipped through baseline limits.
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
