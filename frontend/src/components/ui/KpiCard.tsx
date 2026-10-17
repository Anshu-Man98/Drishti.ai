import React from 'react';
import { ArrowUpRight } from 'lucide-react';
import clsx from 'clsx';
import { GlowCard } from './GlowCard';
import { useCountUp } from '../../utils/motion';
import { formatIndianNumber } from '../../utils/formatters';

export interface KpiCardProps {
  label: string;
  value: number | string;
  prefix?: string;
  suffix?: string;
  icon?: React.ReactNode;
  contextText?: string;
  contextTone?: 'positive' | 'negative' | 'neutral' | 'amber';
  cornerGlow?: boolean;
  href?: string;
  onClick?: () => void;
  className?: string;
  decimals?: number;
  animate?: boolean;
}

/**
 * KpiCard - Adfonic style hero KPI card.
 * Features:
 * - Circle icon on top-left
 * - Muted uppercase label
 * - Diagonal link arrow on top-right (↗)
 * - Very large light-weight numeral with count-up animation
 * - Contextual delta/status line at bottom
 * - Subtle amber corner glow
 */
export const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  prefix = '',
  suffix = '',
  icon,
  contextText,
  contextTone = 'neutral',
  cornerGlow = true,
  href,
  onClick,
  className,
  decimals = 0,
  animate = true,
}) => {
  const isNumeric = typeof value === 'number';
  const targetNum = isNumeric ? (value as number) : 0;
  const animatedNum = useCountUp(targetNum, {
    duration: 800,
    enabled: animate && isNumeric,
    startValue: 0,
  });

  const displayNum = animate && isNumeric ? animatedNum : targetNum;

  const formattedValue = isNumeric
    ? formatIndianNumber(displayNum, decimals)
    : String(value);

  const contextToneClasses = {
    positive: 'text-emerald-400',
    negative: 'text-rose-400',
    amber: 'text-amber-400',
    neutral: 'text-app-muted',
  }[contextTone];

  const content = (
    <div className="p-5 sm:p-6 flex flex-col justify-between h-full relative z-10">
      {/* Top Header Row */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          {icon && (
            <div className="w-8 h-8 rounded-full border border-white/[0.1] bg-white/[0.04] flex items-center justify-center text-amber-primary">
              {icon}
            </div>
          )}
          <span className="text-xs font-medium uppercase tracking-wider text-app-muted">
            {label}
          </span>
        </div>
        <div className="text-app-muted/60 hover:text-amber-primary transition-colors">
          <ArrowUpRight className="w-4 h-4" />
        </div>
      </div>

      {/* Main Numeral */}
      <div className="my-1">
        <div className="text-2xl sm:text-3xl lg:text-3xl xl:text-4xl font-light tracking-tight text-app-primary tabular-nums whitespace-nowrap flex items-baseline gap-0.5">
          {prefix && (
            <span className="text-xl sm:text-2xl lg:text-2xl xl:text-3xl font-normal opacity-90 select-none">
              {prefix}
            </span>
          )}
          <span>{formattedValue}</span>
          {suffix && <span className="text-sm font-normal text-app-muted ml-0.5">{suffix}</span>}
        </div>
      </div>

      {/* Footer Context / Delta Line */}
      {contextText && (
        <div className={clsx('text-xs mt-3 flex items-center gap-1.5 font-medium', contextToneClasses)}>
          {contextText}
        </div>
      )}
    </div>
  );

  return (
    <GlowCard
      cornerGlow={cornerGlow}
      interactive={Boolean(href || onClick)}
      onClick={onClick}
      className={clsx('overflow-hidden min-h-[140px]', className)}
    >
      {href ? (
        <a href={href} className="block h-full focus:outline-none" aria-label={`${label}: ${prefix}${formattedValue}${suffix}`}>
          {content}
        </a>
      ) : (
        content
      )}
    </GlowCard>
  );
};
