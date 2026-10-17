import React, { useId } from 'react';
import clsx from 'clsx';
import { useMotionProgress } from '../../utils/motion';

export interface ArcGaugeProps {
  value: number;
  min?: number;
  max?: number;
  unit?: string;
  label?: string;
  caption?: string;
  variant?: 'amber' | 'danger' | 'success';
  size?: 'sm' | 'md' | 'lg';
  showTicks?: boolean;
  referenceMarkers?: Array<{ value: number; label: string; color?: string }>;
  className?: string;
  animate?: boolean;
}

/**
 * ArcGauge - The signature Nexa-style meter.
 * Features:
 * - Open arc curve with smooth gradient stroke (bright amber to dim bronze, or crimson for danger)
 * - Glowing circular indicator dot at the current value
 * - Fine radial tick marks along the inner curve
 * - Centered display numeral with tabular figures
 * - Caption / date range / status below
 * - Soft warm ambient glow behind the dial
 * - Fully accessible meter semantics
 */
export const ArcGauge: React.FC<ArcGaugeProps> = ({
  value,
  min = 0,
  max = 100,
  unit = '',
  label,
  caption,
  variant = 'amber',
  size = 'md',
  showTicks = true,
  referenceMarkers = [],
  className,
  animate = true,
}) => {
  const gradientId = useId();
  const filterId = useId();

  const progress = useMotionProgress({ duration: 800, enabled: animate });

  const clampedValue = Math.min(max, Math.max(min, value));
  const range = max - min || 1;
  const targetRatio = (clampedValue - min) / range;
  const currentRatio = animate ? targetRatio * progress : targetRatio;

  // Arc configuration: 210 degree sweep (from 165 deg to 375 deg)
  // Center (cx, cy) = (110, 92), Radius R = 70
  const cx = 110;
  const cy = 92;
  const r = 70;

  const startAngle = 165; // deg
  const endAngle = 375;   // deg (sweep = 210 deg)
  const sweepAngle = endAngle - startAngle;

  const toRad = (deg: number) => (deg * Math.PI) / 180;

  // Polar to Cartesian
  const polarToCartesian = (centerX: number, centerY: number, radius: number, angleInDegrees: number) => {
    const angleInRadians = toRad(angleInDegrees);
    return {
      x: centerX + radius * Math.cos(angleInRadians),
      y: centerY + radius * Math.sin(angleInRadians),
    };
  };

  const startPoint = polarToCartesian(cx, cy, r, startAngle);
  const endPoint = polarToCartesian(cx, cy, r, endAngle);

  // Background arc SVG path
  const bgPath = `M ${startPoint.x} ${startPoint.y} A ${r} ${r} 0 1 1 ${endPoint.x} ${endPoint.y}`;

  // Total circumference of 210 deg arc
  const arcLength = 2 * Math.PI * r * (sweepAngle / 360);
  const strokeDashoffset = arcLength * (1 - currentRatio);

  // End dot coordinates
  const currentAngle = startAngle + sweepAngle * currentRatio;
  const dotCoord = polarToCartesian(cx, cy, r, currentAngle);

  // Generate fine tick marks (15 ticks across arc)
  const ticksCount = 15;
  const ticks = Array.from({ length: ticksCount }, (_, i) => {
    const angle = startAngle + (sweepAngle / (ticksCount - 1)) * i;
    const innerPoint = polarToCartesian(cx, cy, r - 10, angle);
    const outerPoint = polarToCartesian(cx, cy, r - 5, angle);
    const isMajor = i % 2 === 0;
    return {
      id: i,
      x1: innerPoint.x,
      y1: innerPoint.y,
      x2: outerPoint.x,
      y2: outerPoint.y,
      isMajor,
    };
  });

  const sizeClasses = {
    sm: 'w-48 h-36',
    md: 'w-60 h-44',
    lg: 'w-72 h-52',
  }[size];

  const strokeColors = {
    amber: {
      bright: '#FFC15A',
      primary: '#F5A524',
      deep: '#B8741A',
      glow: 'rgba(245, 165, 36, 0.35)',
    },
    danger: {
      bright: '#FB7185',
      primary: '#F43F5E',
      deep: '#BE123C',
      glow: 'rgba(244, 63, 94, 0.40)',
    },
    success: {
      bright: '#34D399',
      primary: '#10B981',
      deep: '#047857',
      glow: 'rgba(16, 185, 129, 0.35)',
    },
  }[variant];

  return (
    <div
      role="meter"
      aria-valuenow={clampedValue}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-label={label || caption || 'Metric Gauge'}
      className={clsx('relative flex flex-col items-center justify-center select-none', className)}
    >
      {/* Ambient background glow behind the arc */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-44 h-32 rounded-full pointer-events-none blur-2xl"
        style={{ background: strokeColors.glow }}
      />

      <svg
        viewBox="0 0 220 160"
        className={clsx('overflow-visible relative z-10', sizeClasses)}
      >
        <defs>
          {/* Arc Gradient */}
          <linearGradient id={gradientId} x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={strokeColors.deep} />
            <stop offset="60%" stopColor={strokeColors.primary} />
            <stop offset="100%" stopColor={strokeColors.bright} />
          </linearGradient>

          {/* Indicator Dot Glow Filter */}
          <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
            <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor={strokeColors.bright} floodOpacity="0.8" />
          </filter>
        </defs>

        {/* Background Track Arc */}
        <path
          d={bgPath}
          fill="none"
          stroke="rgba(255, 255, 255, 0.08)"
          strokeWidth="10"
          strokeLinecap="round"
        />

        {/* Fine Radial Ticks along the inside */}
        {showTicks &&
          ticks.map((t) => (
            <line
              key={t.id}
              x1={t.x1}
              y1={t.y1}
              x2={t.x2}
              y2={t.y2}
              stroke="rgba(255, 255, 255, 0.18)"
              strokeWidth={t.isMajor ? 1.5 : 0.8}
            />
          ))}

        {/* Reference Markers */}
        {referenceMarkers.map((marker, idx) => {
          const mRatio = (Math.min(max, Math.max(min, marker.value)) - min) / range;
          const mAngle = startAngle + sweepAngle * mRatio;
          const mPoint = polarToCartesian(cx, cy, r + 9, mAngle);
          return (
            <circle
              key={idx}
              cx={mPoint.x}
              cy={mPoint.y}
              r="2.5"
              fill={marker.color || strokeColors.bright}
              opacity="0.8"
            />
          );
        })}

        {/* Active Animated Value Arc */}
        <path
          d={bgPath}
          fill="none"
          stroke={`url(#${gradientId})`}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={arcLength}
          strokeDashoffset={strokeDashoffset}
          className={clsx(
            animate && 'transition-[stroke-dashoffset] duration-700 ease-out'
          )}
        />

        {/* Glowing Indicator End-Dot */}
        <g
          className={clsx(
            animate && 'transition-transform duration-700 ease-out'
          )}
        >
          {/* Outer Ring */}
          <circle
            cx={dotCoord.x}
            cy={dotCoord.y}
            r="8"
            fill="rgba(14, 14, 13, 0.9)"
            stroke={strokeColors.bright}
            strokeWidth="2.5"
            filter={`url(#${filterId})`}
          />
          {/* Inner Core */}
          <circle
            cx={dotCoord.x}
            cy={dotCoord.y}
            r="3.5"
            fill={strokeColors.bright}
          />
        </g>

        {/* Centered Large Numeric Display */}
        <text
          x={cx}
          y={cy}
          textAnchor="middle"
          className="fill-app-primary font-light tracking-tight tabular-nums select-none"
          style={{ fontSize: '28px' }}
        >
          {Math.round(clampedValue)}
          {unit && <tspan className="text-sm font-normal fill-app-muted ml-1 font-mono"> {unit}</tspan>}
        </text>

        {/* Centered Subtext / Caption below with ample clearance */}
        {caption && (
          <text
            x={cx}
            y={cy + 18}
            textAnchor="middle"
            className="fill-app-muted font-mono text-[10px] select-none"
          >
            {caption}
          </text>
        )}
      </svg>

      {/* Label under Gauge */}
      {label && (
        <span className="text-xs font-medium uppercase tracking-wider text-app-muted -mt-2">
          {label}
        </span>
      )}
    </div>
  );
};
