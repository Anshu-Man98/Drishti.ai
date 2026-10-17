import React from 'react';

interface RouteSkeletonProps {
  label?: string;
}

export const RouteSkeleton: React.FC<RouteSkeletonProps> = ({ label = 'Loading view...' }) => {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-pulse" role="status" aria-label={label}>
      {/* Header bar placeholder */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
        <div className="space-y-2">
          <div className="h-7 w-56 bg-slate-200 dark:bg-slate-800 rounded-lg"></div>
          <div className="h-4 w-80 bg-slate-100 dark:bg-slate-800/60 rounded"></div>
        </div>
        <div className="h-10 w-32 bg-slate-200 dark:bg-slate-800 rounded-lg"></div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 space-y-3">
            <div className="flex items-center justify-between">
              <div className="h-3 w-20 bg-slate-200 dark:bg-slate-800 rounded"></div>
              <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800"></div>
            </div>
            <div className="h-8 w-24 bg-slate-200 dark:bg-slate-800 rounded"></div>
            <div className="h-3 w-32 bg-slate-100 dark:bg-slate-800/50 rounded"></div>
          </div>
        ))}
      </div>

      {/* Main View Area Placeholder */}
      <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/60 p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="h-5 w-40 bg-slate-200 dark:bg-slate-800 rounded"></div>
          <div className="h-8 w-24 bg-slate-100 dark:bg-slate-800 rounded"></div>
        </div>
        <div className="h-72 w-full bg-slate-100 dark:bg-slate-800/40 rounded-lg flex items-center justify-center">
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
            <span className="text-xs font-mono text-slate-500 dark:text-slate-400">{label}</span>
          </div>
        </div>
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
};

export const MapSkeleton: React.FC = () => {
  return (
    <div
      className="w-full h-[520px] bg-slate-100 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 flex flex-col items-center justify-center p-6 text-center animate-pulse"
      role="status"
      aria-label="Loading spacetime map"
    >
      <div className="w-10 h-10 rounded-full border-3 border-indigo-500 border-t-transparent animate-spin mb-3" />
      <p className="text-sm font-medium text-slate-700 dark:text-slate-300">Loading spacetime map & trajectory...</p>
      <p className="text-xs text-slate-500 dark:text-slate-500 mt-1">Initializing Google Maps canvas and route geometry</p>
      <span className="sr-only">Loading spacetime map & trajectory...</span>
    </div>
  );
};
