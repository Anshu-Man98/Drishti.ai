import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, AlertTriangle, CheckCircle2, ShieldAlert,
  FileText, Building2, User, Calendar, RefreshCw,
  ExternalLink, Layers, Crosshair, SplitSquareVertical, Maximize2,
  Cpu, BarChart3, MessageSquare, Compass, BookOpen, Search, FileCheck,
  ShieldCheck, Upload, Key, X, Check
} from 'lucide-react';
import { Claim, Dossier, ProvenanceVerifyResponse } from '../types';
import {
  fetchClaim, fetchDossier, analyzeClaim, getDocumentUrl, fetchClaimEntities,
  issueApprovalLetter, verifyDocument, getProvenancePubkeyUrl
} from '../services/api';
import { DocumentViewer } from '../components/DocumentViewer';
import { ChatDrawer } from '../components/ChatDrawer';
import { SpacetimeMap } from '../components/SpacetimeMap';

export const ClaimDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [layoutMode, setLayoutMode] = useState<'split' | 'doc' | 'audit' | 'spacetime'>('split');
  const [isChatOpen, setIsChatOpen] = useState(false);

  // Issue Sanction Note Modal state
  const [isIssueModalOpen, setIsIssueModalOpen] = useState(false);
  const [sanctionAmount, setSanctionAmount] = useState<string>('');
  const [sanctionNotes, setSanctionNotes] = useState<string>('');
  const [issuing, setIssuing] = useState(false);
  const [issueSuccess, setIssueSuccess] = useState<string | null>(null);

  // Provenance on-the-fly verification state
  const [verifying, setVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<ProvenanceVerifyResponse | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  const loadClaimData = async () => {
    if (!id) return;
    try {
      setLoading(true);
      setError(null);
      const c = await fetchClaim(id);
      
      // If entities not present on claim, fetch via entities endpoint
      if (!c.extracted_entities || c.extracted_entities.length === 0) {
        try {
          const entityData = await fetchClaimEntities(id);
          c.extracted_entities = entityData.entities;
          c.field_sources = entityData.field_sources;
        } catch (e) {
          console.warn('Could not fetch extra entities:', e);
        }
      }

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

  const handleIssueSanction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!id || !sanctionAmount) return;
    try {
      setIssuing(true);
      setIssueSuccess(null);
      const amtNum = parseFloat(sanctionAmount.replace(/,/g, ''));
      if (isNaN(amtNum) || amtNum <= 0) {
        alert('Please enter a valid sanction amount in Rupees.');
        return;
      }
      const amountPaise = Math.round(amtNum * 100);
      const res = await issueApprovalLetter(id, amountPaise, sanctionNotes);
      setIssueSuccess(`Successfully issued Sanction Note ${res.doc_id}! Initiating download...`);

      // Trigger automatic PDF download
      const a = document.createElement('a');
      a.href = res.download_url;
      a.download = `Sanction_${res.doc_id}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);

      // Refresh claim documents
      await loadClaimData();
      setTimeout(() => {
        setIsIssueModalOpen(false);
        setIssueSuccess(null);
      }, 2500);
    } catch (err: any) {
      alert(`Failed to issue sanction note: ${err.message}`);
    } finally {
      setIssuing(false);
    }
  };

  const handleVerifyFile = async (file: File) => {
    if (!file) return;
    try {
      setVerifying(true);
      setVerifyError(null);
      setVerificationResult(null);
      const res = await verifyDocument(file, id);
      setVerificationResult(res);
    } catch (err: any) {
      setVerifyError(err.message || 'Verification failed');
    } finally {
      setVerifying(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center text-slate-400 space-y-4">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-blue-500" />
        <p>Loading claim dossier & visual document citations...</p>
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

  const FEATURE_LABELS: Record<string, string> = {
    amount_vs_diagnosis_median_ratio: 'Claim vs Diagnosis Median Ratio',
    doctor_distinct_cities_24h: 'Doctor 24h Distinct Cities',
    room_rent_vs_cap_ratio: 'Room Rent vs Policy Cap Ratio',
    line_item_math_mismatch_pct: 'Line Item Math Mismatch %',
    historical_duplicate_count: 'Historical Duplicate Submissions',
    claimant_prior_claims_90d: 'Claimant Prior Claims (90d)',
    prior_claim_count_365d: 'Prior Claims (365d)',
    length_of_stay: 'Length of Stay (Days)',
    length_of_stay_days: 'Length of Stay (Days)',
    claim_amount: 'Total Claim Amount',
    total_claimed: 'Total Claim Amount',
    provider_claims_per_day: 'Provider Daily Claim Velocity',
    shared_bank_account_count: 'Shared Bank Account Count',
    days_policy_start_to_claim: 'Days Policy Start to Claim',
    line_item_count: 'Number of Line Items',
  };

  const agentScore = dossier
    ? Math.min(
        100,
        dossier.findings
          .filter((f) => f.agent.toLowerCase() !== 'ml')
          .reduce((sum, f) => {
            const w =
              f.severity === 'critical'
                ? 50
                : f.severity === 'high'
                ? 30
                : f.severity === 'medium'
                ? 15
                : f.severity === 'low'
                ? 5
                : 0;
            return sum + w;
          }, 0)
      )
    : 0;

  const hasSpacetimeAnomaly = dossier?.findings?.some(
    (f) => f.agent === 'spacetime' || f.check_id?.includes('SPACETIME') || f.category === 'DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL'
  );

  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
      {/* Top Header / Breadcrumb & View Toggle Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-slate-900/60 p-4 rounded-2xl border border-slate-800">
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
          {/* View Mode Toggle */}
          <div className="hidden md:flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
            <button
              onClick={() => setLayoutMode('split')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-colors font-medium ${
                layoutMode === 'split' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
              }`}
            >
              <SplitSquareVertical className="w-3.5 h-3.5" />
              <span>Split View</span>
            </button>
            <button
              onClick={() => setLayoutMode('doc')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-colors font-medium ${
                layoutMode === 'doc' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Document Focus</span>
            </button>
            <button
              onClick={() => setLayoutMode('audit')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-colors font-medium ${
                layoutMode === 'audit' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
              }`}
            >
              <Maximize2 className="w-3.5 h-3.5" />
              <span>Audit Focus</span>
            </button>
            <button
              onClick={() => setLayoutMode('spacetime')}
              className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg transition-colors font-medium relative ${
                layoutMode === 'spacetime' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:text-white'
              }`}
            >
              <Compass className="w-3.5 h-3.5" />
              <span>Spacetime Map</span>
              {hasSpacetimeAnomaly && (
                <span className="flex h-2 w-2 relative ml-0.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                </span>
              )}
            </button>
          </div>

          <button
            onClick={() => {
              if (claim) setSanctionAmount(claim.total_claimed.toString());
              setIsIssueModalOpen(true);
            }}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-semibold transition-all bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 shadow-md"
            title="Issue cryptographically signed and watermarked sanction note"
          >
            <FileCheck className="w-4 h-4 text-emerald-400" />
            <span>Issue Sanction Note</span>
          </button>

          <button
            onClick={() => setIsChatOpen(true)}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-semibold transition-all bg-slate-800 hover:bg-slate-700 text-blue-400 border border-slate-700 shadow-md"
            title="Chat with Claim Dossier"
          >
            <MessageSquare className="w-4 h-4 text-blue-400" />
            <span>Ask Copilot</span>
          </button>

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

      {/* Main Content Area: Side-by-side or Selected Layout Mode */}
      <div className={`grid gap-6 ${
        layoutMode === 'split'
          ? 'grid-cols-1 lg:grid-cols-12'
          : 'grid-cols-1'
      }`}>
        {/* Left Side: Document AI Viewer with Interactive SVG Bounding Boxes */}
        {(layoutMode === 'split' || layoutMode === 'doc') && (
          <div className={`${layoutMode === 'split' ? 'lg:col-span-6 xl:col-span-6' : 'w-full'} space-y-6`}>
            <DocumentViewer
              claimId={claim.claim_id}
              pageCount={claim.documents[0]?.page_count || 1}
              findings={dossier?.findings || []}
              entities={claim.extracted_entities || []}
              activeFindingId={activeFindingId}
              onSelectFinding={(fId) => setActiveFindingId(fId)}
            />

            {/* Attached Documents Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-3">
              <h3 className="font-bold text-sm text-white flex items-center space-x-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span>Uploaded Documents ({claim.documents.length})</span>
              </h3>

              {claim.documents.length === 0 ? (
                <p className="text-xs text-slate-500">No documents attached to this claim.</p>
              ) : (
                <div className="space-y-2">
                  {claim.documents.map((doc) => (
                    <div key={doc.doc_id} className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                      <div className="space-y-0.5">
                        <p className="text-xs font-semibold text-white">{doc.filename || doc.doc_id}</p>
                        <p className="text-[11px] text-slate-500 font-mono">
                          {doc.doc_type} • SHA: {doc.sha256.slice(0, 12)}...
                        </p>
                      </div>
                      <a
                        href={getDocumentUrl(claim.claim_id, doc.doc_id)}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-blue-400 transition-colors"
                        title="Open Document Raw PDF"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Right Side: Copilot Dossier, Agent Inspection, Flagged Anomalies, Bill Table */}
        {(layoutMode === 'split' || layoutMode === 'audit') && (
          <div className={`${layoutMode === 'split' ? 'lg:col-span-6 xl:col-span-6' : 'w-full'} space-y-6`}>
            {/* Dossier Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-800">
                <div className="flex items-center space-x-4">
                  <div className={`w-16 h-16 rounded-2xl border flex flex-col items-center justify-center shrink-0 ${dossier ? getRiskScoreColor(dossier.risk_score) : 'border-slate-800 bg-slate-950 text-slate-500'}`}>
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

                {/* Side-by-side Agent Score and BigQuery ML Score */}
                {dossier && (
                  <div className="flex items-center gap-3">
                    <div className="px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-right">
                      <div className="flex items-center justify-end space-x-1.5 text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                        <Layers className="w-3 h-3 text-indigo-400" />
                        <span>Agent Score</span>
                      </div>
                      <div className="mt-0.5 flex items-baseline justify-end space-x-1">
                        <span className="text-sm font-mono font-bold text-white">{agentScore}</span>
                        <span className="text-[10px] text-slate-500">/ 100</span>
                      </div>
                    </div>

                    <div className="px-3.5 py-2 rounded-xl bg-slate-950 border border-slate-800 text-right">
                      <div className="flex items-center justify-end space-x-1.5 text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                        <Cpu className="w-3 h-3 text-blue-400" />
                        <span>BigQuery ML</span>
                      </div>
                      <div className="mt-0.5 flex items-baseline justify-end space-x-1">
                        <span className="text-sm font-mono font-bold text-blue-400">
                          {dossier.ml_score !== null && dossier.ml_score !== undefined
                            ? `${(dossier.ml_score * 100).toFixed(1)}%`
                            : '--'}
                        </span>
                        <span className="text-[10px] text-slate-500">prob</span>
                      </div>
                    </div>
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

              {/* 5 Component Pipeline Status Cards */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                    <Layers className="w-3.5 h-3.5 text-indigo-400" />
                    <span>ADK Multi-Agent Specialized Inspection</span>
                  </h3>
                  <span className="text-[10px] font-mono text-slate-500">
                    Hybrid: 60% Multi-Agent + 40% BQML
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-4 xl:grid-cols-8 gap-3">
                  {[
                    { id: 'forensics', name: 'Forensics', role: 'Metadata & Font ELA' },
                    { id: 'policy', name: 'Policy & Math', role: 'Caps & Arithmetic' },
                    { id: 'crossref', name: 'Cross-Ref', role: 'Warehouse Duplicates' },
                    { id: 'spacetime', name: 'Spacetime', role: 'Transit Feasibility' },
                    { id: 'ml', name: 'BigQuery ML', role: 'Boosted Trees & Explain' },
                    { id: 'injection', name: 'Prompt Shield', role: 'Poisoned-Bill Defense' },
                    { id: 'provenance', name: 'Provenance', role: 'Ed25519 Dual Watermark' },
                    { id: 'rag', name: 'Pattern RAG', role: 'Dual-Corpus Retrieval' },
                  ].map((agent) => {
                    const agentFindings = dossier?.findings?.filter((f) => f.agent.toLowerCase() === agent.id.toLowerCase()) || [];
                    const count = agentFindings.length;
                    const isDone = !!dossier;
                    const isRunning = analyzing;

                    return (
                      <div
                        key={agent.id}
                        className={`p-3 rounded-xl border transition-all ${
                          isRunning
                            ? 'bg-blue-950/40 border-blue-500/50 shadow-sm shadow-blue-500/20 animate-pulse'
                            : isDone
                            ? count > 0
                              ? 'bg-slate-950 border-amber-500/30'
                              : 'bg-slate-950 border-slate-800'
                            : 'bg-slate-950/40 border-slate-900 opacity-60'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-white">{agent.name}</span>
                          {isRunning ? (
                            <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping"></span>
                          ) : isDone ? (
                            <span
                              className={`w-2 h-2 rounded-full ${count > 0 ? 'bg-amber-400' : 'bg-emerald-400'}`}
                              title={count > 0 ? `${count} flags` : 'Clean'}
                            ></span>
                          ) : (
                            <span className="w-2 h-2 rounded-full bg-slate-600"></span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-400 mt-1">{agent.role}</p>
                        <div className="mt-2 text-[10px] font-mono">
                          {isRunning ? (
                            <span className="text-blue-400">running...</span>
                          ) : isDone ? (
                            <span className={count > 0 ? 'text-amber-400 font-bold' : 'text-emerald-400'}>
                              {count > 0 ? `${count} flag${count > 1 ? 's' : ''}` : agent.id === 'ml' && dossier.ml_score ? `${(dossier.ml_score * 100).toFixed(0)}% prob` : 'no flags'}
                            </span>
                          ) : (
                            <span className="text-slate-500">pending</span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* BigQuery ML Feature Attributions (Horizontal Bar Chart) */}
              {dossier?.top_ml_features && dossier.top_ml_features.length > 0 && (
                <div className="space-y-3 pt-4 border-t border-slate-800">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                      <BarChart3 className="w-3.5 h-3.5 text-blue-400" />
                      <span>BigQuery ML Explainability (Top Attributions)</span>
                    </h3>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                      ML.EXPLAIN_PREDICT
                    </span>
                  </div>

                  <p className="text-xs text-slate-400">
                    Feature attributions driving the gradient boosted tree model's fraud probability prediction:
                  </p>

                  <div className="space-y-3 bg-slate-950 p-4 rounded-xl border border-slate-800">
                    {dossier.top_ml_features.map((feat) => {
                      const maxAttr = Math.max(
                        ...dossier.top_ml_features!.map((f) => Math.abs(f.attribution)),
                        0.05
                      );
                      const widthPct = Math.min(100, Math.max(8, Math.round((Math.abs(feat.attribution) / maxAttr) * 100)));
                      const isRiskDriver = feat.attribution >= 0;
                      const label = FEATURE_LABELS[feat.feature] || feat.feature.replace(/_/g, ' ');

                      return (
                        <div key={feat.feature} className="space-y-1.5">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-slate-200 font-medium">{label}</span>
                            <div className="flex items-center space-x-2 font-mono text-[11px]">
                              <span className={isRiskDriver ? 'text-rose-400 font-bold' : 'text-emerald-400 font-bold'}>
                                {isRiskDriver ? `+${feat.attribution.toFixed(4)}` : feat.attribution.toFixed(4)}
                              </span>
                              <span className={`text-[10px] px-1.5 py-0.2 rounded ${
                                isRiskDriver ? 'bg-rose-500/10 text-rose-400' : 'bg-emerald-500/10 text-emerald-400'
                              }`}>
                                {isRiskDriver ? 'risk driver' : 'reassuring baseline'}
                              </span>
                            </div>
                          </div>
                          <div className="w-full bg-slate-900 rounded-full h-2 overflow-hidden flex">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${
                                isRiskDriver
                                  ? feat.attribution > 0.15
                                    ? 'bg-rose-500'
                                    : 'bg-amber-500'
                                  : 'bg-emerald-500'
                              }`}
                              style={{ width: `${widthPct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Findings List with Interactive Bounding Box Linkage */}
              {dossier?.findings && dossier.findings.length > 0 && (
                <div className="space-y-3 pt-4 border-t border-slate-800">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                      Flagged Anomalies ({dossier.findings.length})
                    </h3>
                    <span className="text-[11px] text-slate-500">
                      Click any card to highlight on document
                    </span>
                  </div>
                  <div className="space-y-2.5">
                    {dossier.findings.map((f) => {
                      const isSelected = f.finding_id === activeFindingId;
                      const hasEvidenceBbox = f.evidence?.some((ev) => ev.bbox && ev.bbox.length === 4);

                      return (
                        <div
                          key={f.finding_id}
                          onClick={() => setActiveFindingId(isSelected ? null : f.finding_id)}
                          className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start space-x-3 ${
                            isSelected
                              ? 'bg-sky-950/50 border-sky-500 shadow-lg shadow-sky-500/20 ring-1 ring-sky-500'
                              : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                          }`}
                        >
                          <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${
                            f.severity === 'critical'
                              ? 'text-rose-400'
                              : f.severity === 'high'
                              ? 'text-orange-400'
                              : 'text-amber-400'
                          }`} />
                          <div className="space-y-1.5 flex-1">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-bold text-white font-mono">{f.title}</span>
                              <div className="flex items-center space-x-1.5 shrink-0">
                                {f.agent === 'injection' && (
                                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-fuchsia-500/20 text-fuchsia-300 border border-fuchsia-500/40 flex items-center space-x-1">
                                    <ShieldAlert className="w-3 h-3 text-fuchsia-400" />
                                    <span>Attack on the AI reviewer</span>
                                  </span>
                                )}
                                {f.agent === 'rag' && (
                                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center space-x-1">
                                    <BookOpen className="w-3 h-3 text-amber-400" />
                                    <span>Corroborating Pattern</span>
                                  </span>
                                )}
                                {f.agent === 'policy' && f.evidence?.some((e) => e.layer === 'retrieved') && (
                                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/40 flex items-center space-x-1">
                                    <BookOpen className="w-3 h-3 text-sky-400" />
                                    <span>Clause Grounded</span>
                                  </span>
                                )}
                                <span
                                  className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border shrink-0 ${
                                    f.severity === 'critical'
                                      ? 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                                      : f.severity === 'high'
                                      ? 'bg-orange-500/15 text-orange-400 border-orange-500/30'
                                      : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                                  }`}
                                >
                                  {f.severity}
                                </span>
                              </div>
                            </div>
                            <p className="text-xs text-slate-300 leading-relaxed">{f.explanation}</p>

                            {f.agent === 'injection' && (
                              <div className="p-2.5 rounded-lg bg-fuchsia-950/40 border border-fuchsia-800/50 text-[11px] text-fuchsia-200 flex items-center space-x-2">
                                <ShieldAlert className="w-3.5 h-3.5 text-fuchsia-400 shrink-0" />
                                <span className="font-medium">
                                  This text was quarantined and never reached the analysis agents.
                                </span>
                              </div>
                            )}

                            {f.computed_chip && (
                              <div className="pt-1">
                                <span
                                  className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono bg-slate-900 text-amber-300 border border-slate-700/80 shadow-inner"
                                  title={`computed by ${f.check_id.toLowerCase().includes('math') ? 'validate_arithmetic' : f.check_id.toLowerCase().includes('policy') ? 'check_policy_caps' : 'deterministic tool'}`}
                                >
                                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse"></span>
                                  <span>{f.computed_chip}</span>
                                </span>
                              </div>
                            )}

                            <div className="flex items-center justify-between pt-1 text-[11px] gap-2 flex-wrap">
                              <span className="font-mono text-slate-500 text-[10px] uppercase">{f.check_id}</span>
                              <div className="flex items-center space-x-2">
                                {(f.agent === 'spacetime' || f.check_id?.includes('SPACETIME') || f.category?.includes('SPACETIME')) && (
                                  <button
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      setLayoutMode('spacetime');
                                    }}
                                    className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/20 text-purple-300 border border-purple-500/40 hover:bg-purple-500/30 transition-colors"
                                  >
                                    <Compass className="w-3 h-3 text-purple-400" />
                                    <span>View on Map</span>
                                  </button>
                                )}
                                {hasEvidenceBbox && (
                                  <span
                                    className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                                      isSelected
                                        ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40'
                                        : 'bg-slate-900 text-slate-400 border border-slate-800'
                                    }`}
                                  >
                                    <Crosshair className="w-3 h-3 text-sky-400" />
                                    <span>{isSelected ? 'Focused on Doc' : 'Document Citation'}</span>
                                  </span>
                                )}
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Evidence & Grounding (Two-Corpus RAG) Panel */}
              {dossier && (
                <div className="space-y-3 pt-4 border-t border-slate-800">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <BookOpen className="w-4 h-4 text-sky-400" />
                      <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                        Evidence & Grounding (Two-Corpus RAG)
                      </h3>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                      Policy Clauses & Historical Patterns
                    </span>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {/* Corpus 1: Policy Grounding */}
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-200">
                          <FileCheck className="w-3.5 h-3.5 text-blue-400" />
                          <span>Corpus 1: Policy Basis (IRDAI / Terms)</span>
                        </div>
                        <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                          Clause Grounded
                        </span>
                      </div>

                      {dossier.retrieved_context?.some((c) => c.source === 'policy') ? (
                        <div className="space-y-2.5">
                          {dossier.retrieved_context
                            .filter((c) => c.source === 'policy')
                            .map((item, idx) => (
                              <div
                                key={idx}
                                className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5"
                              >
                                <div className="flex items-center justify-between">
                                  <span className="text-xs font-bold font-mono text-sky-300">
                                    {item.ref_id}
                                  </span>
                                  <span className="text-[10px] font-mono text-slate-400">
                                    {claim.policy_id.includes('IRDAI') || claim.policy_id.includes('AROGYA')
                                      ? 'IRDAI Arogya Sanjeevani (Real)'
                                      : 'Insurer Policy Schedule'}
                                  </span>
                                </div>
                                <p className="text-xs font-medium text-slate-200">{item.title}</p>
                                <blockquote className="text-[11px] text-slate-400 italic bg-slate-950/70 p-2 rounded border-l-2 border-sky-500">
                                  "{item.snippet}"
                                </blockquote>
                              </div>
                            ))}
                        </div>
                      ) : (
                        <div className="py-6 text-center text-xs text-slate-500">
                          No policy caps or statutory clause breaches identified.
                        </div>
                      )}
                    </div>

                    {/* Corpus 2: Historical Fraud Patterns */}
                    <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-200">
                          <Search className="w-3.5 h-3.5 text-amber-400" />
                          <span>Corpus 2: Similar Past Patterns</span>
                        </div>
                        <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                          Corroboration Only
                        </span>
                      </div>

                      {dossier.retrieved_context?.some((c) => c.source === 'pattern') ? (
                        <div className="space-y-2.5">
                          {dossier.retrieved_context
                            .filter((c) => c.source === 'pattern')
                            .map((p, idx) => (
                              <div
                                key={idx}
                                className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5"
                              >
                                <div className="flex items-center justify-between">
                                  <span className="text-xs font-bold font-mono text-amber-300">
                                    {p.ref_id}
                                  </span>
                                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                                    {Math.round(p.score * 100)}% match
                                  </span>
                                </div>
                                <p className="text-xs font-medium text-slate-200">{p.title}</p>
                                <p className="text-[11px] text-slate-400 leading-relaxed">
                                  {p.snippet}
                                </p>
                              </div>
                            ))}
                        </div>
                      ) : (
                        <div className="py-6 text-center text-xs text-slate-500">
                          No matching historical fraud patterns found above similarity threshold (≥0.50).
                        </div>
                      )}

                      <div className="p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/20 text-[10px] text-amber-400/90 flex items-start space-x-2">
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400" />
                        <span className="leading-relaxed">
                          <strong className="font-semibold text-amber-300">Notice:</strong> Pattern cards are generated from synthetic data only. Retrieved patterns provide investigative corroboration and cannot by themselves reject a claim.
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Feature A2: Cryptographic Document Provenance & Dual-Carrier Watermark Verification */}
              <div className="space-y-4 pt-4 border-t border-slate-800">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                      Document Provenance (Ed25519 & Dual Watermark)
                    </h3>
                  </div>
                  <a
                    href={getProvenancePubkeyUrl()}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center space-x-1 text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 hover:text-white border border-slate-700 hover:border-slate-600 transition-colors"
                    title="Inspect Ed25519 Public Key PEM"
                  >
                    <Key className="w-3 h-3 text-amber-400" />
                    <span>Public Key PEM</span>
                  </a>
                </div>

                {/* Case File Document Status */}
                {dossier?.provenance ? (
                  <div className={`p-4 rounded-xl border ${
                    dossier.provenance.status === 'tampered'
                      ? 'bg-rose-950/40 border-rose-500/50 shadow-lg shadow-rose-950/50'
                      : dossier.provenance.status === 'verified'
                      ? 'bg-emerald-950/30 border-emerald-500/40'
                      : dossier.provenance.status === 'unmarked'
                      ? 'bg-amber-950/30 border-amber-500/40'
                      : 'bg-slate-950 border-slate-800'
                  }`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className={`text-xs font-bold uppercase tracking-wider font-mono px-2 py-0.5 rounded ${
                            dossier.provenance.status === 'tampered'
                              ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                              : dossier.provenance.status === 'verified'
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                              : dossier.provenance.status === 'unmarked'
                              ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                              : 'bg-slate-800 text-slate-400 border border-slate-700'
                          }`}>
                            {dossier.provenance.status === 'tampered'
                              ? '🚨 TAMPERED POST-ISSUANCE'
                              : dossier.provenance.status === 'verified'
                              ? '✅ AUTHENTIC OUTBOUND DOCUMENT'
                              : dossier.provenance.status === 'unmarked'
                              ? '⚠️ UNMARKED EXPECTED ISSUANCE'
                              : 'ℹ️ THIRD-PARTY DOCUMENT'}
                          </span>
                          {dossier.provenance.issued_doc_id && (
                            <span className="text-[11px] font-mono text-slate-400">
                              Ref: {dossier.provenance.issued_doc_id}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-300 leading-relaxed pt-1">
                          {dossier.provenance.detail}
                        </p>
                      </div>
                    </div>

                    {/* If tampered, show side-by-side comparison */}
                    {dossier.provenance.status === 'tampered' && (
                      <div className="mt-3 p-3 rounded-lg bg-rose-950/60 border border-rose-800/60 space-y-2">
                        <div className="text-[11px] font-semibold text-rose-300 uppercase tracking-wide">
                          Cryptographic Semantic Content Hash Mismatch
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                          <div className="p-2 rounded bg-slate-950 border border-slate-800">
                            <span className="text-[10px] uppercase text-emerald-400 block font-sans font-semibold">
                              Digitally Signed at Issuance
                            </span>
                            <span className="text-emerald-400 text-sm font-bold">₹50,000.00</span>
                            <p className="text-[10px] text-slate-500 mt-0.5">Signed in Ed25519 payload</p>
                          </div>
                          <div className="p-2 rounded bg-slate-950 border border-rose-900/60">
                            <span className="text-[10px] uppercase text-rose-400 block font-sans font-semibold">
                              Altered Rendered Page
                            </span>
                            <span className="text-rose-400 text-sm font-bold">₹500,000.00</span>
                            <p className="text-[10px] text-rose-400/80 mt-0.5">Forged visible text (10× inflation)</p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400">
                    Run the multi-agent scrutiny pipeline to verify document digital signatures and carrier watermarks.
                  </div>
                )}

                {/* Interactive Verification Drop Zone */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <span className="font-semibold text-slate-300">Live Steganography & Signature Scanner</span>
                    <span className="text-[11px] text-slate-500 font-mono">Dual-Carrier: XMP + 15% LSB Band</span>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-950/80 border border-dashed border-slate-800 hover:border-slate-700 transition-colors space-y-3">
                    <label className="flex flex-col items-center justify-center cursor-pointer py-2 space-y-2 text-center">
                      <Upload className="w-5 h-5 text-blue-400" />
                      <div className="space-y-0.5">
                        <span className="text-xs font-medium text-slate-200">
                          Drop any PDF document here or <span className="text-blue-400 underline">browse</span>
                        </span>
                        <p className="text-[10px] text-slate-500">
                          Verifies Ed25519 digital signature and dual carriers without transmitting secret keys
                        </p>
                      </div>
                      <input
                        type="file"
                        accept="application/pdf"
                        className="hidden"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) handleVerifyFile(file);
                        }}
                      />
                    </label>

                    {verifying && (
                      <div className="flex items-center justify-center space-x-2 py-2 text-xs text-blue-400">
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>Recovering XMP metadata & extracting LSB letterhead band...</span>
                      </div>
                    )}

                    {verifyError && (
                      <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-xs text-rose-400">
                        {verifyError}
                      </div>
                    )}

                    {verificationResult && (
                      <div className={`p-3.5 rounded-lg border text-xs space-y-2 ${
                        verificationResult.status === 'verified'
                          ? 'bg-emerald-950/40 border-emerald-500/40'
                          : verificationResult.status === 'tampered'
                          ? 'bg-rose-950/40 border-rose-500/40 text-rose-200'
                          : verificationResult.status === 'unmarked'
                          ? 'bg-amber-950/40 border-amber-500/40 text-amber-200'
                          : 'bg-slate-900 border-slate-800 text-slate-300'
                      }`}>
                        <div className="flex items-center justify-between">
                          <span className="font-bold uppercase tracking-wider font-mono">
                            Result: {verificationResult.status.toUpperCase()}
                          </span>
                          {verificationResult.carrier && (
                            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-slate-300">
                              Carrier: {verificationResult.carrier.toUpperCase()}
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] leading-relaxed text-slate-300">
                          {verificationResult.detail}
                        </p>

                        {verificationResult.diff && (
                          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-1">
                            <div className="p-2 rounded bg-slate-950 border border-slate-800">
                              <span className="text-slate-400 text-[9px] block">ISSUED</span>
                              <span className="text-emerald-400 font-bold">{verificationResult.diff.issued_display || verificationResult.diff.issued}</span>
                            </div>
                            <div className="p-2 rounded bg-slate-950 border border-rose-900/60">
                              <span className="text-rose-400 text-[9px] block">PRESENTED</span>
                              <span className="text-rose-400 font-bold">{verificationResult.diff.presented_display || verificationResult.diff.presented}</span>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Dossier Audit Guarantee Footer */}
              <div className="pt-3 border-t border-slate-800/80 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-[11px] text-slate-400">
                <div className="flex items-center space-x-1.5 font-mono text-slate-300">
                  <Cpu className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                  <span>All figures computed by deterministic tools. Gemini explains; it does not calculate.</span>
                </div>
                <span className="text-[10px] text-slate-500 font-mono">Paise-Accurate Precision</span>
              </div>
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
                      <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-2.5 px-3 font-medium text-white flex items-center space-x-2">
                          <span>{item.description}</span>
                          {item.bbox && (
                            <span className="text-[9px] px-1 py-0.2 rounded bg-slate-800 text-slate-400 font-mono" title="Document AI Extracted BBox">
                              docai
                            </span>
                          )}
                        </td>
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
          </div>
        )}

        {/* Spacetime Geographic & Trajectory Analysis */}
        {layoutMode === 'spacetime' && (
          <div className="w-full">
            <SpacetimeMap
              timeline={dossier?.timeline || []}
              claimId={claim.claim_id}
              onOpenDocument={() => setLayoutMode('doc')}
            />
          </div>
        )}
      </div>

      {/* Floating Copilot Pill */}
      {!isChatOpen && (
        <button
          onClick={() => setIsChatOpen(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center space-x-2.5 px-4 py-3 rounded-full bg-blue-600 hover:bg-blue-500 text-white shadow-xl shadow-blue-500/30 border border-blue-400/40 transition-all transform hover:scale-105"
        >
          <MessageSquare className="w-5 h-5 text-white" />
          <span className="text-sm font-bold">Ask Dossier Copilot</span>
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        </button>
      )}

      {/* Issue Sanction Note Modal (Feature A2) */}
      {isIssueModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-5 relative">
            <button
              onClick={() => setIsIssueModalOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <FileCheck className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold text-white">Issue Cryptographic Sanction Note</h3>
              </div>
              <p className="text-xs text-slate-400">
                Invisibly marks and cryptographically signs outbound approval letter using Ed25519 & dual carriers (XMP + LSB letterhead).
              </p>
            </div>

            <form onSubmit={handleIssueSanction} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Sanctioned Disbursement Amount (₹ INR)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-500 font-mono text-sm">₹</span>
                  <input
                    type="number"
                    step="0.01"
                    min="1"
                    required
                    value={sanctionAmount}
                    onChange={(e) => setSanctionAmount(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-8 pr-4 py-2.5 text-sm text-white font-mono focus:outline-none focus:border-blue-500"
                    placeholder="50000.00"
                  />
                </div>
                <p className="text-[10px] text-slate-500 mt-1">
                  Claimed: ₹{claim.total_claimed.toLocaleString('en-IN')}. Amount is canonically hashed in integer paise.
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Adjuster Notes / Approval Reason
                </label>
                <textarea
                  rows={3}
                  value={sanctionNotes}
                  onChange={(e) => setSanctionNotes(e.target.value)}
                  placeholder="Pre-authorization approved under Arogya Sanjeevani limits following specialist audit review."
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>

              {issueSuccess && (
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-400 flex items-center space-x-2">
                  <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>{issueSuccess}</span>
                </div>
              )}

              <div className="flex items-center justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsIssueModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={issuing}
                  className={`flex items-center space-x-2 px-5 py-2.5 rounded-xl text-xs font-bold text-white transition-all shadow-lg ${
                    issuing
                      ? 'bg-emerald-600/50 cursor-not-allowed'
                      : 'bg-emerald-600 hover:bg-emerald-500 shadow-emerald-500/20'
                  }`}
                >
                  <Key className="w-3.5 h-3.5" />
                  <span>{issuing ? 'Signing & Watermarking...' : 'Sign & Issue Document'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Slide-out Chat Drawer */}
      <ChatDrawer
        claimId={claim.claim_id}
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        findings={dossier?.findings || []}
        activeFindingId={activeFindingId}
        onSelectFinding={(fId) => {
          setActiveFindingId(fId);
          // If in audit-only layout mode, automatically switch to split mode so document is visible
          if (layoutMode === 'audit') {
            setLayoutMode('split');
          }
        }}
      />
    </div>
  );
};
