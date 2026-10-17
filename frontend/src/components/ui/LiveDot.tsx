import React from 'react';
import clsx from 'clsx';

export interface LiveDotProps {
  color?: 'amber' | 'emerald' | 'rose' | 'muted';
  pulse?: boolean;
  size?: 'sm' | 'md';
  className?: string;
  label?: string;
}

/**
 * LiveDot - Glowing live status indicator dot with gentle pulse animation.
 */
export const LiveDot: React.FC<LiveDotProps> = ({
  color = 'amber',
  pulse = true,
  size = 'md',
  className,
  label,
}) => {
  const colorMap = {
    amber: {
      core: 'bg-amber-primary',
      ring: 'bg-amber-primary/40',
      glow: 'shadow-[0_0_8px_rgba(245,165,36,0.6)]',
    },
    emerald: {
      core: 'bg-emerald-500',
      ring: 'bg-emerald-500/40',
      glow: 'shadow-[0_0_8px_rgba(16,185,129,0.6)]',
    },
    rose: {
      core: 'bg-rose-500',
      ring: 'bg-rose-500/40',
      glow: 'shadow-[0_0_8px_rgba(244,63,94,0.6)]',
    },
    muted: {
      core: 'bg-white/40',
      ring: 'bg-white/20',
      glow: '',
    },
  }[color];

  const sizeClasses = {
    sm: 'w-1.5 h-1.5',
    md: 'w-2 h-2',
  }[size];

  const ringSizeClasses = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
  }[size];

  return (
    <span className={clsx('relative inline-flex items-center gap-1.5', className)}>
      <span className="relative flex items-center justify-center">
        {pulse && (
          <span
            className={clsx(
              'animate-ping absolute inline-flex rounded-full opacity-75',
              ringSizeClasses,
              colorMap.ring
            )}
          />
        )}
        <span
          className={clsx(
            'relative inline-flex rounded-full',
            sizeClasses,
            colorMap.core,
            colorMap.glow
          )}
        />
      </span>
      {label && <span className="text-[11px] font-mono text-app-muted">{label}</span>}
    </span>
  );
};
