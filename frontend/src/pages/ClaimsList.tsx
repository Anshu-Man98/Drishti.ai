import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldAlert,
  ArrowUpRight,
  Filter,
  Building2,
  User,
  RefreshCw,
  Plus,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Check,
} from 'lucide-react';
import { ClaimSummary } from '../types';
import { fetchClaims } from '../services/api';
import { Badge } from '../components/ui/Badge';
import { SearchBar } from '../components/ui/SearchBar';
import { PillTabs } from '../components/ui/PillTabs';
import { GlowCard } from '../components/ui/GlowCard';
import {
  formatIndianCurrency,
  formatDiagnosis,
  formatInsurer,
  formatPolicy,
  formatDateTime,
} from '../utils/formatters';

type SortField = 'created_at' | 'total_claimed' | 'risk_score' | 'claim_id' | 'claimant_name' | 'hospital_name' | 'diagnosis_code';

export const ClaimsList: React.FC = () => {
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Pagination States
  const [searchTerm, setSearchTerm] = useState('');
  const [activeVerdict, setActiveVerdict] = useState<string>('all');
  const [sortBy, setSortBy] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [excludeSynthetic, setExcludeSynthetic] = useState<boolean>(() => {
    return localStorage.getItem('finshield_filter_synthetic') === 'true';
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const offset = (currentPage - 1) * pageSize;
      const res = await fetchClaims({
        limit: pageSize,
        offset,
        verdict: activeVerdict !== 'all' ? activeVerdict : undefined,
        sortBy,
        sortOrder,
        search: searchTerm.trim() || undefined,
        excludeSynthetic,
      });
      setClaims(res.claims);
      setTotalCount(res.totalCount);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load claims';
      setError(msg);
      setClaims([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [currentPage, pageSize, activeVerdict, sortBy, sortOrder, searchTerm, excludeSynthetic]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleSynthetic = () => {
    const nextVal = !excludeSynthetic;
    setExcludeSynthetic(nextVal);
    localStorage.setItem('finshield_filter_synthetic', String(nextVal));
    setCurrentPage(1);
  };

  const handleSearchChange = (val: string) => {
    setSearchTerm(val);
    setCurrentPage(1);
  };

  const handleVerdictChange = (v: string) => {
    setActiveVerdict(v);
    setCurrentPage(1);
  };

  const handleSort = (field: SortField) => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder(field === 'created_at' || field === 'risk_score' || field === 'total_claimed' ? 'desc' : 'asc');
    }
    setCurrentPage(1);
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  const startItem = totalCount > 0 ? (currentPage - 1) * pageSize + 1 : 0;
  const endItem = Math.min(currentPage * pageSize, totalCount);

  const renderSortIcon = (field: SortField) => {
    if (sortBy !== field) {
      return <ArrowUpDown className="w-3.5 h-3.5 text-muted/50" />;
    }
    return sortOrder === 'asc' ? (
      <ArrowUp className="w-3.5 h-3.5 text-amber-primary" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-amber-primary" />
    );
  };

  const verdictTabs = [
    { id: 'all', label: 'All' },
    { id: 'approve', label: 'Approved' },
    { id: 'review', label: 'Under Review' },
    { id: 'reject', label: 'Rejected' },
    { id: 'unreviewed', label: 'Pending' },
  ];

  return (
    <div className="space-y-6">
      {/* Title & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary flex items-center gap-2.5">
            <span>Claims Audit Queue</span>
            <span className="text-xs font-mono font-medium px-2.5 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
              {totalCount} Total Claims
            </span>
          </h1>
          <p className="text-xs sm:text-sm text-text-secondary mt-1">
            Real-time multi-agent audit ledger with clinical indication decoding and risk scrutiny.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            type="button"
            onClick={toggleSynthetic}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border transition-colors ${
              excludeSynthetic
                ? 'bg-amber-primary/10 border-amber-primary/40 text-amber-primary'
                : 'bg-surface border-white/10 text-text-secondary hover:bg-surface-elevated hover:text-text-primary'
            }`}
            title="Toggle exclusion of synthetic and demo test claims"
          >
            <span className={`w-2 h-2 rounded-full ${excludeSynthetic ? 'bg-amber-primary animate-pulse' : 'bg-muted'}`} />
            <span>{excludeSynthetic ? 'Excluding Demo Claims' : 'All Claims (Inc. Demo)'}</span>
          </button>
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-surface hover:bg-surface-elevated text-text-primary text-xs font-medium border border-white/10 transition-colors shadow-2xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-amber-primary ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link
            to="/upload"
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-amber-primary hover:bg-amber-bright text-black text-xs font-semibold shadow-md shadow-amber-primary/20 transition-all hover:scale-[1.02]"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Claim</span>
          </Link>
        </div>
      </div>

      {/* Filter / Search & Pagination Bar */}
      <GlowCard className="p-3.5 sm:p-4 flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">
        {/* Search Input */}
        <div className="flex-1 max-w-md">
          <SearchBar
            placeholder="Search claimant, hospital, city, claim ID, or diagnosis..."
            value={searchTerm}
            onChange={handleSearchChange}
          />
        </div>

        {/* Verdict Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 lg:pb-0">
          <span className="text-xs text-muted font-medium px-1 flex items-center gap-1 shrink-0">
            <Filter className="w-3.5 h-3.5 text-amber-primary" />
            <span>Verdict:</span>
          </span>
          <PillTabs
            tabs={verdictTabs}
            activeTab={activeVerdict}
            onChange={handleVerdictChange}
          />
        </div>

        {/* Page Size Select */}
        <div className="flex items-center gap-2 text-xs text-muted shrink-0">
          <span>Show:</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setCurrentPage(1);
            }}
            className="bg-surface border border-white/10 rounded-lg px-2.5 py-1 text-xs text-text-primary focus:outline-none focus:border-amber-primary/50"
          >
            <option value="10">10 / page</option>
            <option value="25">25 / page</option>
            <option value="50">50 / page</option>
          </select>
        </div>
      </GlowCard>

      {/* Claims Table Container */}
      <div className="bg-surface/80 border border-white/8 rounded-[20px] overflow-hidden shadow-2xs backdrop-blur-md">
        {loading ? (
          <div className="p-16 text-center text-text-secondary space-y-3">
            <RefreshCw className="w-7 h-7 animate-spin mx-auto text-amber-primary" />
            <p className="text-xs font-mono">Querying claims database from Cloud Firestore...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-400 space-y-2">
            <ShieldAlert className="w-8 h-8 mx-auto" />
            <p className="text-sm font-semibold">{error}</p>
            <p className="text-xs text-muted">Fail-Loud Policy: Verify backend API is reachable at port 8000.</p>
          </div>
        ) : claims.length === 0 ? (
          <div className="p-16 text-center text-text-secondary space-y-3">
            <p className="text-sm font-medium text-text-primary">No claims match the selected criteria.</p>
            <p className="text-xs text-muted">
              Try adjusting your search terms or clearing the verdict filter.
            </p>
            <button
              onClick={() => {
                setSearchTerm('');
                setActiveVerdict('all');
                setCurrentPage(1);
              }}
              className="text-xs text-amber-primary hover:text-amber-bright hover:underline inline-block font-medium"
            >
              Reset Filters
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs sm:text-sm text-text-primary">
              <thead className="bg-surface-elevated/80 border-b border-white/8 text-[11px] uppercase tracking-wider text-muted sticky top-0 z-10">
                <tr>
                  <th
                    onClick={() => handleSort('claim_id')}
                    className="py-3 px-4 font-semibold cursor-pointer hover:text-text-primary transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Claim Reference</span>
                      {renderSortIcon('claim_id')}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('claimant_name')}
                    className="py-3 px-4 font-semibold cursor-pointer hover:text-text-primary transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Claimant</span>
                      {renderSortIcon('claimant_name')}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('hospital_name')}
                    className="py-3 px-4 font-semibold cursor-pointer hover:text-text-primary transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Hospital Provider</span>
                      {renderSortIcon('hospital_name')}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('diagnosis_code')}
                    className="py-3 px-4 font-semibold cursor-pointer hover:text-text-primary transition-colors"
                  >
                    <div className="flex items-center gap-1.5">
                      <span>Clinical Indication</span>
                      {renderSortIcon('diagnosis_code')}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('total_claimed')}
                    className="py-3 px-4 font-semibold text-right cursor-pointer hover:text-text-primary transition-colors"
                  >
                    <div className="flex items-center justify-end gap-1.5">
                      <span>Claim Amount</span>
                      {renderSortIcon('total_claimed')}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('risk_score')}
                    className="py-3 px-4 font-semibold text-center cursor-pointer hover:text-text-primary transition-colors"
                  >
                    <div className="flex items-center justify-center gap-1.5">
                      <span>Audit Verdict & Risk</span>
                      {renderSortIcon('risk_score')}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('created_at')}
                    className="py-3 px-4 font-semibold text-right cursor-pointer hover:text-text-primary transition-colors"
                  >
                    <div className="flex items-center justify-end gap-1.5">
                      <span>Date / Action</span>
                      {renderSortIcon('created_at')}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {claims.map((c) => {
                  const diagnosis = formatDiagnosis(c.diagnosis_code);
                  const insurer = formatInsurer(c.insurer_id);
                  const policy = formatPolicy(c.policy_id);
                  const verdictVariant =
                    c.verdict === 'approve'
                      ? 'approve'
                      : c.verdict === 'review'
                      ? 'review'
                      : c.verdict === 'reject'
                      ? 'reject'
                      : 'pending';

                  const riskVal = Math.round(c.risk_score ?? 0);

                  return (
                    <tr
                      key={c.claim_id}
                      className="hover:bg-white/3 transition-colors"
                    >
                      {/* Claim Reference & Policy */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5">
                          <Link
                            to={`/claims/${c.claim_id}`}
                            className="font-semibold text-amber-primary hover:text-amber-bright hover:underline block truncate max-w-[160px] font-mono"
                          >
                            Claim #{c.claim_id.length > 8 ? c.claim_id.slice(-6) : c.claim_id}
                          </Link>
                          <button
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              navigator.clipboard.writeText(c.claim_id);
                              setCopiedId(c.claim_id);
                              setTimeout(() => setCopiedId(null), 1500);
                            }}
                            className="p-1 rounded hover:bg-white/10 text-muted hover:text-text-primary transition-colors"
                            title={`Copy full Claim ID: ${c.claim_id}`}
                            aria-label="Copy Claim ID"
                          >
                            {copiedId === c.claim_id ? (
                              <Check className="w-3 h-3 text-emerald-400" />
                            ) : (
                              <Copy className="w-3 h-3 opacity-60 hover:opacity-100" />
                            )}
                          </button>
                        </div>
                        <span className="text-[11px] text-text-secondary block truncate max-w-[170px]" title={policy.name}>
                          {insurer.short} · {policy.name}
                        </span>
                        <span className="font-mono text-[10px] text-muted block truncate max-w-[170px]">
                          {c.claim_id}
                        </span>
                      </td>

                      {/* Claimant */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-muted shrink-0" />
                          <span className="font-medium text-text-primary">
                            {c.claimant_name || 'Unspecified'}
                          </span>
                        </div>
                      </td>

                      {/* Hospital & City */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-1.5">
                          <Building2 className="w-3.5 h-3.5 text-muted shrink-0" />
                          <span className="text-text-primary truncate max-w-[190px]">
                            {c.hospital_name || 'Unknown Provider'}
                          </span>
                        </div>
                        <span className="text-[11px] text-text-secondary block pl-5">
                          {c.city || '—'}
                        </span>
                      </td>

                      {/* Diagnosis */}
                      <td className="py-3.5 px-4">
                        <span className="block font-medium text-text-primary max-w-[200px] truncate">
                          {diagnosis.label}
                        </span>
                        <span className="font-mono text-[11px] text-muted">
                          ICD-10: {diagnosis.code}
                        </span>
                      </td>

                      {/* Amount */}
                      <td className="py-3.5 px-4 text-right font-mono font-semibold tabular-nums text-text-primary">
                        {formatIndianCurrency(c.total_claimed)}
                      </td>

                      {/* Verdict & Risk Meter */}
                      <td className="py-3.5 px-4 text-center">
                        <div className="flex flex-col items-center gap-1">
                          <Badge
                            variant={verdictVariant}
                            score={c.risk_score}
                            size="sm"
                          />
                          {/* Mini Risk Bar */}
                          <div className="w-20 bg-white/10 rounded-full h-1.5 overflow-hidden flex items-center">
                            <div
                              className={`h-full rounded-full ${
                                riskVal > 60
                                  ? 'bg-rose-500'
                                  : riskVal > 30
                                  ? 'bg-amber-primary'
                                  : 'bg-emerald-400'
                              }`}
                              style={{ width: `${Math.min(100, Math.max(5, riskVal))}%` }}
                            />
                          </div>
                        </div>
                      </td>

                      {/* Action & Date */}
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex flex-col items-end gap-1">
                          <Link
                            to={`/claims/${c.claim_id}`}
                            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface hover:bg-amber-primary hover:text-black text-amber-primary border border-amber-primary/30 text-xs font-semibold transition-all group shadow-2xs"
                          >
                            <span>Audit</span>
                            <ArrowUpRight className="w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                          </Link>
                          {c.created_at && (
                            <span className="text-[10px] text-muted font-mono">
                              {formatDateTime(c.created_at)}
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {!loading && totalCount > 0 && (
          <div className="px-4 py-3 bg-surface-elevated/60 border-t border-white/8 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-text-secondary">
            <div>
              Showing <span className="font-medium text-text-primary">{startItem}</span> to{' '}
              <span className="font-medium text-text-primary">{endItem}</span> of{' '}
              <span className="font-medium text-text-primary">{totalCount}</span> claims
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-white/10 bg-surface text-text-primary hover:bg-surface-elevated disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Previous</span>
              </button>

              <span className="font-mono text-xs px-2 text-text-primary">
                Page {currentPage} of {totalPages}
              </span>

              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-white/10 bg-surface text-text-primary hover:bg-surface-elevated disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
