import React from 'react';
import clsx from 'clsx';

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  className?: string;
  headerClassName?: string;
}

export interface StatusTableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T) => string;
  onRowClick?: (item: T) => void;
  stickyHeader?: boolean;
  emptyMessage?: string;
  className?: string;
}

/**
 * StatusTable - Nexa-style dark status table.
 * Features:
 * - Thin row dividers (1px subtle white/translucent)
 * - Small muted uppercase header labels
 * - Keyboard navigable rows (Tab, Enter, Space)
 * - Support for icon-chips, status badges, and truncated cells
 */
export function StatusTable<T>({
  data,
  columns,
  keyExtractor,
  onRowClick,
  stickyHeader = false,
  emptyMessage = 'No records found',
  className,
}: StatusTableProps<T>) {
  return (
    <div className={clsx('w-full overflow-x-auto select-none', className)}>
      <table className="w-full text-left border-collapse">
        <thead>
          <tr className={clsx('border-b border-white/[0.08]', stickyHeader && 'sticky top-0 bg-app-surface z-10')}>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={clsx(
                  'py-2.5 px-3 text-[11px] font-medium uppercase tracking-wider text-app-muted whitespace-nowrap',
                  col.headerClassName
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/[0.05] text-xs">
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="py-12 text-center text-app-muted text-xs font-mono"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((item) => {
              const key = keyExtractor(item);
              const isClickable = Boolean(onRowClick);

              const handleKeyDown = (e: React.KeyboardEvent<HTMLTableRowElement>) => {
                if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault();
                  onRowClick(item);
                }
              };

              return (
                <tr
                  key={key}
                  tabIndex={isClickable ? 0 : undefined}
                  role={isClickable ? 'button' : undefined}
                  onClick={() => onRowClick?.(item)}
                  onKeyDown={handleKeyDown}
                  className={clsx(
                    'transition-colors group',
                    isClickable && 'cursor-pointer hover:bg-white/[0.03] focus-visible:bg-white/[0.04] focus-visible:outline-none'
                  )}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={clsx('py-3 px-3 align-middle text-app-secondary group-hover:text-app-primary', col.className)}
                    >
                      {col.render ? col.render(item) : ((item as Record<string, unknown>)[col.key] as React.ReactNode)}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
