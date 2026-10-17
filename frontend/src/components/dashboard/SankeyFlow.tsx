import React, { useState } from 'react';
import { formatIndianCurrency } from '../../utils/formatters';

interface SankeyFlowProps {
  totalClaims: number;
  totalAmount: number;
  verdicts: {
    approve: number;
    review: number;
    reject: number;
    pending: number;
  };
  totalProtected: number;
  totalReview: number;
}

export const SankeyFlow: React.FC<SankeyFlowProps> = ({
  totalClaims,
  totalAmount,
  verdicts,
  totalProtected,
  totalReview,
}) => {
  const [activeHover, setActiveHover] = useState<string | null>(null);

  const approvePct = totalClaims > 0 ? Math.round((verdicts.approve / totalClaims) * 100) : 0;
  const reviewPct = totalClaims > 0 ? Math.round((verdicts.review / totalClaims) * 100) : 0;
  const rejectPct = totalClaims > 0 ? Math.round((verdicts.reject / totalClaims) * 100) : 0;
  const pendingPct = totalClaims > 0 ? Math.round((verdicts.pending / totalClaims) * 100) : 0;

  // ViewBox layout dimensions: 800 x 360
  // Col 1: Ingestion (x: 40, w: 160)
  // Col 2: Multi-Agent Pipeline (x: 320, w: 160)
  // Col 3: Verdicts (x: 600, w: 170)

  return (
    <div className="rounded-[20px] bg-app-surface border border-white/[0.08] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.07)] p-5 sm:p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4 pb-4 border-b border-white/[0.06]">
        <div>
          <h2 className="text-base font-bold tracking-tight text-app-primary flex items-center gap-2">
            <span>Claim Adjudication Flow</span>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25 font-medium">
              Multi-Agent Telemetry
            </span>
          </h2>
          <p className="text-xs text-app-muted mt-0.5">
            Real-time pipeline flow from invoice ingestion to automated multi-agent consensus and final adjudication.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs text-app-muted font-mono">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-emerald-500" />
            <span className="text-emerald-800 dark:text-emerald-400 font-medium">Approve ({approvePct}%)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-amber-primary" />
            <span className="text-amber-800 dark:text-amber-primary font-medium">Review ({reviewPct}%)</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-xs bg-rose-500" />
            <span className="text-rose-800 dark:text-rose-400 font-medium">Reject ({rejectPct}%)</span>
          </span>
          {pendingPct > 0 && (
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-xs bg-white/40" />
              <span>Pending ({pendingPct}%)</span>
            </span>
          )}
        </div>
      </div>

      {/* SVG Canvas */}
      <div className="relative w-full overflow-hidden">
        <svg
          viewBox="0 0 860 340"
          className="w-full h-auto select-none font-sans"
          style={{ maxHeight: '360px' }}
        >
          <defs>
            {/* Stream Gradients */}
            <linearGradient id="stream-ingest-agent" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#F5A524" stopOpacity="0.30" />
              <stop offset="100%" stopColor="#FFC15A" stopOpacity="0.22" />
            </linearGradient>

            <linearGradient id="stream-agent-approve" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#FFC15A" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#10B981" stopOpacity="0.38" />
            </linearGradient>

            <linearGradient id="stream-agent-review" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#FFC15A" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#F5A524" stopOpacity="0.40" />
            </linearGradient>

            <linearGradient id="stream-agent-reject" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#FFC15A" stopOpacity="0.22" />
              <stop offset="100%" stopColor="#F43F5E" stopOpacity="0.42" />
            </linearGradient>

            {/* Pattern for flowing dashes */}
            <filter id="subtle-shadow" x="-5%" y="-5%" width="110%" height="110%">
              <feDropShadow dx="0" dy="1" stdDeviation="1.5" floodOpacity="0.08" />
            </filter>
          </defs>

          {/* ================= STREAMS (BACKGROUND CONNECTORS) ================= */}

          {/* Stream 1: Ingestion -> Agent Inspection */}
          <path
            d="M 180 90 C 260 90, 260 80, 340 80 L 340 260 C 260 260, 260 250, 180 250 Z"
            fill="url(#stream-ingest-agent)"
            className="transition-all duration-300"
            opacity={activeHover === 'ingest' ? 0.9 : 0.65}
          />
          {/* Animated Flow Guides */}
          <path
            d="M 180 170 C 260 170, 260 170, 340 170"
            stroke="#818CF8"
            strokeWidth="1.5"
            strokeDasharray="4 6"
            fill="none"
            opacity="0.6"
          >
            <animate attributeName="stroke-dashoffset" from="40" to="0" dur="2s" repeatCount="indefinite" />
          </path>

          {/* Stream 2A: Agent Inspection -> Approved */}
          <path
            d="M 500 90 C 560 90, 560 55, 620 55 L 620 105 C 560 105, 560 125, 500 125 Z"
            fill="url(#stream-agent-approve)"
            className="transition-all duration-300 cursor-pointer"
            opacity={activeHover === 'approve' ? 0.95 : 0.6}
            onMouseEnter={() => setActiveHover('approve')}
            onMouseLeave={() => setActiveHover(null)}
          />

          {/* Stream 2B: Agent Inspection -> Review */}
          <path
            d="M 500 135 C 560 135, 560 155, 620 155 L 620 215 C 560 215, 560 195, 500 195 Z"
            fill="url(#stream-agent-review)"
            className="transition-all duration-300 cursor-pointer"
            opacity={activeHover === 'review' ? 0.95 : 0.6}
            onMouseEnter={() => setActiveHover('review')}
            onMouseLeave={() => setActiveHover(null)}
          />

          {/* Stream 2C: Agent Inspection -> Reject */}
          <path
            d="M 500 205 C 560 205, 560 265, 620 265 L 620 325 C 560 325, 560 255, 500 255 Z"
            fill="url(#stream-agent-reject)"
            className="transition-all duration-300 cursor-pointer"
            opacity={activeHover === 'reject' ? 0.95 : 0.65}
            onMouseEnter={() => setActiveHover('reject')}
            onMouseLeave={() => setActiveHover(null)}
          />

          {/* ================= COLUMN 1: INTAKE & INGESTION ================= */}
          <g transform="translate(30, 80)">
            <rect
              width="150"
              height="180"
              rx="12"
              fill="var(--bg-elevated)"
              stroke="var(--border-default)"
              strokeWidth="1"
              filter="url(#subtle-shadow)"
            />
            <rect
              width="150"
              height="32"
              rx="12"
              fill="var(--bg-subtle)"
              stroke="var(--border-default)"
              strokeWidth="1"
            />
            <text x="14" y="21" fill="var(--brand-primary)" className="text-[11px] font-bold font-mono">
              STAGE 1: INTAKE
            </text>

            <text x="14" y="60" fill="var(--text-primary)" className="text-[12px] font-bold font-mono">
              {totalClaims} Claims Ingested
            </text>
            <text x="14" y="80" fill="var(--brand-primary)" className="text-[11px] font-mono font-semibold tabular-nums">
              {formatIndianCurrency(totalAmount)}
            </text>

            <line x1="14" y1="96" x2="136" y2="96" stroke="var(--border-default)" strokeWidth="1" />

            <text x="14" y="118" fill="var(--text-primary)" className="text-[11px] font-medium">
              Document AI Extraction
            </text>
            <text x="14" y="138" fill="var(--text-primary)" className="text-[11px] font-medium">
              Gemini Vision Cross-Check
            </text>
            <text x="14" y="158" fill="var(--text-primary)" className="text-[11px] font-medium">
              Prompt Shield Sanitized
            </text>
          </g>

          {/* ================= COLUMN 2: MULTI-AGENT SCRUTINY ================= */}
          <g transform="translate(340, 70)">
            <rect
              width="160"
              height="200"
              rx="12"
              fill="var(--bg-elevated)"
              stroke="var(--border-default)"
              strokeWidth="1"
              filter="url(#subtle-shadow)"
            />
            <rect
              width="160"
              height="32"
              rx="12"
              fill="var(--bg-subtle)"
              stroke="var(--border-default)"
              strokeWidth="1"
            />
            <text x="14" y="21" fill="var(--brand-primary)" className="text-[11px] font-bold font-mono">
              STAGE 2: MULTI-AGENT
            </text>

            <text x="14" y="58" fill="var(--text-primary)" className="text-[12px] font-bold">
              Parallel Scrutiny
            </text>

            <g transform="translate(14, 72)">
              <rect width="132" height="24" rx="6" fill="var(--bg-subtle)" stroke="var(--border-default)" strokeWidth="1" />
              <text x="8" y="16" fill="var(--text-primary)" className="text-[10px] font-mono font-medium">
                Forensics & PDF ELA
              </text>
            </g>

            <g transform="translate(14, 102)">
              <rect width="132" height="24" rx="6" fill="var(--bg-subtle)" stroke="var(--border-default)" strokeWidth="1" />
              <text x="8" y="16" fill="var(--text-primary)" className="text-[10px] font-mono font-medium">
                Policy & Benchmark Caps
              </text>
            </g>

            <g transform="translate(14, 132)">
              <rect width="132" height="24" rx="6" fill="var(--bg-subtle)" stroke="var(--border-default)" strokeWidth="1" />
              <text x="8" y="16" fill="var(--text-primary)" className="text-[10px] font-mono font-medium">
                Spacetime & Teleportation
              </text>
            </g>

            <g transform="translate(14, 162)">
              <rect width="132" height="24" rx="6" fill="var(--bg-subtle)" stroke="var(--border-default)" strokeWidth="1" />
              <text x="8" y="16" fill="var(--text-primary)" className="text-[10px] font-mono font-medium">
                BQML Fraud Outliers
              </text>
            </g>
          </g>

          {/* ================= COLUMN 3: ADJUDICATION VERDICTS ================= */}

          {/* Approve Box */}
          <g
            transform="translate(620, 35)"
            className="cursor-pointer"
            onMouseEnter={() => setActiveHover('approve')}
            onMouseLeave={() => setActiveHover(null)}
          >
            <rect
              width="190"
              height="75"
              rx="8"
              fill="var(--bg-elevated)"
              stroke={activeHover === 'approve' ? 'var(--risk-approve)' : 'var(--risk-approve-border)'}
              strokeWidth={activeHover === 'approve' ? 1.5 : 1}
              filter="url(#subtle-shadow)"
            />
            <circle cx="24" cy="24" r="8" fill="var(--risk-approve-bg)" />
            <circle cx="24" cy="24" r="3.5" fill="var(--risk-approve)" />
            <text x="40" y="27" fill="var(--risk-approve)" className="text-[11px] font-bold">
              Auto-Approve ({verdicts.approve})
            </text>
            <text x="16" y="52" fill="var(--text-primary)" className="text-[11px] font-mono font-semibold">
              {approvePct}% of total claims
            </text>
            <text x="16" y="67" fill="var(--text-muted)" className="text-[10px]">
              Zero anomalies, exact math
            </text>
          </g>

          {/* Review Box */}
          <g
            transform="translate(620, 140)"
            className="cursor-pointer"
            onMouseEnter={() => setActiveHover('review')}
            onMouseLeave={() => setActiveHover(null)}
          >
            <rect
              width="190"
              height="80"
              rx="8"
              fill="var(--bg-elevated)"
              stroke={activeHover === 'review' ? 'var(--risk-review)' : 'var(--risk-review-border)'}
              strokeWidth={activeHover === 'review' ? 1.5 : 1}
              filter="url(#subtle-shadow)"
            />
            <circle cx="24" cy="24" r="8" fill="var(--risk-review-bg)" />
            <circle cx="24" cy="24" r="3.5" fill="var(--risk-review)" />
            <text x="40" y="27" fill="var(--risk-review)" className="text-[11px] font-bold">
              Flagged for Review ({verdicts.review})
            </text>
            <text x="16" y="52" fill="var(--text-primary)" className="text-[11px] font-mono font-semibold tabular-nums">
              {formatIndianCurrency(totalReview)} ({reviewPct}%)
            </text>
            <text x="16" y="69" fill="var(--text-muted)" className="text-[10px]">
              Ambiguous caps, unreadable text
            </text>
          </g>

          {/* Reject Box */}
          <g
            transform="translate(620, 245)"
            className="cursor-pointer"
            onMouseEnter={() => setActiveHover('reject')}
            onMouseLeave={() => setActiveHover(null)}
          >
            <rect
              width="190"
              height="85"
              rx="8"
              fill="var(--bg-elevated)"
              stroke={activeHover === 'reject' ? 'var(--risk-reject)' : 'var(--risk-reject-border)'}
              strokeWidth={activeHover === 'reject' ? 1.5 : 1}
              filter="url(#subtle-shadow)"
            />
            <circle cx="24" cy="24" r="8" fill="var(--risk-reject-bg)" />
            <circle cx="24" cy="24" r="3.5" fill="var(--risk-reject)" />
            <text x="40" y="27" fill="var(--risk-reject)" className="text-[11px] font-bold">
              Rejected Fraud ({verdicts.reject})
            </text>
            <text x="16" y="52" fill="var(--risk-reject)" className="text-[11px] font-mono font-semibold tabular-nums">
              {formatIndianCurrency(totalProtected)} Protected
            </text>
            <text x="16" y="70" fill="var(--text-muted)" className="text-[10px]">
              Proven tampering, spacetime rings
            </text>
          </g>
        </svg>
      </div>
    </div>
  );
};
