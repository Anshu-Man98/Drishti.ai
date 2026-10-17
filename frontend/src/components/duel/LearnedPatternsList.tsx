import React, { useState } from 'react';
import { BookOpen, Search } from 'lucide-react';
import { LearnedPattern } from '../../types';
import { formatDateTime } from '../../utils/formatters';

interface LearnedPatternsListProps {
  patterns: LearnedPattern[];
}

export const LearnedPatternsList: React.FC<LearnedPatternsListProps> = ({ patterns }) => {
  const [searchQuery, setSearchQuery] = useState('');

  const filtered = patterns.filter(
    (p) =>
      p.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.tactic?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.pattern_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.narrative?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 sm:p-6 shadow-2xs backdrop-blur-md space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-amber-primary" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-primary">
            Autonomous Evasion Learning Catalog ({patterns.length})
          </h3>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="Search learned patterns..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-8 pr-3 py-1.5 rounded-xl bg-surface border border-white/10 text-xs text-text-primary placeholder-muted focus:outline-none focus:border-amber-primary w-full sm:w-64"
          />
        </div>
      </div>

      <p className="text-xs text-text-secondary leading-relaxed">
        Whenever an adversarial fraudster evades FinShield checks, the evasion signature is automatically extracted,
        persisted to BigQuery, and embedded into the <strong className="text-amber-primary">Two-Corpus RAG Catalog</strong> to immunize future claims.
      </p>

      {/* Patterns Grid */}
      {filtered.length === 0 ? (
        <div className="py-8 text-center text-xs text-muted">
          No learned evasion patterns matching your search.
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((pat) => (
            <div
              key={pat.pattern_id}
              className="p-4 rounded-xl bg-surface-elevated/70 border border-white/8 space-y-2.5 hover:border-amber-primary/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
                      {pat.pattern_id}
                    </span>
                    <h4 className="text-xs font-bold text-text-primary">
                      {pat.title || pat.tactic}
                    </h4>
                  </div>
                  <p className="text-[11px] text-muted">
                    Source: Adversarial Duel
                    {pat.evaded_at && ` • ${formatDateTime(pat.evaded_at)}`}
                  </p>
                </div>

                {(pat.typical_severity || pat.fraud_type) && (
                  <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
                    {pat.typical_severity || pat.fraud_type}
                  </span>
                )}
              </div>

              <p className="text-xs text-text-secondary leading-relaxed">
                {pat.narrative}
              </p>

              {pat.feature_signatures && (
                <div className="pt-1 border-t border-white/6">
                  <span className="text-[10px] text-muted block mb-1">Feature Signatures:</span>
                  <div className="flex flex-wrap gap-1">
                    {pat.feature_signatures.split(',').map((sig, i) => (
                      <span
                        key={i}
                        className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface text-amber-primary border border-amber-primary/20"
                      >
                        {sig.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
