import React from 'react';
import {
  CheckCircle2,
  AlertOctagon,
  Clock,
  Sparkles,
  Info,
  Database,
  AlertTriangle,
  AlertCircle,
} from 'lucide-react';
import clsx from 'clsx';

export type BadgeVariant =
  | 'approve'
  | 'review'
  | 'reject'
  | 'pending'
  | 'critical'
  | 'high'
  | 'medium'
  | 'low'
  | 'info'
  | 'docai'
  | 'gemini'
  | 'layout'
  | 'form'
  | 'amber'
  | 'neutral';

export interface BadgeProps {
  variant: BadgeVariant;
  label?: string;
  score?: number | null;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  showIcon?: boolean;
}

/**
 * Badge - Semantic status badge with WCAG AA contrast and color-blind safe icon pairings.
 * Follows the Nexa & Adfonic amber and black theme.
 */
export const Badge: React.FC<BadgeProps> = ({
  variant,
  label,
  score,
  size = 'md',
  className = '',
  showIcon = true,
}) => {
  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5 gap-1',
    md: 'text-xs px-2.5 py-1 gap-1.5',
    lg: 'text-sm px-3 py-1.5 gap-2',
  }[size];

  switch (variant) {
    case 'approve':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-emerald-50 dark:bg-emerald-500/12 text-emerald-800 dark:text-emerald-400 border-emerald-300 dark:border-emerald-500/30',
            sizeClasses,
            className
          )}
        >
          {showIcon && <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />}
          <span>{label || 'Approve'}</span>
          {score !== undefined && score !== null && (
            <span className="font-mono font-semibold text-[10px] tabular-nums">({score})</span>
          )}
        </span>
      );

    case 'review':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-semibold border',
            'bg-amber-500/10 dark:bg-amber-primary/14 text-amber-800 dark:text-amber-primary border-amber-300 dark:border-amber-primary/40 shadow-[0_0_10px_-2px_rgba(245,165,36,0.2)]',
            sizeClasses,
            className
          )}
        >
          {showIcon && <Clock className="w-3.5 h-3.5 shrink-0 text-amber-800 dark:text-amber-primary" />}
          <span>{label ? (label.toLowerCase().includes('review') ? label : `Review: ${label}`) : 'Review'}</span>
          {score !== undefined && score !== null && (
            <span className="font-mono font-semibold text-[10px] tabular-nums">({score})</span>
          )}
        </span>
      );

    case 'reject':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-rose-50 dark:bg-rose-500/14 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-500/35',
            sizeClasses,
            className
          )}
        >
          {showIcon && <AlertOctagon className="w-3.5 h-3.5 shrink-0" />}
          <span>{label || 'Reject'}</span>
          {score !== undefined && score !== null && (
            <span className="font-mono font-semibold text-[10px] tabular-nums">({score})</span>
          )}
        </span>
      );

    case 'pending':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-stone-100 dark:bg-white/[0.04] text-stone-700 dark:text-app-muted border-stone-300 dark:border-white/[0.1]',
            sizeClasses,
            className
          )}
        >
          {showIcon && <Clock className="w-3.5 h-3.5 shrink-0" />}
          <span>{label || 'Pending Audit'}</span>
        </span>
      );

    case 'critical':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-semibold border',
            'bg-rose-100 dark:bg-rose-500/18 text-rose-900 dark:text-rose-300 border-rose-300 dark:border-rose-500/40',
            sizeClasses,
            className
          )}
        >
          {showIcon && <AlertOctagon className="w-3.5 h-3.5 shrink-0 text-rose-700 dark:text-rose-400" />}
          <span>{label || 'Critical'}</span>
        </span>
      );

    case 'high':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-rose-50 dark:bg-rose-500/12 text-rose-800 dark:text-rose-400 border-rose-200 dark:border-rose-500/25',
            sizeClasses,
            className
          )}
        >
          {showIcon && <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-rose-700 dark:text-rose-400" />}
          <span>{label || 'High'}</span>
        </span>
      );

    case 'medium':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-amber-500/10 dark:bg-amber-primary/12 text-amber-800 dark:text-amber-primary border-amber-300 dark:border-amber-primary/30',
            sizeClasses,
            className
          )}
        >
          {showIcon && <AlertCircle className="w-3.5 h-3.5 shrink-0 text-amber-800 dark:text-amber-primary" />}
          <span>{label || 'Medium'}</span>
        </span>
      );

    case 'low':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-stone-100 dark:bg-white/[0.05] text-stone-700 dark:text-app-muted border-stone-300 dark:border-white/[0.12]',
            sizeClasses,
            className
          )}
        >
          {showIcon && <Info className="w-3.5 h-3.5 shrink-0" />}
          <span>{label || 'Low'}</span>
        </span>
      );

    case 'amber':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-amber-500/10 dark:bg-amber-primary/12 text-amber-800 dark:text-amber-primary border-amber-300 dark:border-amber-primary/35',
            sizeClasses,
            className
          )}
        >
          {showIcon && <Sparkles className="w-3.5 h-3.5 shrink-0" />}
          <span>{label || 'Amber'}</span>
        </span>
      );

    case 'info':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-stone-100 dark:bg-white/[0.05] text-stone-700 dark:text-app-secondary border-stone-300 dark:border-white/[0.12]',
            sizeClasses,
            className
          )}
        >
          {showIcon && <Info className="w-3.5 h-3.5 shrink-0" />}
          <span>{label || 'Info'}</span>
        </span>
      );

    case 'docai':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-amber-500/10 dark:bg-amber-primary/10 text-amber-900 dark:text-amber-bright border-amber-300 dark:border-amber-primary/30',
            sizeClasses,
            className
          )}
        >
          {showIcon && <Database className="w-3.5 h-3.5 shrink-0" />}
          <span>{label || 'DocAI'}</span>
        </span>
      );

    case 'gemini':
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-amber-500/10 dark:bg-amber-primary/12 text-amber-800 dark:text-amber-primary border-amber-300 dark:border-amber-primary/35',
            sizeClasses,
            className
          )}
        >
          {showIcon && <Sparkles className="w-3.5 h-3.5 shrink-0" />}
          <span>{label || 'Gemini Pro'}</span>
        </span>
      );

    default:
      return (
        <span
          className={clsx(
            'inline-flex items-center rounded-full font-medium border',
            'bg-stone-100 dark:bg-white/[0.04] text-stone-700 dark:text-app-muted border-stone-300 dark:border-white/[0.1]',
            sizeClasses,
            className
          )}
        >
          <span>{label || variant}</span>
        </span>
      );
  }
};
