import React from 'react';
import { Search, X } from 'lucide-react';
import clsx from 'clsx';

export interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

/**
 * SearchBar - Nexa-style dark search input with magnifying glass icon.
 */
export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  placeholder = 'Search claims, claimants, hospitals...',
  className,
}) => {
  return (
    <div className={clsx('relative flex items-center w-full', className)}>
      <Search className="absolute left-3 w-4 h-4 text-app-muted pointer-events-none" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={clsx(
          'w-full pl-9 pr-8 py-2 rounded-xl text-xs sm:text-sm font-sans',
          'bg-white/[0.04] border border-white/[0.08]',
          'text-app-primary placeholder:text-app-muted/60',
          'transition-all duration-150',
          'hover:border-white/[0.14]',
          'focus:border-amber-primary/50 focus:bg-white/[0.06] focus:outline-none focus:ring-1 focus:ring-amber-primary/30'
        )}
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange('')}
          aria-label="Clear search"
          className="absolute right-2.5 p-0.5 rounded-full text-app-muted hover:text-app-primary transition-colors cursor-pointer"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
};
