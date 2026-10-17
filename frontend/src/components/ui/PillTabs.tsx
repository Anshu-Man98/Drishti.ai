import React from 'react';
import clsx from 'clsx';

export interface TabItem {
  id: string;
  label: string;
  badge?: number | string;
  icon?: React.ReactNode;
}

export interface PillTabsProps {
  tabs: TabItem[];
  activeTabId: string;
  onChange: (id: string) => void;
  onAddTab?: () => void;
  className?: string;
  size?: 'sm' | 'md';
}

/**
 * PillTabs - Adfonic style outlined pill tabs with warm amber active state.
 * Features:
 * - Rounded full pills
 * - Subtle border with hover brightening
 * - Active state: warm amber glow + amber border + amber text
 * - Optional '+' button
 */
export const PillTabs: React.FC<PillTabsProps> = ({
  tabs,
  activeTabId,
  onChange,
  onAddTab,
  className,
  size = 'md',
}) => {
  const sizeClasses = {
    sm: 'px-3 py-1 text-xs',
    md: 'px-4 py-1.5 text-xs',
  }[size];

  return (
    <div className={clsx('flex items-center gap-2 overflow-x-auto select-none py-1', className)} role="tablist">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTabId;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={clsx(
              'rounded-full font-medium transition-all duration-150 flex items-center gap-1.5 whitespace-nowrap cursor-pointer focus-visible:outline-2 focus-visible:outline-amber-primary',
              sizeClasses,
              isActive
                ? 'bg-amber-primary/12 border border-amber-primary/45 text-amber-primary shadow-[0_0_12px_-2px_rgba(245,165,36,0.25)]'
                : 'bg-white/[0.02] border border-white/[0.08] text-app-muted hover:text-app-primary hover:border-white/[0.18]'
            )}
          >
            {tab.icon && <span className="shrink-0">{tab.icon}</span>}
            <span>{tab.label}</span>
            {tab.badge !== undefined && (
              <span
                className={clsx(
                  'ml-1 px-1.5 py-0.2 rounded-full text-[10px] font-mono',
                  isActive ? 'bg-amber-primary/20 text-amber-primary' : 'bg-white/[0.08] text-app-muted'
                )}
              >
                {tab.badge}
              </span>
            )}
          </button>
        );
      })}

      {onAddTab && (
        <button
          type="button"
          onClick={onAddTab}
          aria-label="Add new tab"
          className="w-7 h-7 rounded-full border border-white/[0.1] bg-white/[0.02] text-app-muted hover:text-amber-primary hover:border-amber-primary/30 flex items-center justify-center transition-colors cursor-pointer"
        >
          <span className="text-sm font-light">+</span>
        </button>
      )}
    </div>
  );
};
