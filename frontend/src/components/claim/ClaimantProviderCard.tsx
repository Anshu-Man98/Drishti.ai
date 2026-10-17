import React from 'react';
import { User, Building2, Calendar, FileText, ExternalLink } from 'lucide-react';
import { Claim } from '../../types';
import { formatDiagnosis, formatDoctor, formatDateTime } from '../../utils/formatters';
import { getDocumentUrl, openAuthenticatedFile } from '../../services/api';

interface ClaimantProviderCardProps {
  claim: Claim;
}

export const ClaimantProviderCard: React.FC<ClaimantProviderCardProps> = ({ claim }) => {
  const diagnosis = formatDiagnosis(claim.diagnosis_code);

  return (
    <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 sm:p-6 shadow-2xs backdrop-blur-md space-y-5 text-xs">
      {/* Claimant Profile */}
      <div className="space-y-2.5">
        <h3 className="font-bold text-xs uppercase tracking-wider text-muted flex items-center gap-1.5">
          <User className="w-3.5 h-3.5 text-amber-primary" />
          <span>Claimant Profile</span>
        </h3>
        <div className="space-y-2 bg-surface-elevated/70 p-3.5 rounded-xl border border-white/8">
          <div className="flex justify-between items-center">
            <span className="text-muted">Name:</span>
            <span className="font-semibold text-text-primary">{claim.claimant.name}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted">Phone:</span>
            <span className="font-mono text-text-primary">{claim.claimant.phone}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted">Bank Hash:</span>
            <span className="font-mono text-text-secondary text-[11px]" title={claim.claimant.bank_account_hash}>
              {claim.claimant.bank_account_hash.slice(0, 14)}...
            </span>
          </div>
        </div>
      </div>

      {/* Healthcare Provider */}
      <div className="space-y-2.5">
        <h3 className="font-bold text-xs uppercase tracking-wider text-muted flex items-center gap-1.5">
          <Building2 className="w-3.5 h-3.5 text-amber-bright" />
          <span>Healthcare Provider</span>
        </h3>
        <div className="space-y-2 bg-surface-elevated/70 p-3.5 rounded-xl border border-white/8">
          <div className="flex justify-between items-center">
            <span className="text-muted">Hospital:</span>
            <span className="font-semibold text-text-primary">{claim.provider.name}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted">City / Geo:</span>
            <span className="text-text-primary">
              {claim.provider.city} ({claim.provider.lat.toFixed(2)}, {claim.provider.lng.toFixed(2)})
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted">Attending Doctor:</span>
            <span className="font-medium text-text-primary">
              {formatDoctor(claim.doctor_id)}
            </span>
          </div>
        </div>
      </div>

      {/* Hospitalization Timeline & Diagnosis */}
      <div className="space-y-2.5">
        <h3 className="font-bold text-xs uppercase tracking-wider text-muted flex items-center gap-1.5">
          <Calendar className="w-3.5 h-3.5 text-amber-primary" />
          <span>Hospitalization & Diagnosis</span>
        </h3>
        <div className="space-y-2 bg-surface-elevated/70 p-3.5 rounded-xl border border-white/8">
          <div className="flex justify-between items-center">
            <span className="text-muted">Admission:</span>
            <span className="text-text-primary font-mono text-[11px]">
              {formatDateTime(claim.admission_ts)}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted">Discharge:</span>
            <span className="text-text-primary font-mono text-[11px]">
              {formatDateTime(claim.discharge_ts)}
            </span>
          </div>
          <div className="flex justify-between items-start pt-1 border-t border-white/6">
            <span className="text-muted">Diagnosis:</span>
            <div className="text-right">
              <span className="text-xs font-semibold text-text-primary block">
                {diagnosis.label}
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
                {diagnosis.code}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Attached Documents */}
      <div className="space-y-2.5">
        <h3 className="font-bold text-xs uppercase tracking-wider text-muted flex items-center gap-1.5">
          <FileText className="w-3.5 h-3.5 text-emerald-400" />
          <span>Attached Documents ({claim.documents.length})</span>
        </h3>

        {claim.documents.length === 0 ? (
          <p className="text-xs text-muted">No documents attached to this claim.</p>
        ) : (
          <div className="space-y-2">
            {claim.documents.map((doc) => (
              <div
                key={doc.doc_id}
                className="p-3 rounded-xl bg-surface-elevated/70 border border-white/8 flex items-center justify-between"
              >
                <div className="space-y-0.5 min-w-0 pr-2">
                  <p className="text-xs font-semibold text-text-primary truncate">
                    {doc.filename || doc.doc_id}
                  </p>
                  <p className="text-[10px] text-muted font-mono">
                    {doc.doc_type} • SHA: {doc.sha256.slice(0, 10)}...
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => openAuthenticatedFile(getDocumentUrl(claim.claim_id, doc.doc_id))}
                  className="p-2 rounded-lg bg-surface hover:bg-surface-elevated text-amber-primary border border-white/10 hover:border-amber-primary/40 transition-colors shrink-0"
                  title="Open Document Raw PDF with Bearer Token"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
