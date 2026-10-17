import React from 'react';
import clsx from 'clsx';

export interface ToggleSwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  sublabel?: string;
  disabled?: boolean;
  className?: string;
}

/**
 * ToggleSwitch - Adfonic style toggle switch with glowing warm amber thumb.
 * Features:
 * - Clean dark track
 * - Smooth transition
 * - Amber glow on active thumb
 * - Keyboard accessible switch role
 */
export const ToggleSwitch: React.FC<ToggleSwitchProps> = ({
  checked,
  onChange,
  label,
  sublabel,
  disabled = false,
  className,
}) => {
  return (
    <label
      className={clsx(
        'inline-flex items-center gap-2.5 cursor-pointer select-none',
        disabled && 'opacity-40 cursor-not-allowed',
        className
      )}
    >
      <button
        type="button"
        role="switch"
        aria-label={label || 'Toggle switch'}
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={clsx(
          'relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border transition-colors duration-200 ease-in-out focus-visible:outline-2 focus-visible:outline-amber-primary',
          checked
            ? 'bg-amber-primary/20 border-amber-primary/50'
            : 'bg-white/[0.06] border-white/[0.12]'
        )}
      >
        <span
          className={clsx(
            'pointer-events-none inline-block h-3.5 w-3.5 transform rounded-full transition duration-200 ease-in-out mt-0.5',
            checked
              ? 'translate-x-4 bg-amber-primary shadow-[0_0_8px_rgba(245,165,36,0.6)]'
              : 'translate-x-0.5 bg-white/40'
          )}
        />
      </button>

      {(label || sublabel) && (
        <div className="flex flex-col">
          {label && <span className="text-xs font-medium text-app-primary">{label}</span>}
          {sublabel && <span className="text-[10px] text-app-muted font-mono">{sublabel}</span>}
        </div>
      )}
    </label>
  );
};
