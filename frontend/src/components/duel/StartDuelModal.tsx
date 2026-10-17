import React, { useState } from 'react';
import { X, Swords, Zap, RefreshCw } from 'lucide-react';

interface StartDuelModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartDuel: (claimId?: string, rounds?: number) => Promise<void>;
  running: boolean;
  modelName?: string;
}

export const StartDuelModal: React.FC<StartDuelModalProps> = ({
  isOpen,
  onClose,
  onStartDuel,
  running,
  modelName = 'gemini-3.5-flash',
}) => {
  const [rounds, setRounds] = useState<number>(3);
  const [claimId, setClaimId] = useState<string>('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onStartDuel(claimId.trim() || undefined, rounds);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-surface border border-white/10 rounded-[20px] w-full max-w-md p-6 shadow-2xl space-y-5 relative">
        <button
          onClick={onClose}
          disabled={running}
          className="absolute top-4 right-4 text-muted hover:text-text-primary p-1.5 rounded-lg hover:bg-white/10 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Swords className="w-5 h-5 text-amber-primary" />
            <h3 className="text-base font-bold text-text-primary">
              Initiate Adversarial Red-Team Duel
            </h3>
          </div>
          <p className="text-xs text-text-secondary">
            Pits an adversarial fraud synthesizer against the Drishti defense agents over multiple mutation rounds.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <span id="duel-rounds-label" className="block font-semibold text-text-secondary mb-1.5">
              Target Duel Rounds (1 to 5)
            </span>
            <div className="flex items-center gap-2" role="group" aria-labelledby="duel-rounds-label">
              {[1, 2, 3, 4, 5].map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRounds(r)}
                  className={`flex-1 py-2 rounded-xl font-bold font-mono text-center transition-all ${
                    rounds === r
                      ? 'bg-amber-primary text-black shadow-md shadow-amber-primary/20'
                      : 'bg-surface-elevated text-muted hover:text-text-primary border border-white/8 hover:border-amber-primary/30'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
            <p className="text-[11px] text-muted mt-1.5">
              Each round tests synthetic modifications to defeat forensic & policy checks.
            </p>
          </div>

          <div>
            <label htmlFor="duel-claim-id" className="block font-semibold text-text-secondary mb-1.5">
              Seed Authentic Claim ID (Optional)
            </label>
            <input
              id="duel-claim-id"
              type="text"
              value={claimId}
              onChange={(e) => setClaimId(e.target.value)}
              placeholder="e.g. CLM-2026-001 (leave empty for random authentic claim)"
              className="w-full bg-surface-elevated border border-white/10 rounded-xl px-3.5 py-2 text-text-primary placeholder-muted font-mono focus:outline-none focus:border-amber-primary focus:ring-1 focus:ring-amber-primary/40 transition-colors"
            />
          </div>

          <div className="p-3.5 rounded-xl bg-surface-elevated/70 border border-white/8 space-y-2">
            <div className="flex items-center gap-1.5 font-bold text-text-primary">
              <Zap className="w-3.5 h-3.5 text-rose-400" />
              <span>Autonomous Red-Team Agent</span>
            </div>
            <p className="text-[11px] text-muted leading-relaxed">
              Powered by <strong className="text-text-primary font-mono">{modelName}</strong>. The model acts as an untrusted claims adversary discovering latent bypass vectors.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2.5 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={running}
              className="px-4 py-2 rounded-xl border border-white/10 bg-surface-elevated hover:bg-surface text-text-secondary hover:text-text-primary text-xs font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={running}
              className="px-4 py-2 rounded-xl bg-amber-primary hover:bg-amber-bright text-black font-semibold text-xs shadow-md shadow-amber-primary/20 transition-all flex items-center gap-1.5 disabled:opacity-50"
            >
              {running ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-black" />
                  <span>Launching Simulation...</span>
                </>
              ) : (
                <>
                  <Swords className="w-3.5 h-3.5" />
                  <span>Begin {rounds}-Round Duel</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
