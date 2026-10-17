import React from 'react';
import { X, ShieldCheck, Scale, Cpu, AlertTriangle } from 'lucide-react';
import { GlowCard } from '../ui/GlowCard';

interface ScoringModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ScoringModal: React.FC<ScoringModalProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-200">
      <GlowCard className="w-full max-w-xl p-6 relative border-amber-primary/30 max-h-[90vh] overflow-y-auto">
        {/* Close Button */}
        <button
          onClick={onClose}
          aria-label="Close scoring guide modal"
          className="absolute top-4 right-4 p-1.5 rounded-lg text-app-muted hover:text-app-primary hover:bg-white/[0.06] transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-amber-primary/12 border border-amber-primary/30 flex items-center justify-center text-amber-primary">
            <Scale className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-app-primary tracking-tight">How FinShield Scoring Works</h2>
            <p className="text-xs text-app-muted font-mono">Calibrated Multi-Agent & BigQuery ML Pipeline</p>
          </div>
        </div>

        {/* Content */}
        <div className="space-y-4 text-xs text-app-secondary leading-relaxed">
          <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
            <div className="font-semibold text-app-primary flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-amber-primary" />
              <span>1. Hybrid Risk Score Blend</span>
            </div>
            <p className="font-mono text-[11px] text-amber-bright/90 bg-black/40 p-2 rounded-lg border border-amber-primary/20">
              Risk Score = round(0.6 × Agent Score + 40 × ML Probability)
            </p>
            <p className="text-app-muted">
              Agent findings contribute 60% of the risk weight; BigQuery ML (logistic regression model trained on clinical & billing corridors) contributes 40%.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
            <div className="font-semibold text-app-primary flex items-center gap-1.5">
              <Scale className="w-3.5 h-3.5 text-emerald-400" />
              <span>2. Widened Regional Benchmark Corridors</span>
            </div>
            <p className="text-app-muted">
              Rather than treating synthetic percentiles as hard ceilings, diagnosis and line-item thresholds use a widened tolerance band (+15% regional buffer or 3× MAD). Normal city price variations remain in <span className="text-emerald-400 font-semibold">APPROVE</span>.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
            <div className="font-semibold text-app-primary flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-primary" />
              <span>3. Monotonic Inflation Guardrail</span>
            </div>
            <p className="text-app-muted">
              Excess charges trigger non-decreasing penalties across the entire inflation ladder (+10% &lt; +20% &lt; +28% &lt; +40% &lt; +60%). Excess &ge; +20% escalates to <span className="text-amber-primary font-semibold">REVIEW</span> or <span className="text-rose-400 font-semibold">REJECT</span>.
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/[0.06] space-y-1.5">
            <div className="font-semibold text-app-primary flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-blue-400" />
              <span>4. Fail-Loud Truth Policy</span>
            </div>
            <p className="text-app-muted">
              No simulated or canned fallbacks. All findings are grounded in document provenance and verified against BigQuery warehouse registries.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-white/[0.08] flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold bg-amber-primary text-black hover:bg-amber-bright transition-colors cursor-pointer"
          >
            Understood
          </button>
        </div>
      </GlowCard>
    </div>
  );
};
