import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  RefreshCw,
  Plus,
  Scale,
  Calendar,
  AlertOctagon,
  Copy,
  Check,
  Clock,
} from 'lucide-react';
import { AnalyticsSummary, RecentCriticalClaim } from '../types';
import { fetchAnalyticsSummary } from '../services/api';
import {
  GlowCard,
  KpiCard,
  ArcGauge,
  GlowAreaChart,
  SparklineRow,
  RankedList,
  StatusTable,
  PillTabs,
  ToggleSwitch,
  SearchBar,
  FilterButton,
  Badge,
} from '../components/ui';
import { SankeyFlow } from '../components/dashboard/SankeyFlow';
import { formatIndianCurrency, formatDiagnosis, formatClaimRef } from '../utils/formatters';

export const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search and Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [activeVerdictTab, setActiveVerdictTab] = useState<string>('all');
  const [showFilters, setShowFilters] = useState<boolean>(false);
  const [chartMetric, setChartMetric] = useState<'amount' | 'volume'>('amount');

  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Synthetic Test Claims Filter State - default to true (exclude synthetic demo claims)
  const [excludeSynthetic, setExcludeSynthetic] = useState<boolean>(() => {
    const saved = localStorage.getItem('finshield_filter_synthetic');
    return saved !== null ? saved === 'true' : true;
  });

  const loadSummary = React.useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const summary = await fetchAnalyticsSummary(excludeSynthetic);
      setData(summary);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch analytics summary';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [excludeSynthetic]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const handleToggleSynthetic = (checked: boolean) => {
    setExcludeSynthetic(checked);
    localStorage.setItem('finshield_filter_synthetic', String(checked));
  };

  // Filtered Claims for the Status Table
  const filteredClaims = useMemo(() => {
    if (!data?.recent_critical_claims) return [];
    return data.recent_critical_claims.filter((c) => {
      // Verdict Filter
      if (activeVerdictTab !== 'all' && c.verdict.toLowerCase() !== activeVerdictTab) {
        return false;
      }
      // Search Query Filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesId = c.claim_id.toLowerCase().includes(q);
        const matchesName = (c.claimant_name || '').toLowerCase().includes(q);
        const matchesHospital = (c.hospital_name || '').toLowerCase().includes(q);
        const matchesCity = (c.city || '').toLowerCase().includes(q);
        const matchesDiag = (c.diagnosis_code || '').toLowerCase().includes(q);
        return matchesId || matchesName || matchesHospital || matchesCity || matchesDiag;
      }
      return true;
    });
  }, [data?.recent_critical_claims, activeVerdictTab, searchQuery]);

  // Ranked Fraud Types Data for the Nexa RankedList
  const rankedFraudItems = useMemo(() => {
    if (!data?.fraud_categories || data.fraud_categories.length === 0) return [];
    const totalFindings = data.fraud_categories.reduce((acc, cat) => acc + cat.count, 0) || 1;
    return data.fraud_categories
      .slice(0, 4)
      .map((cat, idx) => ({
        id: `fraud-${idx}`,
        name: cat.category,
        subtext: `${cat.claims_count} claims affected`,
        percentage: Math.round((cat.count / totalFindings) * 100),
        onClick: () => navigate('/claims?verdict=reject'),
      }));
  }, [data?.fraud_categories, navigate]);

  // Trend Chart Data Points
  const trendChartData = useMemo(() => {
    if (!data?.time_series || data.time_series.length === 0) {
      // If server returned empty time_series (e.g. no claims in window), return empty array
      return [];
    }
    return data.time_series.map((ts) => ({
      label: ts.date,
      value: chartMetric === 'amount' ? ts.amount_claimed : ts.claims_count,
      formattedValue: chartMetric === 'amount' ? formatIndianCurrency(ts.amount_claimed) : `${ts.claims_count} claims`,
    }));
  }, [data?.time_series, chartMetric]);

  // Anomaly Vector Share & Trends (Honest Data Policy: no synthetic wave points)
  const sparklineCategories = useMemo(() => {
    if (!data?.fraud_categories) return [];
    const totalCount = data.fraud_categories.reduce((sum, c) => sum + c.count, 0) || 1;
    return data.fraud_categories.slice(0, 4).map((cat) => {
      // Empty data array: sparse daily history (< 4 days) renders clean 'trend n/a' instead of inventing fake waves
      return {
        label: cat.category.split('&')[0].trim(),
        fullLabel: cat.category,
        data: [] as number[],
        valueText: `${Math.round((cat.count / totalCount) * 100)}% of findings`,
        claimsCount: cat.claims_count,
        findingsCount: cat.count,
      };
    });
  }, [data?.fraud_categories]);

  // Prevention Rate for ArcGauge
  const preventionRate = data && data.total_claims > 0
    ? Math.round((data.verdicts.reject / data.total_claims) * 100)
    : 0;

  // Table Columns Definition
  const statusTableColumns = [
    {
      key: 'created_at',
      header: 'Time',
      className: 'font-mono text-app-muted whitespace-nowrap text-[11px]',
      render: (c: RecentCriticalClaim) => {
        try {
          const date = new Date(c.created_at);
          return isNaN(date.getTime()) ? 'Recent' : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        } catch {
          return 'Recent';
        }
      },
    },
    {
      key: 'claim_id',
      header: 'Claim Reference',
      className: 'font-mono font-medium text-app-primary whitespace-nowrap',
      render: (c: RecentCriticalClaim) => (
        <div className="flex items-center gap-1.5">
          <span className="text-amber-primary hover:text-amber-bright font-mono font-semibold">
            {formatClaimRef(c.claim_id)}
          </span>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              navigator.clipboard.writeText(c.claim_id);
              setCopiedId(c.claim_id);
              setTimeout(() => setCopiedId(null), 1500);
            }}
            className="p-1 rounded hover:bg-white/10 text-app-muted hover:text-app-primary transition-colors cursor-pointer"
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
      ),
    },
    {
      key: 'top_finding_title',
      header: 'Anomaly Type',
      className: 'max-w-[200px] truncate',
      render: (c: RecentCriticalClaim) => {
        const v = (c.verdict || '').toLowerCase();
        const isNotAnalysed = !v || v === 'not_analysed' || v === 'pending';
        const isReject = v === 'reject';
        const isReview = v === 'review';

        let icon = <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />;
        if (isNotAnalysed) {
          icon = <Clock className="w-3.5 h-3.5 text-app-muted shrink-0" />;
        } else if (isReject) {
          icon = <AlertOctagon className="w-3.5 h-3.5 text-rose-400 shrink-0" />;
        } else if (isReview) {
          icon = <AlertTriangle className="w-3.5 h-3.5 text-amber-primary shrink-0" />;
        }

        const displayAnomaly = isNotAnalysed
          ? 'Not analysed'
          : (c.top_finding_title && c.top_finding_title !== 'Audit Completed'
              ? c.top_finding_title
              : 'No anomalies');

        return (
          <div className="flex items-center gap-1.5 truncate" title={displayAnomaly}>
            {icon}
            <span className="truncate text-xs font-medium text-app-primary">
              {displayAnomaly}
            </span>
          </div>
        );
      },
    },
    {
      key: 'city',
      header: 'City / Diagnosis',
      className: 'text-app-muted text-xs whitespace-nowrap',
      render: (c: RecentCriticalClaim) => {
        const diag = formatDiagnosis(c.diagnosis_code);
        return (
          <div className="flex flex-col">
            <span className="text-app-primary">{c.city || 'Regional'}</span>
            <span className="text-[10px] text-app-muted font-mono">{diag.code}</span>
          </div>
        );
      },
    },
    {
      key: 'verdict',
      header: 'Verdict',
      className: 'text-center whitespace-nowrap',
      render: (c: RecentCriticalClaim) => {
        const v = (c.verdict || '').toLowerCase();
        if (!v || v === 'not_analysed' || v === 'pending') {
          return <Badge variant="unanalysed" label="Not analysed" size="sm" />;
        }
        if (c.status === 'incomplete') {
          return (
            <div className="inline-flex items-center justify-center gap-1.5">
              <Badge
                variant={v === 'reject' ? 'reject' : 'review'}
                score={c.risk_score}
                size="sm"
              />
              <span
                title={c.incomplete_reason || 'Doc unreadable — manual review required'}
                className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-primary border border-amber-500/30 cursor-help"
              >
                Incomplete
              </span>
            </div>
          );
        }
        return (
          <Badge
            variant={
              v === 'approve'
                ? 'approve'
                : v === 'review'
                ? 'review'
                : v === 'reject'
                ? 'reject'
                : 'unanalysed'
            }
            score={c.risk_score}
            size="sm"
          />
        );
      },
    },
    {
      key: 'total_claimed',
      header: 'Amount',
      className: 'text-right font-mono font-semibold tabular-nums text-app-primary whitespace-nowrap',
      render: (c: RecentCriticalClaim) => formatIndianCurrency(c.total_claimed),
    },
  ];

  const verdictTabs = [
    { id: 'all', label: 'All Claims', badge: data?.total_claims || 0 },
    { id: 'review', label: 'Under Review', badge: data?.verdicts.review || 0 },
    { id: 'reject', label: 'Rejected (Fraud)', badge: data?.verdicts.reject || 0 },
    { id: 'approve', label: 'Approved', badge: data?.verdicts.approve || 0 },
  ];

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* =========================================================================
          1. Nexa Top Search, Filter & Controls Row
         ========================================================================= */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        {/* Search Input & Filter Button */}
        <div className="flex items-center gap-3 flex-1 max-w-xl">
          <SearchBar
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Filter claims, claimants, diagnosis codes..."
          />
          <FilterButton
            label="Filter"
            isOpen={showFilters}
            activeCount={activeVerdictTab !== 'all' ? 1 : 0}
            onClick={() => setShowFilters(!showFilters)}
          />
        </div>

        {/* Right Controls: Synthetic Toggle, Refresh, New Claim */}
        <div className="flex items-center gap-3 flex-wrap justify-end">
          <ToggleSwitch
            checked={!excludeSynthetic}
            onChange={(checked) => handleToggleSynthetic(!checked)}
            label="Include demo and duel claims"
          />

          <button
            onClick={loadSummary}
            className="p-2 rounded-xl border border-white/[0.08] bg-white/[0.03] text-app-muted hover:text-app-primary hover:border-white/[0.16] transition-colors cursor-pointer"
            title="Refresh analytics data"
            aria-label="Refresh analytics data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => navigate('/upload')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-primary text-black font-semibold text-xs hover:bg-amber-bright transition-all shadow-[0_0_16px_rgba(245,165,36,0.35)] cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Audit Bill</span>
          </button>
        </div>
      </div>

      {/* Pill Tabs Filter Row */}
      {(showFilters || activeVerdictTab !== 'all') && (
        <div className="pt-1 pb-2">
          <PillTabs
            tabs={verdictTabs}
            activeTabId={activeVerdictTab}
            onChange={setActiveVerdictTab}
          />
        </div>
      )}

      {/* Fail-Loud Error State */}
      {error && (
        <div className="p-4 rounded-2xl bg-rose-500/12 border border-rose-500/30 text-rose-300 flex items-center gap-3 text-xs sm:text-sm">
          <ShieldAlert className="w-5 h-5 shrink-0 text-rose-400" />
          <div>
            <p className="font-semibold">{error}</p>
            <p className="text-xs text-rose-300/80 mt-0.5">
              Fail-Loud Policy: Verify backend API and Cloud Firestore connections are active.
            </p>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {loading && !data && (
        <div className="p-20 text-center text-app-muted space-y-4 rounded-[20px] bg-app-surface border border-white/[0.08]">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-amber-primary" />
          <p className="text-xs font-mono">Aggregating live loss prevention metrics from Cloud Firestore & BigQuery...</p>
        </div>
      )}

      {/* Main Bento Grid */}
      {data && (
        <>
          {/* =========================================================================
              2. Hero KPI Cards Row (Adfonic Style with Amber Corner Glow)
             ========================================================================= */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
            <KpiCard
              label="Claims Audited"
              value={data.total_claims}
              icon={<FileText className="w-4 h-4" />}
              contextText={`${formatIndianCurrency(data.total_amount_claimed)} total billed`}
              contextTone="neutral"
              cornerGlow={true}
              onClick={() => navigate('/claims')}
            />
            <KpiCard
              label="Fraud Loss Prevented"
              value={data.total_amount_protected}
              prefix="₹ "
              icon={<ShieldAlert className="w-4 h-4" />}
              contextText={`${data.verdicts.reject} fraudulent claims denied`}
              contextTone="positive"
              cornerGlow={true}
              onClick={() => navigate('/claims?verdict=reject')}
            />
            <KpiCard
              label="Under Manual Review"
              value={data.verdicts.review}
              icon={<AlertTriangle className="w-4 h-4" />}
              contextText={`${formatIndianCurrency(data.total_amount_review)} under scrutiny`}
              contextTone="amber"
              cornerGlow={true}
              onClick={() => navigate('/claims?verdict=review')}
            />
            <KpiCard
              label="Auto-Approved Rate"
              value={data.total_claims > 0 ? Math.round((data.verdicts.approve / data.total_claims) * 100) : 0}
              suffix="%"
              icon={<CheckCircle2 className="w-4 h-4" />}
              contextText={`${data.verdicts.approve} authentic claims verified`}
              contextTone="neutral"
              cornerGlow={true}
              onClick={() => navigate('/claims?verdict=approve')}
            />
          </div>

          {/* =========================================================================
              3. Nexa Core Bento Section: Recent Claims (Left) + Meter & Ranked (Right)
             ========================================================================= */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6 items-start">
            {/* Left Panel: Recent Claims StatusTable (Nexa Center Card) */}
            <GlowCard className="lg:col-span-8 p-5 sm:p-6 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-white/[0.06]">
                <div>
                  <h3 className="text-sm sm:text-base font-semibold tracking-wide text-app-primary">
                    Recent Claims Audit
                  </h3>
                  <p className="text-xs text-app-muted mt-0.5">
                    Real-time claims telemetry prioritized by fraud severity.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => navigate('/claims')}
                  className="text-xs font-mono text-amber-primary hover:underline flex items-center gap-1 cursor-pointer"
                >
                  <span>View All ({data.total_claims})</span>
                  <span>&rarr;</span>
                </button>
              </div>

              {/* Status Table */}
              <StatusTable
                data={filteredClaims}
                columns={statusTableColumns}
                keyExtractor={(c) => c.claim_id}
                onRowClick={(c) => navigate(`/claims/${c.claim_id}`)}
                emptyMessage="No claims matched the active filter"
              />
            </GlowCard>

            {/* Right Column: ArcGauge + Top Fraud Types RankedList */}
            <div className="lg:col-span-4 space-y-5">
              {/* Card 1: ArcGauge (Fraud Prevention Ratio Meter) */}
              <GlowCard className="p-5 flex flex-col items-center justify-center relative overflow-hidden">
                <div className="w-full flex items-center justify-between mb-2">
                  <span className="text-xs font-medium uppercase tracking-wider text-app-muted">
                    Loss Mitigation Ratio
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/20">
                    Live
                  </span>
                </div>

                <ArcGauge
                  value={preventionRate}
                  min={0}
                  max={100}
                  unit="%"
                  caption="Fraud Losses Prevented"
                  variant="amber"
                  size="md"
                />

                <div className="w-full mt-3 pt-3 border-t border-white/[0.06] flex items-center justify-between text-[11px] font-mono text-app-muted">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-amber-primary/70" />
                    <span>Active Period</span>
                  </span>
                  <span className="text-app-primary font-semibold">FY 2026 Q3</span>
                </div>
              </GlowCard>

              {/* Card 2: Top Fraud Types RankedList (Nexa Top 3 Origins Panel) */}
              <GlowCard className="p-5">
                <RankedList
                  title="Top 4 Anomaly Vectors"
                  items={rankedFraudItems}
                  emptyMessage="No anomalies recorded"
                />
              </GlowCard>
            </div>
          </div>

          {/* =========================================================================
              4. Bottom Bento Row: Glowing Area Chart (Left) + Sparkline Trends (Right)
             ========================================================================= */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6 items-start">
            {/* Bottom-Left: Claims Trend GlowAreaChart or Designed Sparse State */}
            <GlowCard className="lg:col-span-7 p-5 sm:p-6">
              {trendChartData.length >= 5 ? (
                <GlowAreaChart
                  title="Claims Volume & Loss Trajectory"
                  data={trendChartData}
                  valuePrefix={chartMetric === 'amount' ? '₹ ' : ''}
                  height={200}
                  selector={
                    <div className="flex items-center gap-1 p-0.5 rounded-lg bg-white/[0.04] border border-white/[0.08]">
                      <button
                        type="button"
                        onClick={() => setChartMetric('amount')}
                        className={`px-2 py-1 rounded text-[11px] font-mono transition-colors cursor-pointer ${
                          chartMetric === 'amount'
                            ? 'bg-amber-primary/20 text-amber-primary font-bold'
                            : 'text-app-muted hover:text-app-primary'
                        }`}
                      >
                        Billed (₹)
                      </button>
                      <button
                        type="button"
                        onClick={() => setChartMetric('volume')}
                        className={`px-2 py-1 rounded text-[11px] font-mono transition-colors cursor-pointer ${
                          chartMetric === 'volume'
                            ? 'bg-amber-primary/20 text-amber-primary font-bold'
                            : 'text-app-muted hover:text-app-primary'
                        }`}
                      >
                        Count
                      </button>
                    </div>
                  }
                />
              ) : (
                <div className="space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3 border-b border-app-default">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-semibold tracking-wide text-app-primary">
                          Claims Volume & Loss Trajectory
                        </h3>
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
                          {trendChartData.length} Days on Record
                        </span>
                      </div>
                      <p className="text-xs text-app-muted mt-1">
                        Not enough history yet: {trendChartData.length} days of data. Continuous trajectory curve requires ≥ 5 days of chronological records.
                      </p>
                    </div>

                    <div className="flex items-center gap-1 p-0.5 rounded-lg bg-white/[0.04] border border-white/[0.08] shrink-0 self-start sm:self-auto">
                      <button
                        type="button"
                        onClick={() => setChartMetric('amount')}
                        className={`px-2 py-1 rounded text-[11px] font-mono transition-colors cursor-pointer ${
                          chartMetric === 'amount'
                            ? 'bg-amber-primary/20 text-amber-primary font-bold'
                            : 'text-app-muted hover:text-app-primary'
                        }`}
                      >
                        Billed (₹)
                      </button>
                      <button
                        type="button"
                        onClick={() => setChartMetric('volume')}
                        className={`px-2 py-1 rounded text-[11px] font-mono transition-colors cursor-pointer ${
                          chartMetric === 'volume'
                            ? 'bg-amber-primary/20 text-amber-primary font-bold'
                            : 'text-app-muted hover:text-app-primary'
                        }`}
                      >
                        Count
                      </button>
                    </div>
                  </div>

                  {/* Clean Comparative Bars / Table */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                    {trendChartData.map((d, i) => {
                      const maxVal = Math.max(...trendChartData.map((pt) => pt.value)) || 1;
                      const pct = Math.round((d.value / maxVal) * 100);
                      return (
                        <div
                          key={d.label}
                          className="p-3.5 rounded-xl bg-app-surface-elevated border border-app-default space-y-2.5"
                        >
                          <div className="flex items-center justify-between text-xs">
                            <span className="font-mono text-app-muted font-medium">Day {i + 1} · {d.label}</span>
                            <span className="font-mono text-[11px] text-amber-primary font-bold">
                              {d.formattedValue}
                            </span>
                          </div>
                          {/* Relative Proportion Bar */}
                          <div className="w-full h-2 rounded-full bg-white/[0.06] overflow-hidden">
                            <div
                              className="h-full rounded-full bg-gradient-to-r from-amber-deep via-amber-primary to-amber-bright transition-all duration-500 shadow-[0_0_8px_rgba(245,165,36,0.4)]"
                              style={{ width: `${Math.max(12, pct)}%` }}
                            />
                          </div>
                          <div className="flex items-center justify-between text-[10px] font-mono text-app-muted">
                            <span>Relative share: {pct}%</span>
                            <span>Recorded pipeline data</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </GlowCard>

            {/* Bottom-Right: Fraud Type Velocity Sparklines (Nexa Malware Trends) */}
            <GlowCard className="lg:col-span-5 p-5 sm:p-6 space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-app-default">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold tracking-wide text-app-primary">
                      Anomaly Vector Trends
                    </h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.04] text-app-muted border border-white/[0.08]">
                      Last 30 Days
                    </span>
                  </div>
                  <p className="text-xs text-app-muted mt-0.5">
                    Finding distribution across active claims. Historical velocity requires ≥ 4 days.
                  </p>
                </div>
                <Scale className="w-4 h-4 text-amber-primary/70 shrink-0" />
              </div>

              <div className="divide-y divide-white/[0.06]">
                {sparklineCategories.length > 0 ? (
                  sparklineCategories.map((cat, idx) => (
                    <SparklineRow
                      key={idx}
                      label={cat.label}
                      data={cat.data}
                      valueText={cat.valueText}
                      sublabel={`${cat.claimsCount} claims`}
                    />
                  ))
                ) : (
                  <div className="py-8 text-center text-xs text-app-muted font-mono">
                    No fraud categories detected
                  </div>
                )}
              </div>
            </GlowCard>
          </div>

          {/* =========================================================================
              5. Multi-Agent Adjudication Flow (Restyled Sankey)
             ========================================================================= */}
          <SankeyFlow
            totalClaims={data.total_claims}
            totalAmount={data.total_amount_claimed}
            verdicts={data.verdicts}
            totalProtected={data.total_amount_protected}
            totalReview={data.total_amount_review}
          />
        </>
      )}
    </div>
  );
};
