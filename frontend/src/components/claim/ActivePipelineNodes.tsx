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
    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-indigo-500" />
          <span>ADK Multi-Agent Specialized Inspection</span>
        </h3>
        <span className="text-[10px] font-mono text-slate-400">
          Hybrid: 60% Multi-Agent + 40% BQML
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
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
              className={`p-3 rounded-lg border transition-all ${
                isRunning
                  ? 'bg-blue-50/50 dark:bg-blue-950/40 border-blue-400 dark:border-blue-500/50 shadow-2xs animate-pulse'
                  : isDone
                  ? count > 0
                    ? 'bg-amber-50/50 dark:bg-amber-950/20 border-amber-300 dark:border-amber-500/30'
                    : 'bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800'
                  : 'bg-slate-50/40 dark:bg-slate-950/40 border-slate-200/50 dark:border-slate-900 opacity-60'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate">
                  {agent.name}
                </span>
                {isRunning ? (
                  <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping shrink-0" />
                ) : isDone ? (
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${count > 0 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                    title={count > 0 ? `${count} flags` : 'Clean'}
                  />
                ) : (
                  <span className="w-2 h-2 rounded-full bg-slate-400 dark:bg-slate-600 shrink-0" />
                )}
              </div>

              <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-1 truncate">
                {agent.role}
              </p>

              <div className="mt-2 text-[10px] font-mono">
                {isRunning ? (
                  <span className="text-blue-600 dark:text-blue-400">running...</span>
                ) : isDone ? (
                  <span
                    className={
                      count > 0
                        ? 'text-amber-700 dark:text-amber-400 font-bold'
                        : 'text-emerald-700 dark:text-emerald-400'
                    }
                  >
                    {count > 0
                      ? `${count} flag${count > 1 ? 's' : ''}`
                      : agent.id === 'ml' && dossier.ml_score
                      ? `${(dossier.ml_score * 100).toFixed(0)}% prob`
                      : 'clean'}
                  </span>
                ) : (
                  <span className="text-slate-400">pending</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
