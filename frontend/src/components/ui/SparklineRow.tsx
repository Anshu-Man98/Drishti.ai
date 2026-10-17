import React, { useId } from 'react';
import clsx from 'clsx';

export interface SparklineRowProps {
  label: string;
  data: number[];
  valueText: string;
  sublabel?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  className?: string;
}

/**
 * SparklineRow - Nexa "Malware type trends" style row.
 * Features:
 * - Label on the left
 * - Compact glowing amber sparkline in the middle
 * - Percentage / value on the right
 * - Thin divider
 */
export const SparklineRow: React.FC<SparklineRowProps> = ({
  label,
  data,
  valueText,
  sublabel,
  icon,
  className,
}) => {
  const filterId = useId();

  // Sparkline dimensions
  const width = 100;
  const height = 24;
  const padding = 2;

  let pathD = '';
  if (data && data.length > 1) {
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min === 0 ? 1 : max - min;

    const points = data.map((val, i) => {
      const x = padding + (i / (data.length - 1)) * (width - padding * 2);
      const y = height - padding - ((val - min) / range) * (height - padding * 2);
      return { x, y };
    });

    pathD = points.reduce((acc, p, i) => {
      return i === 0 ? `M ${p.x.toFixed(1)} ${p.y.toFixed(1)}` : `${acc} L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
    }, '');
  }

  return (
    <div
      className={clsx(
        'flex items-center justify-between py-2.5 px-1 border-b border-white/[0.06] last:border-b-0 hover:bg-white/[0.02] transition-colors',
        className
      )}
    >
      {/* Left: Label & Icon */}
      <div className="flex items-center gap-2.5 min-w-[110px]">
        {icon && <span className="text-amber-primary/80">{icon}</span>}
        <div>
          <div className="text-xs font-medium text-app-primary tracking-tight">{label}</div>
          {sublabel && <div className="text-[10px] text-app-muted font-mono">{sublabel}</div>}
        </div>
      </div>

      {/* Middle: Glowing Amber Sparkline */}
      <div className="flex-1 max-w-[120px] mx-3">
        {pathD ? (
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-6 overflow-visible">
            <defs>
              <filter id={filterId} x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="glow" />
                <feMerge>
                  <feMergeNode in="glow" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            {/* Soft Glow Path */}
            <path
              d={pathD}
              fill="none"
              stroke="#FFC15A"
              strokeWidth="2"
              opacity="0.4"
              filter={`url(#${filterId})`}
            />
            {/* Core Path */}
            <path
              d={pathD}
              fill="none"
              stroke="#F5A524"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : (
          <div className="w-full h-[1px] bg-white/[0.1]" />
        )}
      </div>

      {/* Right: Percentage Value */}
      <div className="text-xs font-mono font-medium text-app-primary text-right tabular-nums min-w-[50px]">
        {valueText}
      </div>
    </div>
  );
};
