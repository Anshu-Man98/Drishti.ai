import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, AlertTriangle, CheckCircle2, ShieldAlert,
  FileText, Building2, User, Calendar, RefreshCw,
  ExternalLink, Layers
} from 'lucide-react';
import { Claim, Dossier } from '../types';
import { fetchClaim, fetchDossier, analyzeClaim, getDocumentUrl } from '../services/api';

export const ClaimDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadClaimData = async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const c = await fetchClaim(id);
      setClaim(c);
      const d = await fetchDossier(id);
      setDossier(d);
    } catch (err: any) {
      setError(err.message || 'Failed to load claim');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadClaimData();
  }, [id]);

  const handleRunAnalysis = async () => {
    if (!id) return;
    try {
      setAnalyzing(true);
      const newDossier = await analyzeClaim(id);
      setDossier(newDossier);
    } catch (err: any) {
      alert(`Analysis failed: ${err.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center text-slate-400 space-y-4">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-500" />
        <p>Loading claim dossier...</p>
      </div>
    );
  }

  if (error || !claim) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center space-y-4">
        <ShieldAlert className="w-12 h-12 text-rose-500 mx-auto" />
        <h2 className="text-xl font-bold text-white">Claim Not Found</h2>
        <p className="text-slate-400 text-sm">{error || `Claim ${id} could not be located.`}</p>
        <Link to="/" className="inline-flex items-center text-blue-400 hover:underline text-sm">
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Claims Queue
        </Link>
      </div>
    );
  }

  const getVerdictBadge = (verdict: string) => {
    switch (verdict.toLowerCase()) {
      case 'approve':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-4 h-4" />
            <span>CLAIM APPROVED</span>
          </span>
        );
      case 'review':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-400 border border-amber-500/30">
            <AlertTriangle className="w-4 h-4" />
            <span>NEEDS MANUAL ADJUSTER REVIEW</span>
          </span>
        );
      case 'reject':
        return (
          <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/30">
            <ShieldAlert className="w-4 h-4" />
            <span>REJECT FRAUDULENT CLAIM</span>
          </span>
        );
      default:
        return null;
    }
  };

  const getRiskScoreColor = (score: number) => {
    if (score < 30) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
    if (score < 70) return 'text-amber-400 border-amber-500/30 bg-amber-500/10';
    return 'text-rose-400 border-rose-500/30 bg-rose-500/10';
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Header / Breadcrumb */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center space-x-3">
          <Link to="/" className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-slate-400 hover:text-white transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-xl font-bold text-white font-mono">{claim.claim_id}</h1>
              <span className="text-xs px-2.5 py-0.5 rounded bg-slate-800 text-slate-300 font-mono border border-slate-700">
                {claim.policy_id}
              </span>
              <span className="text-xs text-slate-400">{claim.insurer_id}</span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Claimant: <span className="text-slate-200 font-medium">{claim.claimant.name}</span> • Provider: <span className="text-slate-200 font-medium">{claim.provider.name}</span>
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={handleRunAnalysis}
            disabled={analyzing}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all shadow-lg ${
              analyzing
                ? 'bg-blue-600/50 text-blue-200 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20'
            }`}
          >
            <RefreshCw className={`w-4 h-4 ${analyzing ? 'animate-spin' : ''}`} />
            <span>{analyzing ? 'Running Agents...' : dossier ? 'Re-Analyze Claim' : 'Analyze Claim with ADK'}</span>
          </button>
        </div>
      </div>

      {/* Grid: Left Dossier / Agents, Right Metadata & Documents */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Copilot Dossier & Multi-Agent Findings */}
        <div className="lg:col-span-2 space-y-6">
          {/* Dossier Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-800">
              <div className="flex items-center space-x-4">
                <div className={`w-16 h-16 rounded-2xl border flex flex-col items-center justify-center ${dossier ? getRiskScoreColor(dossier.risk_score) : 'border-slate-800 bg-slate-950 text-slate-500'}`}>
                  <span className="text-2xl font-black font-mono leading-none">
                    {dossier ? dossier.risk_score : '--'}
                  </span>
                  <span className="text-[10px] tracking-wider uppercase font-semibold mt-1">Risk</span>
                </div>
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                    <span>Audit Verdict</span>
                  </h2>
                  <div className="mt-1">
                    {dossier ? getVerdictBadge(dossier.verdict) : (
                      <span className="text-xs text-slate-400">Click "Analyze Claim" to trigger agent audit</span>
                    )}
                  </div>
                </div>
              </div>

              {dossier?.ml_score !== null && dossier?.ml_score !== undefined && (
                <div className="px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-right">
                  <span className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold block">BigQuery ML Score</span>
                  <span className="text-sm font-mono font-bold text-blue-400">
                    {(dossier.ml_score * 100).toFixed(1)}% fraud probability
                  </span>
                </div>
              )}
            </div>

            {/* Executive Summary */}
            <div className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <FileText className="w-3.5 h-3.5 text-blue-400" />
                <span>Synthesis & Adjuster Summary</span>
              </h3>
              <p className="text-sm text-slate-200 leading-relaxed bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
                {dossier?.summary || 'No audit findings generated yet. Run the multi-agent pipeline to examine document forensics, policy limits, cross-insurer submissions, and trajectory spacetime feasibility.'}
              </p>
            </div>

            {/* 4 Agent Pipeline Status Cards */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <Layers className="w-3.5 h-3.5 text-indigo-400" />
                <span>ADK Multi-Agent Specialized Inspection</span>
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { name: 'Forensics', role: 'Tampering / ELA / Font' },
                  { name: 'Policy & Math', role: 'Caps & Arithmetic' },
                  { name: 'Cross-Ref', role: 'Duplicate Claims' },
                  { name: 'Spacetime', role: 'Impossible Travel' },
                ].map((agent, i) => (
                  <div key={i} className="p-3 rounded-xl bg-slate-950 border border-slate-800 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-white">{agent.name}</span>
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    </div>
                    <p className="text-[11px] text-slate-500">{agent.role}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Findings List */}
            {dossier?.findings && dossier.findings.length > 0 && (
              <div className="space-y-3 pt-4 border-t border-slate-800">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Flagged Anomalies ({dossier.findings.length})
                </h3>
                <div className="space-y-2">
                  {dossier.findings.map((f) => (
                    <div key={f.finding_id} className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex items-start space-x-3">
                      <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                      <div className="space-y-1 flex-1">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white font-mono">{f.title}</span>
                          <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            {f.severity}
                          </span>
                        </div>
                        <p className="text-xs text-slate-300">{f.explanation}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Itemized Bill Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
            <h3 className="text-sm font-bold text-white">Itemized Medical Bill Breakdown</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950 border-b border-slate-800 text-slate-400">
                  <tr>
                    <th className="py-2.5 px-3">Description</th>
                    <th className="py-2.5 px-3 text-right">Qty/Days</th>
                    <th className="py-2.5 px-3 text-right">Unit Price (₹)</th>
                    <th className="py-2.5 px-3 text-right">Total (₹)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {claim.line_items.map((item, idx) => (
                    <tr key={idx} className="hover:bg-slate-800/30">
                      <td className="py-2.5 px-3 font-medium text-white">{item.description}</td>
                      <td className="py-2.5 px-3 text-right font-mono">{item.qty}</td>
                      <td className="py-2.5 px-3 text-right font-mono">₹{item.unit_price.toLocaleString('en-IN')}</td>
                      <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-100">
                        ₹{item.amount.toLocaleString('en-IN')}
                      </td>
                    </tr>
                  ))}
                  <tr className="bg-slate-950 font-semibold text-slate-200">
                    <td colSpan={3} className="py-2.5 px-3 text-right text-slate-400">Subtotal:</td>
                    <td className="py-2.5 px-3 text-right font-mono">₹{claim.subtotal.toLocaleString('en-IN')}</td>
                  </tr>
                  <tr className="bg-slate-950 text-slate-300">
                    <td colSpan={3} className="py-2 px-3 text-right text-slate-400">Tax / GST:</td>
                    <td className="py-2 px-3 text-right font-mono">₹{claim.tax.toLocaleString('en-IN')}</td>
                  </tr>
                  <tr className="bg-slate-950 font-bold text-white border-t border-slate-700">
                    <td colSpan={3} className="py-3 px-3 text-right text-blue-400 text-sm">Total Claimed:</td>
                    <td className="py-3 px-3 text-right font-mono text-base text-blue-400">
                      ₹{claim.total_claimed.toLocaleString('en-IN')}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right Col: Metadata, Hospital Info, Attached Documents */}
        <div className="space-y-6">
          {/* Patient & Hospital Info Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4 text-xs">
            <h3 className="font-bold text-sm text-white flex items-center space-x-2">
              <User className="w-4 h-4 text-blue-400" />
              <span>Claimant Profile</span>
            </h3>
            <div className="space-y-2 bg-slate-950 p-3.5 rounded-xl border border-slate-800">
              <div className="flex justify-between">
                <span className="text-slate-500">Name:</span>
                <span className="font-medium text-white">{claim.claimant.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Phone:</span>
                <span className="font-mono text-slate-300">{claim.claimant.phone}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Bank Hash:</span>
                <span className="font-mono text-slate-400">{claim.claimant.bank_account_hash.slice(0, 12)}...</span>
              </div>
            </div>

            <h3 className="font-bold text-sm text-white flex items-center space-x-2 pt-2">
              <Building2 className="w-4 h-4 text-indigo-400" />
              <span>Healthcare Provider</span>
            </h3>
            <div className="space-y-2 bg-slate-950 p-3.5 rounded-xl border border-slate-800">
              <div className="flex justify-between">
                <span className="text-slate-500">Hospital:</span>
                <span className="font-medium text-white">{claim.provider.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">City / Geo:</span>
                <span className="text-slate-300">{claim.provider.city} ({claim.provider.lat}, {claim.provider.lng})</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Attending Doctor:</span>
                <span className="font-mono text-slate-300">{claim.doctor_id}</span>
              </div>
            </div>

            <h3 className="font-bold text-sm text-white flex items-center space-x-2 pt-2">
              <Calendar className="w-4 h-4 text-cyan-400" />
              <span>Hospitalization Timeline</span>
            </h3>
            <div className="space-y-2 bg-slate-950 p-3.5 rounded-xl border border-slate-800">
              <div className="flex justify-between">
                <span className="text-slate-500">Admission:</span>
                <span className="text-slate-300">{new Date(claim.admission_ts).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Discharge:</span>
                <span className="text-slate-300">{new Date(claim.discharge_ts).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Diagnosis Code:</span>
                <span className="font-mono text-blue-400 font-bold">{claim.diagnosis_code}</span>
              </div>
            </div>
          </div>

          {/* Attached Documents Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4">
            <h3 className="font-bold text-sm text-white flex items-center space-x-2">
              <FileText className="w-4 h-4 text-emerald-400" />
              <span>Uploaded Documents ({claim.documents.length})</span>
            </h3>

            {claim.documents.length === 0 ? (
              <p className="text-xs text-slate-500">No documents attached to this claim.</p>
            ) : (
              <div className="space-y-2.5">
                {claim.documents.map((doc) => (
                  <div key={doc.doc_id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                    <div className="space-y-0.5">
                      <p className="text-xs font-semibold text-white">{doc.filename || doc.doc_id}</p>
                      <p className="text-[11px] text-slate-500 font-mono">
                        {doc.doc_type} • {doc.sha256.slice(0, 10)}...
                      </p>
                    </div>
                    <a
                      href={getDocumentUrl(claim.claim_id, doc.doc_id)}
                      target="_blank"
                      rel="noreferrer"
                      className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-blue-400 transition-colors"
                      title="Open Document"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
