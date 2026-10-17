import React, { useEffect, useState } from 'react';
import { Activity, AlertCircle, CheckCircle2, ChevronDown, RefreshCw, XCircle } from 'lucide-react';
import { fetchHealthStatus, HealthStatus } from '../../services/api';

interface SystemHealthPillProps {
  collapsed?: boolean;
}

export const SystemHealthPill: React.FC<SystemHealthPillProps> = ({ collapsed = false }) => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  const checkHealth = React.useCallback(async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const data = await fetchHealthStatus();
      setHealth(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Connection failed';
      setErrorMsg(msg);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    // Re-check every 45 seconds to keep live state accurate
    const timer = setInterval(checkHealth, 45000);
    return () => clearInterval(timer);
  }, [checkHealth]);

  const failingDependencies = health?.dependencies
    ? Object.entries(health.dependencies)
        .filter(([_, dep]) => !dep.ok)
        .map(([name, dep]) => ({ name, ...dep }))
    : [];

  const isFullyHealthy = health && health.status === 'healthy' && health.all_healthy && failingDependencies.length === 0;

  if (collapsed) {
    return (
      <div className="relative group flex justify-center py-2">
        {loading ? (
          <div className="w-2.5 h-2.5 rounded-full bg-slate-400 animate-ping" title="Checking health..." />
        ) : isFullyHealthy ? (
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" title="All Services Healthy" />
        ) : health ? (
          <div className="w-2.5 h-2.5 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50" title={`Degraded: ${failingDependencies.map(f => f.name).join(', ')}`} />
        ) : (
          <div className="w-2.5 h-2.5 rounded-full bg-rose-500 shadow-sm shadow-rose-500/50" title="Backend Disconnected" />
        )}
      </div>
    );
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setShowDetails(!showDetails)}
        className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-xs cursor-pointer hover:border-slate-300 dark:hover:border-slate-700 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          {loading ? (
            <Activity className="w-3.5 h-3.5 text-slate-400 animate-spin shrink-0" />
          ) : isFullyHealthy ? (
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          ) : health ? (
            <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
          ) : (
            <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0" />
          )}

          <div className="truncate">
            {loading ? (
              <span className="text-slate-500 dark:text-slate-400">Checking cloud status...</span>
            ) : isFullyHealthy ? (
              <span className="font-medium text-emerald-700 dark:text-emerald-400">All Cloud Services Live</span>
            ) : health ? (
              <span className="font-medium text-amber-700 dark:text-amber-400">
                {failingDependencies.length} Degraded {failingDependencies.length === 1 ? 'Service' : 'Services'}
              </span>
            ) : (
              <span className="font-medium text-rose-600 dark:text-rose-400">Backend Disconnected</span>
            )}
          </div>
        </div>

        <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${showDetails ? 'rotate-180' : ''}`} />
      </button>

      {/* Expanded Details Popover */}
      {showDetails && (
        <div className="mt-2 p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl text-xs space-y-2.5">
          <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-2">
            <span className="font-semibold text-slate-900 dark:text-slate-100">Service Infrastructure</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                checkHealth();
              }}
              className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded text-slate-500 transition-colors"
              title="Refresh status"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {health ? (
            <div className="space-y-1.5">
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>Active Model:</span>
                <span className="font-mono text-slate-900 dark:text-slate-200">
                  {health.models?.flash || 'Gemini Vertex'}
                </span>
              </div>
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>Environment:</span>
                <span className="font-mono text-slate-900 dark:text-slate-200 capitalize">
                  {health.environment || 'Cloud-Only'}
                </span>
              </div>

              {health.dependencies && (
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-1">
                  <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider">
                    Cloud Subsystems
                  </div>
                  {Object.entries(health.dependencies).map(([depName, info]) => (
                    <div key={depName} className="flex items-center justify-between py-0.5">
                      <span className="capitalize text-slate-700 dark:text-slate-300">{depName}</span>
                      <div className="flex items-center gap-1">
                        {info.ok ? (
                          <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>OK</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-[11px] text-rose-600 dark:text-rose-400 font-medium">
                            <XCircle className="w-3 h-3" />
                            <span>{info.status || 'Failed'}</span>
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="text-rose-600 dark:text-rose-400 flex items-start gap-1.5 py-1">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">Backend Unreachable</p>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
                  {errorMsg || 'Verify backend process is active on port 8000.'}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
