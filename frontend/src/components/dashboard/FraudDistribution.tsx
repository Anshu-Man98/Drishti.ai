import React from 'react';
import { ShieldAlert, Activity, CheckCircle2 } from 'lucide-react';
import { FraudCategoryStat } from '../../types';
import { AgentBadge } from '../common/Badge';

interface FraudDistributionProps {
  categories: FraudCategoryStat[];
  agentBreakdown: Record<string, number>;
  agentClaimsBreakdown?: Record<string, number>;
}

export const FraudDistribution: React.FC<FraudDistributionProps> = ({
  categories,
  agentBreakdown,
  agentClaimsBreakdown,
}) => {
  const totalCategoryFindings = categories.reduce((acc, curr) => acc + curr.count, 0);

  // Sort categories by highest count
  const sortedCategories = [...categories].sort((a, b) => b.count - a.count);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Fraud Category Breakdown */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-rose-500" />
              <span>Fraud Modality Distribution</span>
            </h3>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Aggregated findings categorized across all adjudicated dossiers in BigQuery & Firestore.
            </p>
          </div>
          <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
            {totalCategoryFindings} Violations
          </span>
        </div>

        <div className="space-y-3">
          {sortedCategories.map((item) => {
            const pct = totalCategoryFindings > 0 ? Math.round((item.count / totalCategoryFindings) * 100) : 0;
            return (
              <div key={item.category} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-slate-700 dark:text-slate-300">
                    {item.category}
                  </span>
                  <div className="flex items-center gap-2 font-mono text-[11px]">
                    <span className="font-semibold text-slate-900 dark:text-slate-100">
                      {item.count}
                    </span>
                    <span className="text-slate-400">({pct}%)</span>
                  </div>
                </div>
                {/* Visual Progress Bar */}
                <div className="h-2 w-full rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-600 dark:bg-blue-500 transition-all duration-500"
                    style={{ width: `${Math.max(pct, 3)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Multi-Agent Defense Telemetry */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-5 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
              <Activity className="w-4 h-4 text-indigo-500" />
              <span>Multi-Agent Findings Telemetry</span>
            </h3>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Autonomous findings detected per specialized scrutiny subagent.
            </p>
          </div>
          <span className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Active</span>
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {Object.entries(agentBreakdown).map(([agentName, count]) => {
            const claimsAffected = agentClaimsBreakdown ? agentClaimsBreakdown[agentName] : undefined;
            return (
              <div
                key={agentName}
                className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800/80 space-y-1.5"
              >
                <AgentBadge agent={agentName} />
                <div className="font-mono text-lg font-bold text-slate-900 dark:text-slate-100 tabular-nums">
                  {count}
                </div>
                <div className="text-[10px] text-slate-500 space-y-0.5">
                  <span className="block font-medium">Real Findings</span>
                  {claimsAffected !== undefined && (
                    <span className="block text-slate-400 dark:text-slate-500">
                      {claimsAffected} {claimsAffected === 1 ? 'claim' : 'claims'} flagged
                    </span>
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
