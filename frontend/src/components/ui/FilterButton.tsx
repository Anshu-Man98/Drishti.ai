import React from 'react';
import { Filter } from 'lucide-react';
import clsx from 'clsx';

export interface FilterButtonProps {
  activeCount?: number;
  onClick: () => void;
  label?: string;
  isOpen?: boolean;
  className?: string;
}

/**
 * FilterButton - Nexa-style rounded dark button with filter funnel icon and badge.
 */
export const FilterButton: React.FC<FilterButtonProps> = ({
  activeCount = 0,
  onClick,
  label = 'Filter',
  isOpen = false,
  className,
}) => {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={isOpen}
      className={clsx(
        'inline-flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-medium cursor-pointer transition-all duration-150',
        'border focus-visible:outline-2 focus-visible:outline-amber-primary',
        isOpen || activeCount > 0
          ? 'bg-amber-primary/10 border-amber-primary/40 text-amber-primary shadow-xs'
          : 'bg-app-surface dark:bg-white/[0.04] border-app-border text-app-secondary hover:text-app-primary hover:border-app-muted/40 dark:hover:border-white/[0.16] shadow-2xs',
        className
      )}
    >
      <Filter className="w-3.5 h-3.5 shrink-0" />
      <span>{label}</span>
      {activeCount > 0 && (
        <span className="w-4 h-4 rounded-full bg-amber-primary text-black font-mono font-bold text-[10px] flex items-center justify-center">
          {activeCount}
        </span>
      )}
    </button>
  );
};
