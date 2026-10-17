import React from 'react';
import clsx from 'clsx';

export interface GlowCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  cornerGlow?: boolean;
  interactive?: boolean;
  className?: string;
  elevation?: 'surface' | 'elevated' | 'subtle';
}

/**
 * GlowCard - Black glass card with 20px radius, 1px subtle border,
 * inner top highlight, optional amber corner glow, and 2px hover lift.
 * Follows the Nexa & Adfonic reference aesthetic.
 */
export const GlowCard: React.FC<GlowCardProps> = ({
  children,
  cornerGlow = false,
  interactive = false,
  elevation = 'surface',
  className,
  ...props
}) => {
  const elevationClasses = {
    surface: 'bg-app-surface',
    elevated: 'bg-app-elevated',
    subtle: 'bg-app-subtle',
  }[elevation];

  return (
    <div
      className={clsx(
        'relative rounded-[20px] border border-white/[0.08] dark:border-white/[0.08] light:border-black/[0.08]',
        'shadow-[inset_0_1px_0_0_rgba(255,255,255,0.07)]',
        'transition-all duration-200 ease-out',
        elevationClasses,
        cornerGlow && 'corner-glow-amber',
        interactive && [
          'cursor-pointer',
          'hover:-translate-y-0.5',
          'hover:border-amber-500/30',
          'hover:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1),0_6px_24px_-4px_rgba(245,165,36,0.12)]',
          'focus-visible:outline-2 focus-visible:outline-amber-500',
        ],
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};
