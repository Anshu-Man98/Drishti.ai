import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ShieldAlert, RefreshCw, MessageSquare } from 'lucide-react';
import { useAssistant } from '../context/AssistantContext';
import { Claim, Dossier, ProvenanceVerifyResponse } from '../types';
import {
  fetchClaim,
  fetchDossier,
  analyzeClaim,
  fetchClaimEntities,
  issueApprovalLetter,
  verifyDocument,
  downloadAuthenticatedFile,
} from '../services/api';

import { ClaimHeader } from '../components/claim/ClaimHeader';
import { VerdictSummaryCard } from '../components/claim/VerdictSummaryCard';
import { ActivePipelineNodes } from '../components/claim/ActivePipelineNodes';
import { MLFeatureAttributions } from '../components/claim/MLFeatureAttributions';
import { FindingsAccordion } from '../components/claim/FindingsAccordion';
import { BillLineItemsTable } from '../components/claim/BillLineItemsTable';
import { ClaimantProviderCard } from '../components/claim/ClaimantProviderCard';
import { ProvenanceCard } from '../components/claim/ProvenanceCard';
import { IssueSanctionModal } from '../components/claim/IssueSanctionModal';

import { DocumentViewer } from '../components/DocumentViewer';
import { ChatDrawer } from '../components/ChatDrawer';
import { MapSkeleton } from '../components/common/RouteSkeleton';

// Lazy-load SpacetimeMap so Google Maps and vector libs are only fetched on demand (C4)
const SpacetimeMap = React.lazy(() =>
  import('../components/SpacetimeMap').then((m) => ({ default: m.SpacetimeMap }))
);

export const ClaimDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeFindingId, setActiveFindingId] = useState<string | null>(null);
  const [layoutMode, setLayoutMode] = useState<'split' | 'doc' | 'audit' | 'spacetime'>('split');
  const [mobileTab, setMobileTab] = useState<'audit' | 'doc' | 'spacetime'>('audit');
  const [isChatOpen, setIsChatOpen] = useState(false);

  // Assistant pulse and auto-open handling
  const [searchParams] = useSearchParams();
  const { registerClaimDetailChatOpener } = useAssistant();
  const [hasPulsed, setHasPulsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem('drishti_chat_pulsed') === 'true';
    } catch {
      return false;
    }
  });

  const handleOpenChat = useCallback(() => {
    setIsChatOpen(true);
    if (!hasPulsed) {
      setHasPulsed(true);
      try {
        localStorage.setItem('drishti_chat_pulsed', 'true');
      } catch {
        // Ignore storage write failures in incognito/quota modes
      }
    }
  }, [hasPulsed]);

  useEffect(() => {
    return registerClaimDetailChatOpener(handleOpenChat);
  }, [registerClaimDetailChatOpener, handleOpenChat]);

  useEffect(() => {
    if (searchParams.get('chat') === 'open') {
      handleOpenChat();
    }
  }, [searchParams, handleOpenChat]);

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

  const loadClaimData = React.useCallback(async () => {
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
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load claim';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadClaimData();
  }, [loadClaimData]);

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

      // Trigger authenticated PDF download
      await downloadAuthenticatedFile(res.download_url, `Sanction_${res.doc_id}.pdf`);

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
      <div className="max-w-7xl mx-auto px-4 py-24 text-center text-text-secondary space-y-4">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-amber-primary" />
        <p className="text-sm font-medium">Loading claim dossier & visual document citations...</p>
      </div>
    );
  }

  if (error || !claim) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center space-y-4">
        <ShieldAlert className="w-12 h-12 text-rose-400 mx-auto" />
        <h2 className="text-xl font-bold text-text-primary">Claim Not Found</h2>
        <p className="text-text-secondary text-sm">
          {error || `Claim ${id} could not be located.`}
        </p>
        <Link
          to="/claims"
          className="inline-flex items-center text-amber-primary hover:text-amber-bright hover:underline text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Claims Queue
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-32 space-y-6">
      {/* Top Header / Breadcrumb & View Toggle Controls */}
      <ClaimHeader
        claim={claim}
        dossier={dossier}
        analyzing={analyzing}
        layoutMode={layoutMode}
        onLayoutChange={setLayoutMode}
        onOpenChat={handleOpenChat}
        onOpenSanctionModal={() => {
          setSanctionAmount(claim.total_claimed.toString());
          setIsIssueModalOpen(true);
        }}
        onRunAnalysis={handleRunAnalysis}
      />

      {/* Mobile-Only Segmented Control (< 768px) */}
      <div className="md:hidden flex items-center bg-surface-elevated p-1 rounded-xl border border-white/10 text-xs font-semibold gap-1">
        <button
          type="button"
          onClick={() => setMobileTab('audit')}
          className={`flex-1 py-2 rounded-lg text-center transition-all ${
            mobileTab === 'audit'
              ? 'bg-amber-primary text-black font-bold shadow-2xs'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          Audit Dossier
        </button>
        <button
          type="button"
          onClick={() => setMobileTab('doc')}
          className={`flex-1 py-2 rounded-lg text-center transition-all ${
            mobileTab === 'doc'
              ? 'bg-amber-primary text-black font-bold shadow-2xs'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          Document AI
        </button>
        {dossier?.findings?.some(
          (f) =>
            f.agent === 'spacetime' ||
            f.check_id?.includes('SPACETIME') ||
            f.category === 'DOCTOR_IMPOSSIBLE_SPACETIME_TRAVEL'
        ) && (
          <button
            type="button"
            onClick={() => setMobileTab('spacetime')}
            className={`flex-1 py-2 rounded-lg text-center transition-all flex items-center justify-center gap-1 ${
              mobileTab === 'spacetime'
                ? 'bg-amber-primary text-black font-bold shadow-2xs'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            <span>Spacetime</span>
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
          </button>
        )}
      </div>

      {/* Mobile Content Area (< 768px): Shows single active tab to prevent clutter */}
      <div className="md:hidden space-y-6">
        {mobileTab === 'doc' && (
          <div className="space-y-6">
            <DocumentViewer
              claimId={claim.claim_id}
              pageCount={claim.documents[0]?.page_count || 1}
              findings={dossier?.findings || []}
              entities={claim.extracted_entities || []}
              activeFindingId={activeFindingId}
              onSelectFinding={(fId) => setActiveFindingId(fId)}
            />
            <ClaimantProviderCard claim={claim} />
          </div>
        )}

        {mobileTab === 'audit' && (
          <div className="space-y-6">
            <VerdictSummaryCard dossier={dossier} />
            <ActivePipelineNodes dossier={dossier} analyzing={analyzing} />
            <MLFeatureAttributions
              features={dossier?.top_ml_features}
              mlScore={dossier?.ml_score}
              baselineScore={dossier?.baseline_ml_score}
            />
            <FindingsAccordion
              findings={dossier?.findings || []}
              retrievedContext={dossier?.retrieved_context}
              policyId={claim.policy_id}
              activeFindingId={activeFindingId}
              onSelectFinding={setActiveFindingId}
              onSwitchToSpacetime={() => setMobileTab('spacetime')}
            />
            <ProvenanceCard
              provenance={dossier?.provenance}
              onVerifyFile={handleVerifyFile}
              verifying={verifying}
              verificationResult={verificationResult}
              verifyError={verifyError}
            />
            <BillLineItemsTable claim={claim} />
          </div>
        )}

        {mobileTab === 'spacetime' && (
          <div className="w-full">
            <React.Suspense fallback={<MapSkeleton />}>
              <SpacetimeMap
                timeline={dossier?.timeline || []}
                claimId={claim.claim_id}
                onOpenDocument={() => setMobileTab('doc')}
              />
            </React.Suspense>
          </div>
        )}
      </div>

      {/* Desktop Content Area (>= 768px): Multi-column Side-by-side or Selected Layout Mode */}
      <div
        className={`hidden md:grid gap-6 ${
          layoutMode === 'split' ? 'grid-cols-1 lg:grid-cols-12' : 'grid-cols-1'
        }`}
      >
        {/* Left Side: Document AI Viewer & Profile Details */}
        {(layoutMode === 'split' || layoutMode === 'doc') && (
          <div
            className={`${
              layoutMode === 'split' ? 'lg:col-span-6 xl:col-span-6 min-w-0' : 'w-full min-w-0'
            } space-y-6`}
          >
            <DocumentViewer
              claimId={claim.claim_id}
              pageCount={claim.documents[0]?.page_count || 1}
              findings={dossier?.findings || []}
              entities={claim.extracted_entities || []}
              activeFindingId={activeFindingId}
              onSelectFinding={(fId) => setActiveFindingId(fId)}
            />

            <ClaimantProviderCard claim={claim} />
          </div>
        )}

        {/* Right Side: Copilot Dossier, Agent Inspection, Findings, Line Items */}
        {(layoutMode === 'split' || layoutMode === 'audit') && (
          <div
            className={`${
              layoutMode === 'split' ? 'lg:col-span-6 xl:col-span-6 min-w-0' : 'w-full min-w-0'
            } space-y-6`}
          >
            <VerdictSummaryCard dossier={dossier} />

            <ActivePipelineNodes dossier={dossier} analyzing={analyzing} />

            <MLFeatureAttributions
              features={dossier?.top_ml_features}
              mlScore={dossier?.ml_score}
              baselineScore={dossier?.baseline_ml_score}
            />

            <FindingsAccordion
              findings={dossier?.findings || []}
              retrievedContext={dossier?.retrieved_context}
              policyId={claim.policy_id}
              activeFindingId={activeFindingId}
              onSelectFinding={setActiveFindingId}
              onSwitchToSpacetime={() => setLayoutMode('spacetime')}
            />

            <ProvenanceCard
              provenance={dossier?.provenance}
              onVerifyFile={handleVerifyFile}
              verifying={verifying}
              verificationResult={verificationResult}
              verifyError={verifyError}
            />

            <BillLineItemsTable claim={claim} />
          </div>
        )}

        {/* Spacetime Geographic & Trajectory Analysis */}
        {layoutMode === 'spacetime' && (
          <div className="w-full">
            <React.Suspense fallback={<MapSkeleton />}>
              <SpacetimeMap
                timeline={dossier?.timeline || []}
                claimId={claim.claim_id}
                onOpenDocument={() => setLayoutMode('doc')}
              />
            </React.Suspense>
          </div>
        )}
      </div>

      {/* Floating Case Assistant Pill (High contrast in both light and dark themes) */}
      {!isChatOpen && (
        <button
          type="button"
          onClick={handleOpenChat}
          data-testid="floating-case-assistant-pill"
          aria-label="Ask Case Assistant"
          className={`fixed z-40 flex items-center gap-2.5 px-4 py-2.5 rounded-full bg-stone-900 hover:bg-stone-800 text-white border-2 border-amber-500 shadow-2xl ring-2 ring-amber-400/20 dark:bg-amber-primary dark:hover:bg-amber-bright dark:text-black dark:border-amber-primary/40 transition-all transform hover:scale-102 cursor-pointer ${
            !hasPulsed
              ? 'ring-2 ring-amber-400 shadow-[0_0_20px_rgba(245,165,36,0.6)] animate-pulse'
              : ''
          }`}
          style={{
            bottom: 'calc(1.5rem + env(safe-area-inset-bottom, 0px))',
            right: 'calc(1.5rem + env(safe-area-inset-right, 0px))',
          }}
          title="Ask Case Assistant (/ or ⌘K)"
        >
          <MessageSquare className="w-4 h-4 text-amber-400 dark:text-black shrink-0" />
          <span className="text-xs font-bold text-white dark:text-black">Ask Case Assistant</span>
          <span className="w-2 h-2 rounded-full bg-amber-400 dark:bg-black animate-pulse" />
        </button>
      )}

      {/* Issue Sanction Note Modal */}
      <IssueSanctionModal
        isOpen={isIssueModalOpen}
        onClose={() => setIsIssueModalOpen(false)}
        claim={claim}
        sanctionAmount={sanctionAmount}
        setSanctionAmount={setSanctionAmount}
        sanctionNotes={sanctionNotes}
        setSanctionNotes={setSanctionNotes}
        onSubmit={handleIssueSanction}
        issuing={issuing}
        issueSuccess={issueSuccess}
      />

      {/* Slide-out Case Assistant Drawer */}
      <ChatDrawer
        claimId={claim.claim_id}
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        findings={dossier?.findings || []}
        activeFindingId={activeFindingId}
        onSelectFinding={(fId) => {
          setActiveFindingId(fId);
          if (layoutMode === 'audit') {
            setLayoutMode('split');
          }
        }}
      />
    </div>
  );
};
