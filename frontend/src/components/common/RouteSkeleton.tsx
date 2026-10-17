import React from 'react';

interface RouteSkeletonProps {
  label?: string;
}

export const RouteSkeleton: React.FC<RouteSkeletonProps> = ({ label = 'Loading view...' }) => {
  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-pulse" role="status" aria-label={label}>
      {/* Header bar placeholder */}
      <div className="flex items-center justify-between pb-4 border-b border-app-default">
        <div className="space-y-2">
          <div className="h-7 w-56 bg-white/[0.08] rounded-lg"></div>
          <div className="h-4 w-80 bg-white/[0.04] rounded"></div>
        </div>
        <div className="h-10 w-32 bg-white/[0.08] rounded-lg"></div>
      </div>

      {/* Metric Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-5 rounded-2xl border border-app-default bg-app-surface space-y-3 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="h-3 w-20 bg-white/[0.08] rounded"></div>
              <div className="w-8 h-8 rounded-lg bg-amber-primary/10 border border-amber-primary/20"></div>
            </div>
            <div className="h-8 w-24 bg-white/[0.08] rounded"></div>
            <div className="h-3 w-32 bg-white/[0.04] rounded"></div>
          </div>
        ))}
      </div>

      {/* Main View Area Placeholder */}
      <div className="rounded-2xl border border-app-default bg-app-surface p-6 space-y-4 shadow-2xs">
        <div className="flex items-center justify-between">
          <div className="h-5 w-40 bg-white/[0.08] rounded"></div>
          <div className="h-8 w-24 bg-white/[0.04] rounded"></div>
        </div>
        <div className="h-72 w-full bg-white/[0.02] border border-app-default/50 rounded-xl flex items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="w-8 h-8 rounded-full border-2 border-amber-primary border-t-transparent animate-spin shadow-[0_0_12px_rgba(245,165,36,0.3)]" />
            <span className="text-xs font-mono text-app-muted">{label}</span>
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
      className="w-full h-[520px] bg-app-surface rounded-2xl border border-app-default flex flex-col items-center justify-center p-6 text-center animate-pulse"
      role="status"
      aria-label="Loading spacetime map"
    >
      <div className="w-10 h-10 rounded-full border-3 border-amber-primary border-t-transparent animate-spin mb-3 shadow-[0_0_16px_rgba(245,165,36,0.4)]" />
      <p className="text-sm font-medium text-app-primary">Loading spacetime map & trajectory...</p>
      <p className="text-xs text-app-muted mt-1 font-mono">Initializing Google Maps canvas and route geometry</p>
      <span className="sr-only">Loading spacetime map & trajectory...</span>
    </div>
  );
};
