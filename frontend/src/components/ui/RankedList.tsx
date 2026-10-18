import React from 'react';
import { ChevronRight } from 'lucide-react';
import clsx from 'clsx';

export interface RankedItem {
  id: string;
  name: string;
  value?: number | string;
  percentage?: number;
  icon?: React.ReactNode;
  subtext?: string;
  onClick?: () => void;
}

export interface RankedListProps {
  title?: string;
  items: RankedItem[];
  className?: string;
  emptyMessage?: string;
  onTitleClick?: () => void;
  headerAction?: React.ReactNode;
}

/**
 * RankedList - Nexa "Top 3 attack origins" style panel.
 * Features:
 * - Icon or badge on the left
 * - Name / category label
 * - Distinctive circled arrow affordance in the middle-right
 * - Bold tabular percentage / value on the far right
 * - Thin dividers
 */
export const RankedList: React.FC<RankedListProps> = ({
  title,
  items,
  className,
  emptyMessage = 'No ranked data available',
  onTitleClick,
  headerAction,
}) => {
  return (
    <div className={clsx('flex flex-col', className)}>
      {title && (
        <div className="flex items-center justify-between mb-3 px-1">
          {onTitleClick ? (
            <button
              type="button"
              onClick={onTitleClick}
              className="text-left group cursor-pointer focus:outline-none"
            >
              <h3 className="text-sm font-semibold tracking-wide text-app-primary group-hover:text-amber-primary transition-colors flex items-center gap-1.5">
                <span>{title}</span>
                <ChevronRight className="w-3.5 h-3.5 text-app-muted group-hover:text-amber-primary transition-colors" />
              </h3>
            </button>
          ) : (
            <h3 className="text-sm font-semibold tracking-wide text-app-primary">
              {title}
            </h3>
          )}
          {headerAction}
        </div>
      )}

      {items.length === 0 ? (
        <div className="py-8 text-center text-xs text-app-muted border border-white/[0.06] rounded-xl bg-white/[0.02]">
          {emptyMessage}
        </div>
      ) : (
        <div className="flex flex-col divide-y divide-white/[0.06]">
          {items.map((item) => {
            const rowContent = (
              <>
                {/* Left: Icon & Name */}
                <div className="flex items-center gap-3 min-w-0">
                  {item.icon && (
                    <div className="w-6 h-6 rounded-md bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-xs text-amber-primary shrink-0">
                      {item.icon}
                    </div>
                  )}
                  <div className="truncate text-left">
                    <div className="text-xs sm:text-sm font-medium text-app-primary truncate">
                      {item.name}
                    </div>
                    {item.subtext && (
                      <div className="text-[10px] text-app-muted truncate font-mono">
                        {item.subtext}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Circled Arrow & Percentage/Value */}
                <div className="flex items-center gap-3 shrink-0 ml-3">
                  <div className="w-5 h-5 rounded-full border border-white/[0.12] bg-white/[0.02] flex items-center justify-center text-amber-primary/70">
                    <ChevronRight className="w-3 h-3" />
                  </div>
                  <div className="text-xs sm:text-sm font-mono font-medium text-app-primary tabular-nums text-right min-w-[42px]">
                    {item.percentage !== undefined ? `${item.percentage}%` : item.value}
                  </div>
                </div>
              </>
            );

            return item.onClick ? (
              <button
                key={item.id}
                type="button"
                onClick={item.onClick}
                className="w-full flex items-center justify-between py-3 px-1 transition-colors cursor-pointer hover:bg-white/[0.03] rounded-lg focus-visible:outline-2 focus-visible:outline-amber-primary"
              >
                {rowContent}
              </button>
            ) : (
              <div
                key={item.id}
                className="flex items-center justify-between py-3 px-1"
              >
                {rowContent}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
