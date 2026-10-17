import React from 'react';
import { Layers } from 'lucide-react';
import { Dossier } from '../../types';

interface ActivePipelineNodesProps {
  dossier: Dossier | null;
  analyzing: boolean;
}

export const ActivePipelineNodes: React.FC<ActivePipelineNodesProps> = ({
  dossier,
  analyzing,
}) => {
  const AGENT_NODES = [
    { id: 'forensics', name: 'Forensics', role: 'Metadata & Font ELA' },
    { id: 'policy', name: 'Policy & Math', role: 'Caps & Arithmetic' },
    { id: 'crossref', name: 'Cross-Ref', role: 'Warehouse Duplicates' },
    { id: 'spacetime', name: 'Spacetime', role: 'Transit Feasibility' },
    { id: 'ml', name: 'BigQuery ML', role: 'Boosted Trees & Outliers' },
    { id: 'injection', name: 'Prompt Shield', role: 'Poisoned-Bill Defense' },
    { id: 'provenance', name: 'Provenance', role: 'Ed25519 Dual Watermark' },
    { id: 'rag', name: 'Pattern RAG', role: 'Dual-Corpus Retrieval' },
  ];

  return (
    <div className="bg-app-surface border border-app-default rounded-[20px] p-5 shadow-2xs backdrop-blur-md space-y-4">
      <div className="flex items-center justify-between border-b border-app-default pb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-app-muted flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-amber-primary" />
          <span>ADK Multi-Agent Specialized Inspection</span>
        </h3>
        <span className="text-[10px] font-mono text-amber-800 dark:text-amber-primary font-medium">
          Hybrid: 60% Multi-Agent + 40% BQML
        </span>
      </div>

      <div className="relative">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 relative z-10">
          {AGENT_NODES.map((agent) => {
            const agentFindings =
              dossier?.findings?.filter(
                (f) =>
                  f.agent.toLowerCase() === agent.id.toLowerCase() &&
                  f.severity?.toLowerCase() !== 'info' &&
                  !f.check_id.toLowerCase().includes('ungrounded')
              ) || [];
            const count = agentFindings.length;
            const isDone = !!dossier;
            const isRunning = analyzing;

            return (
              <div
                key={agent.id}
                className={`p-3 rounded-xl border transition-all ${
                  isRunning
                    ? 'bg-amber-primary/10 border-amber-primary/50 shadow-sm shadow-amber-primary/20 ring-1 ring-amber-primary/40 animate-pulse'
                    : isDone
                    ? count > 0
                      ? 'bg-amber-primary/10 border-amber-primary/40 hover:border-amber-primary/60'
                      : 'bg-app-surface-elevated border-app-default hover:border-amber-primary/30'
                    : 'bg-app-surface-elevated/40 border-app-faint opacity-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-app-primary truncate">
                    {agent.name}
                  </span>
                  {isRunning ? (
                    <span className="w-2 h-2 rounded-full bg-amber-primary animate-ping shrink-0" />
                  ) : isDone ? (
                    <span
                      className={`w-2 h-2 rounded-full shrink-0 ${
                        count > 0 ? 'bg-amber-primary shadow-xs shadow-amber-primary/60' : 'bg-emerald-500'
                      }`}
                      title={count > 0 ? `${count} flags` : 'Clean'}
                    />
                  ) : (
                    <span className="w-2 h-2 rounded-full bg-app-faint shrink-0" />
                  )}
                </div>

                <p className="text-[10px] text-app-muted mt-1 truncate">
                  {agent.role}
                </p>

                <div className="mt-2 text-[10px] font-mono">
                  {isRunning ? (
                    <span className="text-amber-800 dark:text-amber-primary font-medium">auditing...</span>
                  ) : isDone ? (
                    <span
                      className={
                        count > 0
                          ? 'text-amber-800 dark:text-amber-primary font-bold'
                          : 'text-emerald-800 dark:text-emerald-400 font-semibold'
                      }
                    >
                      {count > 0
                        ? `${count} flag${count > 1 ? 's' : ''}`
                        : agent.id === 'ml' && dossier.ml_score
                        ? `${(dossier.ml_score * 100).toFixed(0)}% prob`
                        : 'clean'}
                    </span>
                  ) : (
                    <span className="text-app-faint">pending</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
