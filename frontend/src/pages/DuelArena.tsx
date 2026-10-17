import React, { useEffect, useState, useRef } from 'react';
import {
  Swords,
  ShieldCheck,
  ShieldAlert,
  Zap,
  BookOpen,
  RefreshCw,
  Sparkles,
  Trophy,
  ArrowRight,
  Plus,
} from 'lucide-react';
import { DuelResult, LearnedPattern } from '../types';
import { startDuel, fetchDuelStatus, fetchLearnedPatterns, fetchHealthStatus } from '../services/api';
import { DuelRoundCard } from '../components/duel/DuelRoundCard';
import { LearnedPatternsList } from '../components/duel/LearnedPatternsList';
import { StartDuelModal } from '../components/duel/StartDuelModal';
import { PillTabs } from '../components/ui/PillTabs';
import { GlowCard } from '../components/ui/GlowCard';
import { formatINR } from '../utils/formatters';

export const DuelArena: React.FC = () => {
  const [activeDuel, setActiveDuel] = useState<DuelResult | null>(null);
  const [learnedPatterns, setLearnedPatterns] = useState<LearnedPattern[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [runningDuel, setRunningDuel] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [duelError, setDuelError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'arena' | 'patterns'>('arena');
  const [configuredModel, setConfiguredModel] = useState<string>('gemini-3.5-flash');

  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, []);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [pats, health] = await Promise.all([
        fetchLearnedPatterns(),
        fetchHealthStatus().catch(() => null),
      ]);
      setLearnedPatterns(pats);
      if (health?.models?.pro) {
        setConfiguredModel(health.models.pro);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load learned evasion patterns.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  const pollDuel = (duelId: string) => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
    }

    const pollInterval = setInterval(async () => {
      try {
        const st = await fetchDuelStatus(duelId);
        setActiveDuel((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            rounds: st.rounds || [],
            status: st.status,
            winning_side: st.winning_side || prev.winning_side,
            learned_pattern: st.learned_pattern || prev.learned_pattern,
          };
        });

        if (st.status === 'completed') {
          clearInterval(pollInterval);
          pollTimerRef.current = null;
          setRunningDuel(false);
          const updatedPats = await fetchLearnedPatterns();
          setLearnedPatterns(updatedPats);
        } else if (st.status === 'failed') {
          clearInterval(pollInterval);
          pollTimerRef.current = null;
          setRunningDuel(false);
          setDuelError(st.error || 'Adversarial duel execution failed');
        }
      } catch (err: any) {
        console.warn('Polling duel status error:', err);
      }
    }, 1500);

    pollTimerRef.current = pollInterval;
  };

  if (loading && learnedPatterns.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-24 text-center text-text-muted space-y-4">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-amber-primary" />
        <p className="text-sm font-medium">Loading adversarial duel arena & learned evasion signatures...</p>
      </div>
    );
  }

  const handleStartDuel = async (claimId?: string, rounds: number = 3) => {
    try {
      setRunningDuel(true);
      setError(null);
      setDuelError(null);
      setIsModalOpen(false);
      setActiveTab('arena');

      const result = await startDuel(claimId, rounds);
      setActiveDuel(result);

      if (result.status === 'running') {
        pollDuel(result.duel_id);
      } else {
        setRunningDuel(false);
        const updatedPats = await fetchLearnedPatterns();
        setLearnedPatterns(updatedPats);
      }
    } catch (err: any) {
      setError(err.message || 'Adversarial duel execution failed.');
      setRunningDuel(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text-primary flex items-center gap-2">
            <Swords className="w-6 h-6 text-amber-primary" />
            <span>Adversarial Duel Arena</span>
          </h1>
          <p className="text-xs sm:text-sm text-text-muted mt-1">
            Automated red-team simulator ({configuredModel}) challenging the 8-agent Drishti scrutiny pipeline to expose evasion blindspots.
          </p>
        </div>

        {/* Action Controls & Tab Switcher */}
        <div className="flex items-center gap-3 flex-wrap">
          <PillTabs
            tabs={[
              { id: 'arena', label: 'Duel Arena' },
              { id: 'patterns', label: `Learned Patterns (${learnedPatterns.length})` },
            ]}
            activeTab={activeTab}
            onChange={(tab) => setActiveTab(tab as 'arena' | 'patterns')}
            size="sm"
          />

          <button
            onClick={() => setIsModalOpen(true)}
            disabled={runningDuel}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-primary hover:bg-amber-bright text-black text-xs font-bold transition-all shadow-md shadow-amber-primary/20 disabled:opacity-50"
          >
            {runningDuel ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Simulating Rounds...</span>
              </>
            ) : (
              <>
                <Plus className="w-3.5 h-3.5" />
                <span>Launch New Duel</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* KPI Telemetry Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <GlowCard className="p-4 space-y-1">
          <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-text-muted">
            <BookOpen className="w-3 h-3 text-amber-primary" />
            <span>Learned Evasion Patterns</span>
          </div>
          <div className="text-xl font-bold font-mono text-text-primary tabular-nums">
            {learnedPatterns.length}
          </div>
          <p className="text-[10px] text-text-faint">Indexed in Two-Corpus RAG</p>
        </GlowCard>

        <GlowCard className="p-4 space-y-1">
          <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-text-muted">
            <ShieldCheck className="w-3 h-3 text-emerald-700 dark:text-emerald-400" />
            <span>Defender Multi-Agent</span>
          </div>
          <div className="text-xl font-bold font-mono text-emerald-700 dark:text-emerald-400">
            8 Specialist Agents
          </div>
          <p className="text-[10px] text-text-faint">Continuous Active Defense</p>
        </GlowCard>

        <GlowCard className="p-4 space-y-1">
          <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-text-muted">
            <Zap className="w-3 h-3 text-rose-700 dark:text-rose-400" />
            <span>Adversarial Red-Team</span>
          </div>
          <div className="text-xl font-bold font-mono text-rose-700 dark:text-rose-400 truncate">
            {configuredModel}
          </div>
          <p className="text-[10px] text-text-faint">Autonomous Invoice Mutator</p>
        </GlowCard>

        <GlowCard className="p-4 space-y-1">
          <div className="flex items-center gap-1.5 text-[10px] uppercase font-bold text-text-muted">
            <Trophy className="w-3 h-3 text-amber-primary" />
            <span>Active Session</span>
          </div>
          <div className="text-xl font-bold font-mono text-amber-primary truncate">
            {activeDuel ? activeDuel.duel_id : 'Idle'}
          </div>
          <p className="text-[10px] text-text-faint">
            {activeDuel ? `${activeDuel.rounds.length} rounds fought` : 'Ready to launch'}
          </p>
        </GlowCard>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400 flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Content Area */}
      {activeTab === 'arena' ? (
        activeDuel ? (
          <div className="space-y-5">
            {/* Duel Result Summary Card */}
            <GlowCard glow corner="top-right" className="p-5 sm:p-6 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-white/6 pb-4">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <h2 className="text-base font-bold text-text-primary font-mono">
                      Duel {activeDuel.duel_id}
                    </h2>
                    <span className="text-xs px-2 py-0.5 rounded font-mono bg-amber-primary/10 text-amber-primary border border-amber-primary/20">
                      Base: {activeDuel.base_claim_id}
                    </span>
                  </div>
                  <p className="text-xs text-text-muted">
                    Baseline Authentic Claim Value: {formatINR(activeDuel.baseline_amount)}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {activeDuel.winning_side === 'defender' ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-emerald-50 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-500/20">
                      <ShieldCheck className="w-4 h-4 text-emerald-800 dark:text-emerald-400" />
                      <span>DEFENDER VICTORY (All Evasions Caught)</span>
                    </span>
                  ) : activeDuel.status === 'running' ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-amber-500/10 dark:bg-amber-primary/10 text-amber-800 dark:text-amber-primary border border-amber-300 dark:border-amber-primary/20 animate-pulse">
                      <RefreshCw className="w-4 h-4 text-amber-800 dark:text-amber-primary animate-spin" />
                      <span>SIMULATING ROUNDS...</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold bg-rose-50 dark:bg-rose-500/10 text-rose-800 dark:text-rose-400 border border-rose-300 dark:border-rose-500/20 animate-pulse">
                      <ShieldAlert className="w-4 h-4 text-rose-800 dark:text-rose-400" />
                      <span>FRAUDSTER EVADED SHIELD (Defense Learned)</span>
                    </span>
                  )}
                </div>
              </div>

              {/* Newly Learned Pattern Callout (if evaded) */}
              {activeDuel.learned_pattern && (
                <div className="p-4 rounded-xl bg-amber-primary/10 border border-amber-primary/30 text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 font-bold text-amber-primary">
                      <Sparkles className="w-4 h-4 text-amber-primary" />
                      <span>Newly Discovered Evasion Pattern Cataloged</span>
                    </div>
                    <span className="font-mono text-[10px] text-amber-bright">
                      {activeDuel.learned_pattern.pattern_id}
                    </span>
                  </div>
                  <p className="text-text-primary leading-relaxed">
                    {activeDuel.learned_pattern.narrative}
                  </p>
                  <p className="text-[11px] text-amber-primary/80 font-mono">
                    Signatures: {activeDuel.learned_pattern.feature_signatures}
                  </p>
                </div>
              )}

              {/* Rounds Accordion List */}
              <div className="space-y-3 pt-1">
                <h3 className="text-xs font-bold uppercase tracking-wider text-text-muted">
                  Round-by-Round Mutation & Defense Telemetry ({activeDuel.rounds.length} / {activeDuel.max_rounds})
                </h3>

                <div className="space-y-3">
                  {activeDuel.rounds.map((round) => (
                    <DuelRoundCard key={round.round_number} round={round} modelName={configuredModel} />
                  ))}

                  {/* Active In-Progress Round Card */}
                  {activeDuel.status === 'running' && (
                    <div className="p-4 sm:p-5 rounded-xl border border-dashed border-amber-primary/30 bg-amber-primary/5 flex items-center justify-between gap-4 animate-in fade-in duration-200">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-amber-primary/10 flex items-center justify-center shrink-0">
                          <RefreshCw className="w-4 h-4 text-amber-primary animate-spin" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold font-mono px-2 py-0.5 rounded bg-amber-primary/15 text-amber-bright">
                              Round #{activeDuel.rounds.length + 1} of {activeDuel.max_rounds}
                            </span>
                            <span className="text-xs font-semibold text-text-primary">
                              Adversarial Mutation Running...
                            </span>
                          </div>
                          <p className="text-[11px] text-text-muted mt-1">
                            {configuredModel} is mutating line items to test Drishti scrutiny boundaries.
                          </p>
                        </div>
                      </div>
                      <span className="text-xs font-mono font-bold text-amber-primary animate-pulse shrink-0">
                        Simulating...
                      </span>
                    </div>
                  )}

                  {/* Explicit Error Card on Round / Duel Failure */}
                  {activeDuel.status === 'failed' && (
                    <div className="p-4 sm:p-5 rounded-xl border border-rose-500/30 bg-rose-500/10 space-y-3 animate-in fade-in duration-200">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-rose-400 font-bold text-xs">
                          <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
                          <span>Adversarial Simulation Failed</span>
                        </div>
                        <button
                          onClick={() => handleStartDuel(activeDuel.base_claim_id, activeDuel.max_rounds)}
                          className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-colors shadow-2xs"
                        >
                          Retry Duel
                        </button>
                      </div>
                      <p className="text-xs text-rose-400 font-mono">
                        {duelError || 'Adversarial simulation halted due to an unexpected error.'}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </GlowCard>
          </div>
        ) : (
          /* Empty State: Ready to Duel */
          <GlowCard glow corner="top-left" className="p-10 text-center max-w-xl mx-auto space-y-4">
            <div className="w-12 h-12 rounded-xl bg-amber-primary/10 border border-amber-primary/20 flex items-center justify-center mx-auto text-amber-primary">
              <Swords className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-base font-bold text-text-primary">
                Ready for Adversarial Red-Teaming
              </h3>
              <p className="text-xs text-text-muted leading-relaxed">
                Launch a live duel where {configuredModel} attempts to inflate medical bills and bypass Drishti's 8-agent
                scrutiny pipeline. When evasion occurs, defense patterns are immediately immunized.
              </p>
            </div>
            <button
              onClick={() => setIsModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-5 py-2.5 rounded-xl bg-amber-primary hover:bg-amber-bright text-black text-xs font-bold transition-all shadow-md shadow-amber-primary/20"
            >
              <Swords className="w-4 h-4" />
              <span>Launch 3-Round Duel</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </GlowCard>
        )
      ) : (
        /* Patterns Library Tab */
        <LearnedPatternsList patterns={learnedPatterns} />
      )}

      {/* Start Duel Modal */}
      <StartDuelModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onStartDuel={handleStartDuel}
        running={runningDuel}
        modelName={configuredModel}
      />
    </div>
  );
};
