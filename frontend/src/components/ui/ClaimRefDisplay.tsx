import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Copy, Check } from 'lucide-react';
import clsx from 'clsx';
import { formatClaimRef, FormatClaimRefOptions } from '../../utils/formatters';

export interface ClaimRefDisplayProps {
  claimId: string;
  claimantName?: string | null;
  hospitalName?: string | null;
  mode?: 'full' | 'short' | 'ellipsis';
  maxLen?: number;
  headLen?: number;
  tailLen?: number;
  linkTo?: string;
  showCopy?: boolean;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * ClaimRefDisplay - Standardized, accessible claim reference cell.
 * Displays monospace claim ID with optional head-and-tail ellipsis,
 * native tooltip with full ID, 1-click copy button, and claimant/hospital subtitle.
 */
export const ClaimRefDisplay: React.FC<ClaimRefDisplayProps> = ({
  claimId,
  claimantName,
  hospitalName,
  mode = 'ellipsis',
  maxLen = 17,
  headLen = 9,
  tailLen = 5,
  linkTo,
  showCopy = true,
  className = '',
  size = 'sm',
}) => {
  const [copied, setCopied] = useState(false);

  const options: FormatClaimRefOptions = {
    mode,
    maxLen,
    headLen,
    tailLen,
  };

  const displayText = formatClaimRef(claimId, options);

  const handleCopy = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (claimId) {
      navigator.clipboard.writeText(claimId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  const refSizes = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base font-bold',
  }[size];

  const subText = [claimantName?.trim(), hospitalName?.trim()].filter(Boolean).join(' · ');

  const content = (
    <span
      className={clsx(
        'font-mono font-semibold text-amber-primary hover:text-amber-bright tracking-tight',
        refSizes
      )}
      title={claimId}
    >
      {displayText}
    </span>
  );

  return (
    <div className={clsx('flex flex-col min-w-0', className)}>
      <div className="flex items-center gap-1.5 min-w-0">
        {linkTo ? (
          <Link
            to={linkTo}
            className="hover:underline truncate focus:outline-hidden focus:ring-1 focus:ring-amber-primary rounded-xs"
            title={claimId}
          >
            {content}
          </Link>
        ) : (
          <div className="truncate" title={claimId}>
            {content}
          </div>
        )}

        {showCopy && claimId && (
          <button
            type="button"
            onClick={handleCopy}
            className="p-1 rounded hover:bg-white/10 text-app-muted hover:text-app-primary transition-colors cursor-pointer shrink-0"
            title={`Copy claim ID: ${claimId}`}
            aria-label={`Copy claim ID ${claimId}`}
          >
            {copied ? (
              <Check className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <Copy className="w-3.5 h-3.5 opacity-60 hover:opacity-100" />
            )}
          </button>
        )}
      </div>

      {subText && (
        <div
          className="text-[11px] text-app-muted truncate mt-0.5"
          title={subText}
        >
          {subText}
        </div>
      )}
    </div>
  );
};
