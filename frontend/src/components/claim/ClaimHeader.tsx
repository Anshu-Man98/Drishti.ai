import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowLeft,
  FileCheck,
  MessageSquare,
  RefreshCw,
  Copy,
  Check,
} from 'lucide-react';
import { Claim, Dossier } from '../../types';
import { formatInsurer, formatPolicy } from '../../utils/formatters';
import { PillTabs } from '../ui/PillTabs';

interface ClaimHeaderProps {
  claim: Claim;
  dossier: Dossier | null;
  analyzing: boolean;
  layoutMode: 'split' | 'doc' | 'audit' | 'spacetime';
  onLayoutChange: (mode: 'split' | 'doc' | 'audit' | 'spacetime') => void;
  onOpenChat: () => void;
  onOpenSanctionModal: () => void;
  onRunAnalysis: () => void;
}

export const ClaimHeader: React.FC<ClaimHeaderProps> = ({
  claim,
  dossier,
  analyzing,
  layoutMode,
  onLayoutChange,
  onOpenChat,
  onOpenSanctionModal,
  onRunAnalysis,
}) => {
  const [copied, setCopied] = React.useState(false);
  const insurer = formatInsurer(claim.insurer_id);
  const policy = formatPolicy(claim.policy_id);

  const hasSpacetimeAnomaly = dossier?.findings?.some(
    (f) =>
      f.agent === 'spacetime' ||
      f.check_id?.includes('SPACETIME') ||
      f.category === 'DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL'
  );

  const layoutTabs = [
    { id: 'split', label: 'Split View' },
    { id: 'doc', label: 'Document' },
    { id: 'audit', label: 'Audit Dossier' },
    ...(hasSpacetimeAnomaly || (dossier?.timeline && dossier.timeline.length > 0)
      ? [{ id: 'spacetime', label: 'Spacetime' }]
      : []),
  ];

  return (
    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 bg-surface/80 p-4 sm:p-5 rounded-[20px] border border-white/8 backdrop-blur-md shadow-2xs">
      {/* Left: Claim Identifier & Metadata */}
      <div className="flex items-start sm:items-center gap-3">
        <Link
          to="/claims"
          className="p-2.5 rounded-xl bg-surface-elevated text-muted hover:text-text-primary border border-white/10 hover:border-amber-primary/40 transition-colors shrink-0"
          title="Back to Claims Queue"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-1.5">
              <h1 className="text-lg sm:text-xl font-bold text-text-primary font-mono tracking-tight">
                {claim.claim_id}
              </h1>
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(claim.claim_id);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                }}
                className="p-1 rounded hover:bg-white/10 text-muted hover:text-text-primary transition-colors cursor-pointer"
                title={`Copy Claim ID: ${claim.claim_id}`}
                aria-label={`Copy Claim ID ${claim.claim_id}`}
              >
                {copied ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                ) : (
                  <Copy className="w-3.5 h-3.5 opacity-60 hover:opacity-100" />
                )}
              </button>
            </div>
            <span className="text-xs px-2.5 py-0.5 rounded-full font-mono font-medium bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
              {policy.name}
            </span>
            <span className="text-xs text-muted font-medium">
              {insurer.name}
            </span>
          </div>
          <p className="text-xs text-text-secondary mt-1">
            Claimant: <span className="font-semibold text-text-primary">{claim.claimant.name}</span> • Provider: <span className="font-semibold text-text-primary">{claim.provider.name}</span> ({claim.provider.city})
          </p>
        </div>
      </div>

      {/* Right: Layout Switcher & Action Controls */}
      <div className="flex items-center gap-2.5 flex-wrap">
        {/* Layout Switcher Tabs (Desktop only) */}
        <div className="hidden md:flex items-center">
          <PillTabs
            tabs={layoutTabs}
            activeTab={layoutMode}
            onChange={(tabId) => onLayoutChange(tabId as 'split' | 'doc' | 'audit' | 'spacetime')}
          />
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Ask Case Assistant Button */}
          <button
            type="button"
            onClick={onOpenChat}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-surface hover:bg-surface-elevated text-text-primary border border-white/10 text-xs font-medium transition-colors"
            title="Open Interactive Case Assistant"
          >
            <MessageSquare className="w-3.5 h-3.5 text-amber-primary" />
            <span className="hidden sm:inline">Ask Assistant</span>
          </button>

          {/* Issue Sanction Note Button (Available if claim is approved or reviewed) */}
          {dossier && (
            <button
              type="button"
              onClick={onOpenSanctionModal}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold transition-colors"
              title="Issue cryptographic Sanction Note"
            >
              <FileCheck className="w-3.5 h-3.5 text-emerald-400" />
              <span className="hidden sm:inline">Issue Sanction</span>
            </button>
          )}

          {/* Analyze / Re-Run Button */}
          <button
            type="button"
            onClick={onRunAnalysis}
            disabled={analyzing}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-amber-primary hover:bg-amber-bright text-black font-semibold text-xs transition-all shadow-md shadow-amber-primary/20 disabled:opacity-50"
            title="Run 8-Agent Adjudication Audit"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${analyzing ? 'animate-spin' : ''}`} />
            <span>{analyzing ? 'Auditing...' : 'Analyze Claim'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
