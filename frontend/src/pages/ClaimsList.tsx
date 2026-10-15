import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, ShieldAlert, CheckCircle2, AlertTriangle, ArrowUpRight, Filter, Building2, User, RefreshCw } from 'lucide-react';
import { ClaimSummary } from '../types';
import { fetchClaims } from '../services/api';

export const ClaimsList: React.FC = () => {
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterVerdict, setFilterVerdict] = useState<string>('all');

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchClaims();
      setClaims(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load claims');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filtered = claims.filter((c) => {
    const matchesSearch =
      c.claim_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.claimant_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.hospital_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.city.toLowerCase().includes(searchTerm.toLowerCase());

    if (filterVerdict === 'all') return matchesSearch;
    if (filterVerdict === 'unreviewed') return matchesSearch && !c.verdict;
    return matchesSearch && c.verdict?.toLowerCase() === filterVerdict;
  });

  const getVerdictBadge = (verdict?: string, score?: number) => {
    if (!verdict) {
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
          Pending Audit
        </span>
      );
    }
    switch (verdict.toLowerCase()) {
      case 'approve':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            <span>Approve {score !== undefined && `(${score})`}</span>
          </span>
        );
      case 'review':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertTriangle className="w-3 h-3" />
            <span>Review {score !== undefined && `(${score})`}</span>
          </span>
        );
      case 'reject':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <ShieldAlert className="w-3 h-3" />
            <span>Reject {score !== undefined && `(${score})`}</span>
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Title & Quick Stats */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center space-x-2">
            <span>Claims Audit Queue</span>
            <span className="text-xs px-2.5 py-0.5 rounded-md bg-blue-500/10 text-blue-400 border border-blue-500/20">
              {claims.length} claims registered
            </span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Automated scrutiny across Forensics, Policy Caps, Cross-Insurer Duplicates & Spacetime Trajectories.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={loadData}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm font-medium transition-colors border border-slate-700"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <Link
            to="/upload"
            className="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/20 transition-colors"
          >
            <span>+ New Claim</span>
          </Link>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="relative w-full sm:w-96">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search claimant, hospital, city or claim ID..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>
        <div className="flex items-center space-x-2 w-full sm:w-auto">
          <Filter className="w-4 h-4 text-slate-400" />
          <span className="text-xs text-slate-400">Verdict:</span>
          {['all', 'approve', 'review', 'reject', 'unreviewed'].map((v) => (
            <button
              key={v}
              onClick={() => setFilterVerdict(v)}
              className={`px-2.5 py-1 rounded-md text-xs font-medium capitalize transition-colors ${
                filterVerdict === v
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* Claims Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="p-12 text-center text-slate-400 space-y-3">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-500" />
            <p className="text-sm">Loading claims audit database...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-400 space-y-2">
            <ShieldAlert className="w-8 h-8 mx-auto" />
            <p className="text-sm font-medium">{error}</p>
            <p className="text-xs text-slate-500">Ensure the FastAPI backend is running on port 8000.</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-12 text-center text-slate-400 space-y-3">
            <p className="text-sm">No claims match the selected criteria.</p>
            <Link to="/upload" className="text-xs text-blue-400 hover:underline">Upload a claim PDF to start</Link>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-950/60 border-b border-slate-800 text-xs uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="py-3.5 px-4 font-semibold">Claim ID</th>
                  <th className="py-3.5 px-4 font-semibold">Claimant</th>
                  <th className="py-3.5 px-4 font-semibold">Hospital & City</th>
                  <th className="py-3.5 px-4 font-semibold">Diagnosis</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Claim Amount</th>
                  <th className="py-3.5 px-4 font-semibold text-center">Audit Verdict</th>
                  <th className="py-3.5 px-4 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {filtered.map((c) => (
                  <tr key={c.claim_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-4 px-4 font-mono text-xs text-blue-400 font-medium">
                      {c.claim_id}
                      <span className="block text-[11px] text-slate-500 font-sans">{c.policy_id}</span>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center space-x-2">
                        <User className="w-3.5 h-3.5 text-slate-500" />
                        <span className="font-medium text-white">{c.claimant_name}</span>
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center space-x-2">
                        <Building2 className="w-3.5 h-3.5 text-slate-500" />
                        <span>{c.hospital_name}</span>
                      </div>
                      <span className="text-xs text-slate-500 block pl-5">{c.city}</span>
                    </td>
                    <td className="py-4 px-4 font-mono text-xs text-slate-400">
                      {c.diagnosis_code}
                    </td>
                    <td className="py-4 px-4 text-right font-medium text-white">
                      ₹{c.total_claimed.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-4 px-4 text-center">
                      {getVerdictBadge(c.verdict, c.risk_score)}
                    </td>
                    <td className="py-4 px-4 text-right">
                      <Link
                        to={`/claims/${c.claim_id}`}
                        className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-blue-600 hover:text-white text-slate-300 text-xs font-medium transition-all group"
                      >
                        <span>Audit</span>
                        <ArrowUpRight className="w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
