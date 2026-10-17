import React, { useEffect, useState } from 'react';
import { LucideIcon } from 'lucide-react';
import { formatIndianCurrency } from '../../utils/formatters';

interface MetricCardProps {
  title: string;
  value: number;
  isCurrency?: boolean;
  subtitle?: string;
  icon: LucideIcon;
  variant?: 'default' | 'approve' | 'review' | 'reject' | 'brand';
  badge?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  isCurrency = false,
  subtitle,
  icon: Icon,
  variant = 'default',
  badge,
}) => {
  const [displayValue, setDisplayValue] = useState(0);

  // Smooth numeric count-up animation over 800ms
  useEffect(() => {
    let startTimestamp: number | null = null;
    const duration = 750;
    const startValue = 0;
    const endValue = value;

    if (endValue === 0) {
      setDisplayValue(0);
      return;
    }

    const step = (timestamp: number) => {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      // Ease out cubic
      const easeOut = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(startValue + (endValue - startValue) * easeOut);
      setDisplayValue(current);

      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        setDisplayValue(endValue);
      }
    };

    const animId = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(animId);
  }, [value]);

  const variantStyles = {
    default: {
      bg: 'bg-white dark:bg-slate-900',
      border: 'border-slate-200 dark:border-slate-800',
      iconBg: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300',
      text: 'text-slate-900 dark:text-slate-100',
    },
    brand: {
      bg: 'bg-white dark:bg-slate-900',
      border: 'border-blue-200 dark:border-blue-900/60',
      iconBg: 'bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400',
      text: 'text-blue-600 dark:text-blue-400',
    },
    approve: {
      bg: 'bg-white dark:bg-slate-900',
      border: 'border-emerald-200 dark:border-emerald-900/50',
      iconBg: 'bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400',
      text: 'text-emerald-600 dark:text-emerald-400',
    },
    review: {
      bg: 'bg-white dark:bg-slate-900',
      border: 'border-amber-200 dark:border-amber-900/50',
      iconBg: 'bg-amber-50 dark:bg-amber-950/50 text-amber-600 dark:text-amber-400',
      text: 'text-amber-600 dark:text-amber-400',
    },
    reject: {
      bg: 'bg-white dark:bg-slate-900',
      border: 'border-rose-200 dark:border-rose-900/50',
      iconBg: 'bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400',
      text: 'text-rose-600 dark:text-rose-400',
    },
  }[variant];

  const formattedDisplay = isCurrency
    ? formatIndianCurrency(displayValue)
    : displayValue.toLocaleString('en-IN');

  return (
    <div
      className={`p-4 sm:p-5 rounded-xl border ${variantStyles.bg} ${variantStyles.border} shadow-2xs transition-all hover:shadow-xs`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-slate-500 dark:text-slate-400 tracking-tight">
          {title}
        </span>
        <div className={`p-2 rounded-lg ${variantStyles.iconBg}`}>
          <Icon className="w-4 h-4" />
        </div>
      </div>

      <div className="flex items-baseline justify-between gap-2">
        <div className="font-mono text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 tabular-nums">
          {formattedDisplay}
        </div>
        {badge && (
          <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 font-medium border border-slate-200 dark:border-slate-700">
            {badge}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-2 truncate">
          {subtitle}
        </p>
      )}
    </div>
  );
};
