import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Network,
  Layers,
  ArrowRight,
  ExternalLink,
  ShieldAlert,
  RefreshCw,
  X,
  Building2,
  User,
  CreditCard,
  Stethoscope,
} from 'lucide-react';
import { FraudRingSummary, RingDetailResponse, NetworkNode, RingClaimRecord } from '../types';
import { fetchFraudRings } from '../services/api';
import { NetworkCanvas } from '../components/network/NetworkCanvas';
import { Badge } from '../components/ui/Badge';
import { PillTabs } from '../components/ui/PillTabs';
import { formatINR, formatDateTime, formatDoctor } from '../utils/formatters';

export const NetworkGraph: React.FC = () => {
  const [rings, setRings] = useState<FraudRingSummary[]>([]);
  const [selectedRingId, setSelectedRingId] = useState<string>('');
  const [ringDetail, setRingDetail] = useState<RingDetailResponse | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'graph' | 'table'>('graph');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async (ringId?: string) => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchFraudRings(ringId);
      setRings(res.rings);
      if (res.selected_ring) {
        setRingDetail(res.selected_ring);
        setSelectedRingId(res.selected_ring.ring.ring_id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load BigQuery fraud rings.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectRing = (ringId: string) => {
    setSelectedRingId(ringId);
    setSelectedNodeId(null);
    loadData(ringId);
  };

  const selectedNode: NetworkNode | undefined = ringDetail?.nodes.find(
    (n) => n.id === selectedNodeId
  );

  // Filter claims matching selected node (if any)
  const filteredClaims: RingClaimRecord[] = ringDetail
    ? selectedNodeId
      ? ringDetail.claims.filter(
          (c) =>
            c.claimant_id === selectedNodeId ||
            c.doctor_id === selectedNodeId ||
            c.hospital_id === selectedNodeId ||
            c.bank_account_hash === selectedNodeId
        )
      : ringDetail.claims
    : [];

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'bank_account':
        return <CreditCard className="w-3.5 h-3.5 text-amber-primary" />;
      case 'doctor':
        return <Stethoscope className="w-3.5 h-3.5 text-amber-bright" />;
      case 'hospital':
        return <Building2 className="w-3.5 h-3.5 text-text-primary" />;
      case 'claimant':
      default:
        return <User className="w-3.5 h-3.5 text-muted" />;
    }
  };

  if (loading && rings.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-24 text-center text-text-secondary space-y-4">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-amber-primary" />
        <p className="text-sm font-medium font-mono">
          Querying BigQuery graph intelligence & extracting collusion clusters...
        </p>
      </div>
    );
  }

  if (error && rings.length === 0) {
    return (
      <div className="max-w-xl mx-auto px-4 py-20 text-center space-y-4 bg-surface/80 border border-white/8 rounded-[20px] p-8">
        <ShieldAlert className="w-12 h-12 text-rose-400 mx-auto" />
        <h2 className="text-xl font-bold text-text-primary">
          Graph Intelligence Unavailable
        </h2>
        <p className="text-text-secondary text-xs leading-relaxed">{error}</p>
        <button
          onClick={() => loadData()}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-amber-primary hover:bg-amber-bright text-black text-xs font-semibold shadow-md shadow-amber-primary/20 transition-all"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry BigQuery Query</span>
        </button>
      </div>
    );
  }

  const viewTabs = [
    { id: 'graph', label: 'Interactive Graph' },
    { id: 'table', label: 'Accessible Table' },
  ];

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-text-primary flex items-center gap-2">
            <Network className="w-6 h-6 text-amber-primary" />
            <span>Fraud-Ring Network Graph</span>
          </h1>
          <p className="text-xs sm:text-sm text-text-secondary mt-1">
            Live BigQuery graph intelligence isolating collusive syndicates sharing bank accounts, doctors, and clinics.
          </p>
        </div>

        {/* View Mode Switcher */}
        <div className="self-start sm:self-auto">
          <PillTabs
            tabs={viewTabs}
            activeTab={viewMode}
            onChange={(tabId) => setViewMode(tabId as 'graph' | 'table')}
          />
        </div>
      </div>

      {/* Ring Selector Horizontal Badges */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-xs text-muted font-semibold uppercase tracking-wider">
          <span>Detected Syndicates in BigQuery ({rings.length})</span>
          <span className="font-mono text-[11px] text-amber-primary">
            Real BQ Warehouse Traverse
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {rings.map((r) => {
            const isSelected = r.ring_id === selectedRingId;
            return (
              <button
                key={r.ring_id}
                type="button"
                onClick={() => handleSelectRing(r.ring_id)}
                className={`p-4 rounded-xl border text-left transition-all ${
                  isSelected
                    ? 'bg-amber-primary/10 border-amber-primary/50 shadow-xs ring-1 ring-amber-primary/40'
                    : 'bg-surface border-white/8 hover:border-amber-primary/30'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-bold text-text-primary truncate">
                    {r.title}
                  </span>
                  <Badge
                    variant={r.risk_level === 'critical' ? 'critical' : 'high'}
                    label={r.risk_level.toUpperCase()}
                    size="sm"
                  />
                </div>

                <div className="mt-3 space-y-1">
                  <div className="text-sm font-bold font-mono text-app-primary tabular-nums">
                    {formatINR(r.total_amount)}
                  </div>
                  <div className="text-[11px] font-mono text-app-muted flex items-center gap-1.5">
                    <span>{r.claim_count} claims</span>
                    <span>·</span>
                    <span>{r.claimant_count} claimants</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Content Area: Interactive Canvas vs Accessible Table */}
      {viewMode === 'graph' ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Canvas Graph View (8 cols) */}
          <div className="lg:col-span-8 space-y-3">
            <div className="bg-surface/80 border border-white/8 rounded-[20px] p-4 shadow-2xs backdrop-blur-md">
              <div className="flex items-center justify-between mb-3 px-1">
                <div className="flex items-center gap-2">
                  <Layers className="w-4 h-4 text-amber-primary" />
                  <span className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    {ringDetail?.ring.title || 'Cluster Topology'}
                  </span>
                </div>
                <div className="text-[11px] text-muted font-mono">
                  {ringDetail?.nodes.length || 0} nodes • {ringDetail?.edges.length || 0} edges
                </div>
              </div>

              <NetworkCanvas
                nodes={ringDetail?.nodes || []}
                edges={ringDetail?.edges || []}
                selectedNodeId={selectedNodeId}
                onSelectNode={setSelectedNodeId}
              />

              <div className="mt-3 flex items-center justify-between text-[11px] text-muted px-1">
                <span>Click any node to filter involved claims in the side panel. Drag to rearrange.</span>
                <span className="font-mono">Scroll to zoom • Drag background to pan</span>
              </div>
            </div>
          </div>

          {/* Side Panel: Syndicate Details & Claims Inspector (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            {/* Syndicate Overview Card */}
            {ringDetail && (
              <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 shadow-2xs backdrop-blur-md space-y-4 text-xs">
                <div className="flex items-start justify-between gap-2 border-b border-white/8 pb-3">
                  <div>
                    <h3 className="font-bold text-sm text-text-primary">
                      {ringDetail.ring.title}
                    </h3>
                    <p className="text-[11px] font-mono text-muted mt-0.5">
                      {ringDetail.ring.ring_id}
                    </p>
                  </div>
                  <Badge
                    variant={ringDetail.ring.risk_level === 'critical' ? 'critical' : 'high'}
                    label={ringDetail.ring.risk_level.toUpperCase()}
                  />
                </div>

                <div className="grid grid-cols-2 gap-2 text-center">
                  <div className="p-3 rounded-xl bg-surface-elevated/70 border border-white/8">
                    <span className="text-[10px] text-muted block uppercase font-semibold">Total at Risk</span>
                    <span className="text-sm font-bold font-mono text-text-primary tabular-nums">
                      {formatINR(ringDetail.ring.total_amount)}
                    </span>
                  </div>
                  <div className="p-3 rounded-xl bg-surface-elevated/70 border border-white/8">
                    <span className="text-[10px] text-muted block uppercase font-semibold">Claimants</span>
                    <span className="text-sm font-bold font-mono text-amber-primary tabular-nums">
                      {ringDetail.ring.claimant_count}
                    </span>
                  </div>
                </div>

                <p className="text-text-secondary leading-relaxed bg-surface-elevated/50 p-3.5 rounded-xl border border-white/6">
                  {ringDetail.ring.description}
                </p>

                {ringDetail.ring.sample_cities.length > 0 && (
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[11px] text-muted">Target Cities:</span>
                    {ringDetail.ring.sample_cities.map((city) => (
                      <span
                        key={city}
                        className="text-[10px] px-2.5 py-0.5 rounded-full bg-surface-elevated text-text-primary border border-white/10 font-medium"
                      >
                        {city}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Selected Node Filter Banner */}
            {selectedNode && (
              <div className="p-3.5 rounded-xl bg-amber-primary/10 border border-amber-primary/30 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="p-1.5 rounded-lg bg-surface text-amber-primary border border-amber-primary/30">
                    {getNodeIcon(selectedNode.type)}
                  </div>
                  <div className="min-w-0">
                    <span className="text-[10px] uppercase font-bold text-amber-primary block">
                      Filtered by {selectedNode.type.replace('_', ' ')}
                    </span>
                    <span className="font-semibold text-text-primary truncate block">
                      {selectedNode.label}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedNodeId(null)}
                  className="p-1 rounded-md text-muted hover:text-text-primary transition-colors"
                  title="Clear filter"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Member Claims List */}
            <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 shadow-2xs backdrop-blur-md space-y-3">
              <div className="flex items-center justify-between border-b border-white/8 pb-2.5">
                <h4 className="text-xs font-bold uppercase tracking-wider text-muted">
                  Involved Claims ({filteredClaims.length})
                </h4>
                <span className="text-[10px] font-mono text-muted">
                  Live BigQuery Records
                </span>
              </div>

              {filteredClaims.length === 0 ? (
                <div className="py-8 text-center text-xs text-muted">
                  No claims found matching the selected entity filter.
                </div>
              ) : (
                <div className="space-y-2.5 max-h-[460px] overflow-y-auto pr-1">
                  {filteredClaims.map((claim) => (
                    <div
                      key={claim.claim_id}
                      className="p-3 rounded-xl bg-surface-elevated/70 border border-white/8 hover:border-amber-primary/30 transition-all space-y-1.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <Link
                          to={`/claims/${claim.claim_id}`}
                          className="text-xs font-bold font-mono text-amber-primary hover:text-amber-bright hover:underline flex items-center gap-1"
                        >
                          <span>{claim.claim_id}</span>
                          <ExternalLink className="w-3 h-3" />
                        </Link>
                        <span className="text-xs font-mono font-bold text-text-primary tabular-nums">
                          {formatINR(claim.total_claimed)}
                        </span>
                      </div>

                      <div className="text-[11px] text-text-secondary flex items-center justify-between">
                        <span>{claim.claimant_name}</span>
                        <span className="text-muted">{claim.city}</span>
                      </div>

                      <div className="text-[10px] text-muted flex items-center justify-between font-mono pt-1 border-t border-white/6">
                        <span>{formatDoctor(claim.doctor_id)}</span>
                        <span>{claim.hospital_name}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Accessible Table View (Full Width) */
        <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 shadow-2xs backdrop-blur-md space-y-4">
          <div className="flex items-center justify-between border-b border-white/8 pb-3">
            <div>
              <h3 className="text-sm font-bold text-text-primary">
                {ringDetail?.ring.title || 'Syndicate Claims Data'}
              </h3>
              <p className="text-xs text-text-secondary mt-0.5">
                Full tabulated records from BigQuery dataset `finshield.claims`.
              </p>
            </div>
            <span className="text-xs font-mono text-muted">
              Showing {ringDetail?.claims.length || 0} claims
            </span>
          </div>

          <div className="overflow-x-auto rounded-xl border border-white/8">
            <table className="w-full text-left text-xs text-text-primary">
              <thead className="bg-surface-elevated/80 border-b border-white/8 text-muted">
                <tr>
                  <th className="py-2.5 px-3 font-semibold">Claim ID</th>
                  <th className="py-2.5 px-3 font-semibold">Claimant</th>
                  <th className="py-2.5 px-3 font-semibold">Attending Doctor</th>
                  <th className="py-2.5 px-3 font-semibold">Hospital & City</th>
                  <th className="py-2.5 px-3 font-semibold">Admission</th>
                  <th className="py-2.5 px-3 text-right font-semibold">Total Claimed</th>
                  <th className="py-2.5 px-3 font-semibold">Fraud Type</th>
                  <th className="py-2.5 px-3 text-center font-semibold">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6 bg-surface-elevated/40">
                {ringDetail?.claims.map((claim) => (
                  <tr
                    key={claim.claim_id}
                    className="hover:bg-white/3 transition-colors"
                  >
                    <td className="py-2.5 px-3 font-mono font-medium text-amber-primary">
                      {claim.claim_id}
                    </td>
                    <td className="py-2.5 px-3 font-medium text-text-primary">
                      <div>{claim.claimant_name}</div>
                      <div className="text-[10px] text-muted font-mono">{claim.claimant_id}</div>
                    </td>
                    <td className="py-2.5 px-3 text-text-secondary font-mono">
                      {formatDoctor(claim.doctor_id)}
                    </td>
                    <td className="py-2.5 px-3 text-text-secondary">
                      <div>{claim.hospital_name}</div>
                      <div className="text-[10px] text-muted">{claim.city}</div>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-muted text-[11px]">
                      {formatDateTime(claim.admission_ts)}
                    </td>
                    <td className="py-2.5 px-3 text-right font-mono tabular-nums font-semibold text-text-primary">
                      {formatINR(claim.total_claimed)}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-400 border border-rose-500/20">
                        {claim.fraud_type}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <Link
                        to={`/claims/${claim.claim_id}`}
                        className="inline-flex items-center gap-1 px-3 py-1 rounded-lg bg-surface hover:bg-amber-primary hover:text-black text-amber-primary border border-amber-primary/30 transition-all text-[11px] font-medium"
                      >
                        <span>Audit</span>
                        <ArrowRight className="w-3 h-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
