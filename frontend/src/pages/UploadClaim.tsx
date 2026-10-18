import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, AlertCircle,
  FileText, Cpu, ShieldCheck, FileCheck, X, RefreshCw
} from 'lucide-react';
import { uploadClaim } from '../services/api';
import { GlowCard } from '../components/ui/GlowCard';

const EMPTY_FORM_DATA = {
  policy_id: '',
  insurer_id: '',
  claimant_name: '',
  hospital_name: '',
  city: '',
  diagnosis_code: '',
  subtotal: '' as unknown as number,
  total_claimed: '' as unknown as number,
  line_items: [] as any[]
};

export const UploadClaim: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<any>(EMPTY_FORM_DATA);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const validate = () => {
    const errs: Record<string, string> = {};
    // If a document file is attached, metadata fields are optional (extracted by Document AI)
    // If NO document file is attached, metadata fields are strictly required
    if (!file) {
      if (!formData.policy_id?.trim()) errs.policy_id = 'Policy ID is required (e.g. POL-AROGYA-88124)';
      if (!formData.insurer_id?.trim()) errs.insurer_id = 'Insurer ID is required (e.g. INS-HDFC)';
      if (!formData.claimant_name?.trim()) errs.claimant_name = 'Claimant full name is required';
      if (!formData.hospital_name?.trim()) errs.hospital_name = 'Hospital provider name is required';
      if (!formData.city?.trim()) errs.city = 'Hospital provider city is required';
      if (!formData.diagnosis_code?.trim()) errs.diagnosis_code = 'ICD-10 diagnosis code is required';
      if (formData.subtotal === '' || isNaN(Number(formData.subtotal)) || Number(formData.subtotal) <= 0) {
        errs.subtotal = 'Subtotal must be a positive number';
      }
      if (formData.total_claimed === '' || isNaN(Number(formData.total_claimed)) || Number(formData.total_claimed) <= 0) {
        errs.total_claimed = 'Total claimed amount must be a positive number';
      }
    }
    return errs;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setSubmitting(true);

    try {
      const data = new FormData();

      // Only append fields if they are actually populated
      Object.entries(formData).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') {
          if (key === 'line_items') {
            if (Array.isArray(value) && value.length > 0) {
              data.append('line_items_json', JSON.stringify(value));
            }
          } else {
            data.append(key, String(value));
          }
        }
      });

      if (file) {
        data.append('files', file);
      }

      const res = await uploadClaim(data);
      navigate(`/claims/${res.claim_id}`);
    } catch (err: any) {
      setError(err.message || 'Claim creation failed');
    } finally {
      setSubmitting(false);
    }
  };

  const steps = [
    { num: '1', title: 'File & Metadata', desc: 'Upload PDF & claim fields', icon: FileText, current: true },
    { num: '2', title: 'Document AI', desc: 'OCR & Line-item extraction', icon: Cpu, current: false },
    { num: '3', title: '8-Agent Scrutiny', desc: 'Spacetime, Caps, Fraud audit', icon: ShieldCheck, current: false },
    { num: '4', title: 'Adjudication Dossier', desc: 'Final verdict & breakdown', icon: FileCheck, current: false },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-app-primary tracking-tight">
          Register New Health Insurance Claim
        </h1>
        <p className="text-xs sm:text-sm text-app-muted mt-1">
          Upload medical hospital bill, discharge summaries, and prescriptions for multi-agent automated fraud scrutiny.
        </p>
      </div>

      {/* Amber Progress Stepper */}
      <GlowCard className="p-4 sm:p-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 relative">
          {steps.map((st, idx) => {
            const Icon = st.icon;
            return (
              <div key={st.num} className="flex flex-col items-start gap-2 relative">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center font-mono text-xs font-bold transition-all ${
                      st.current
                        ? 'bg-amber-primary text-black ring-2 ring-amber-primary/30'
                        : 'bg-app-surface-elevated text-app-muted border border-app-default'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <span
                    className={`text-xs font-semibold ${
                      st.current ? 'text-amber-primary' : 'text-app-muted'
                    }`}
                  >
                    {st.title}
                  </span>
                </div>
                <p className="text-[11px] text-app-faint pl-9 hidden sm:block">
                  {st.desc}
                </p>
                {idx < steps.length - 1 && (
                  <div className="hidden md:block absolute right-0 top-3.5 w-6 h-[1px] bg-white/10 -mr-3" />
                )}
              </div>
            );
          })}
        </div>
      </GlowCard>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center gap-3 text-xs sm:text-sm">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-400" />
          <span>{error}</span>
        </div>
      )}

      {/* Upload & Metadata Form */}
      <form onSubmit={handleSubmit} className="space-y-6">
        <GlowCard glow corner="top-right" className="p-5 sm:p-6 space-y-6">

          {/* Dashed Amber-Tinted File Dropzone */}
          <div className="space-y-2">
            <span className="block text-xs font-semibold uppercase tracking-wider text-app-muted">
              Hospital Invoice PDF / Bill Document
            </span>
            <div className="border-2 border-dashed border-amber-primary/30 hover:border-amber-primary/60 rounded-[20px] p-6 sm:p-8 text-center transition-colors bg-app-surface">
              <Upload className="w-8 h-8 text-amber-primary/70 mx-auto mb-2" />
              <p className="text-xs sm:text-sm text-app-primary font-medium">
                {file ? file.name : 'Select or drag hospital invoice PDF here'}
              </p>
              <p className="text-[11px] text-app-faint mt-1">Accepts PDF, PNG, JPG (up to 25MB)</p>
              {file && (
                <div className="mt-2 inline-flex items-center gap-2 px-3 py-1 rounded-lg bg-white/[0.04] border border-app-default text-xs font-mono text-app-primary">
                  <span>{file.name} ({(file.size / 1024).toFixed(1)} KB)</span>
                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="text-app-muted hover:text-rose-400 cursor-pointer"
                    aria-label="Remove attached file"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
              <div className="mt-3">
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={handleFileChange}
                  className="hidden"
                  id="file-upload"
                />
                <label
                  htmlFor="file-upload"
                  className="inline-block px-4 py-1.5 rounded-xl bg-app-surface-elevated hover:bg-white/[0.08] text-app-primary text-xs font-medium cursor-pointer transition-colors border border-amber-primary/30"
                >
                  {file ? 'Replace File' : 'Browse Files'}
                </label>
              </div>
            </div>
          </div>

          {/* Claim Core Metadata */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label htmlFor="form-policy-id" className="block text-app-muted mb-1.5 font-medium">
                Policy ID {!file && <span className="text-amber-primary">*</span>}
              </label>
              <input
                id="form-policy-id"
                type="text"
                value={formData.policy_id || ''}
                onChange={(e) => {
                  setFormData({ ...formData, policy_id: e.target.value });
                  if (errors.policy_id) setErrors({ ...errors, policy_id: '' });
                }}
                placeholder="e.g. POL-AROGYA-88124"
                aria-invalid={!!errors.policy_id}
                aria-describedby={errors.policy_id ? 'err-policy-id' : undefined}
                className={`w-full bg-app-surface-elevated border rounded-xl px-3.5 py-2.5 text-app-primary font-mono focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary transition-colors ${
                  errors.policy_id ? 'border-rose-500/80 bg-rose-500/[0.03]' : 'border-app-default hover:border-white/20'
                }`}
              />
              {errors.policy_id && (
                <p id="err-policy-id" className="text-[11px] text-rose-400 mt-1 flex items-center gap-1 font-mono">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.policy_id}</span>
                </p>
              )}
            </div>

            <div>
              <label htmlFor="form-insurer-id" className="block text-app-muted mb-1.5 font-medium">
                Insurer ID {!file && <span className="text-amber-primary">*</span>}
              </label>
              <input
                id="form-insurer-id"
                type="text"
                value={formData.insurer_id || ''}
                onChange={(e) => {
                  setFormData({ ...formData, insurer_id: e.target.value });
                  if (errors.insurer_id) setErrors({ ...errors, insurer_id: '' });
                }}
                placeholder="e.g. INS-HDFC"
                aria-invalid={!!errors.insurer_id}
                aria-describedby={errors.insurer_id ? 'err-insurer-id' : undefined}
                className={`w-full bg-app-surface-elevated border rounded-xl px-3.5 py-2.5 text-app-primary font-mono focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary transition-colors ${
                  errors.insurer_id ? 'border-rose-500/80 bg-rose-500/[0.03]' : 'border-app-default hover:border-white/20'
                }`}
              />
              {errors.insurer_id && (
                <p id="err-insurer-id" className="text-[11px] text-rose-400 mt-1 flex items-center gap-1 font-mono">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.insurer_id}</span>
                </p>
              )}
            </div>

            <div>
              <label htmlFor="form-claimant-name" className="block text-app-muted mb-1.5 font-medium">
                Claimant Full Name {!file && <span className="text-amber-primary">*</span>}
              </label>
              <input
                id="form-claimant-name"
                type="text"
                value={formData.claimant_name || ''}
                onChange={(e) => {
                  setFormData({ ...formData, claimant_name: e.target.value });
                  if (errors.claimant_name) setErrors({ ...errors, claimant_name: '' });
                }}
                placeholder="e.g. Rohan Verma"
                aria-invalid={!!errors.claimant_name}
                aria-describedby={errors.claimant_name ? 'err-claimant-name' : undefined}
                className={`w-full bg-app-surface-elevated border rounded-xl px-3.5 py-2.5 text-app-primary focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary transition-colors ${
                  errors.claimant_name ? 'border-rose-500/80 bg-rose-500/[0.03]' : 'border-app-default hover:border-white/20'
                }`}
              />
              {errors.claimant_name && (
                <p id="err-claimant-name" className="text-[11px] text-rose-400 mt-1 flex items-center gap-1 font-mono">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.claimant_name}</span>
                </p>
              )}
            </div>

            <div>
              <label htmlFor="form-hospital-name" className="block text-app-muted mb-1.5 font-medium">
                Hospital Provider Name {!file && <span className="text-amber-primary">*</span>}
              </label>
              <input
                id="form-hospital-name"
                type="text"
                value={formData.hospital_name || ''}
                onChange={(e) => {
                  setFormData({ ...formData, hospital_name: e.target.value });
                  if (errors.hospital_name) setErrors({ ...errors, hospital_name: '' });
                }}
                placeholder="e.g. Max Super Speciality Hospital"
                aria-invalid={!!errors.hospital_name}
                aria-describedby={errors.hospital_name ? 'err-hospital-name' : undefined}
                className={`w-full bg-app-surface-elevated border rounded-xl px-3.5 py-2.5 text-app-primary focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary transition-colors ${
                  errors.hospital_name ? 'border-rose-500/80 bg-rose-500/[0.03]' : 'border-app-default hover:border-white/20'
                }`}
              />
              {errors.hospital_name && (
                <p id="err-hospital-name" className="text-[11px] text-rose-400 mt-1 flex items-center gap-1 font-mono">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.hospital_name}</span>
                </p>
              )}
            </div>

            <div>
              <label htmlFor="form-provider-city" className="block text-app-muted mb-1.5 font-medium">
                Provider City {!file && <span className="text-amber-primary">*</span>}
              </label>
              <input
                id="form-provider-city"
                type="text"
                value={formData.city || ''}
                onChange={(e) => {
                  setFormData({ ...formData, city: e.target.value });
                  if (errors.city) setErrors({ ...errors, city: '' });
                }}
                placeholder="e.g. New Delhi"
                aria-invalid={!!errors.city}
                aria-describedby={errors.city ? 'err-provider-city' : undefined}
                className={`w-full bg-app-surface-elevated border rounded-xl px-3.5 py-2.5 text-app-primary focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary transition-colors ${
                  errors.city ? 'border-rose-500/80 bg-rose-500/[0.03]' : 'border-app-default hover:border-white/20'
                }`}
              />
              {errors.city && (
                <p id="err-provider-city" className="text-[11px] text-rose-400 mt-1 flex items-center gap-1 font-mono">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.city}</span>
                </p>
              )}
            </div>

            <div>
              <label htmlFor="form-diagnosis-code" className="block text-app-muted mb-1.5 font-medium">
                Diagnosis Code (ICD-10) {!file && <span className="text-amber-primary">*</span>}
              </label>
              <input
                id="form-diagnosis-code"
                type="text"
                value={formData.diagnosis_code || ''}
                onChange={(e) => {
                  setFormData({ ...formData, diagnosis_code: e.target.value });
                  if (errors.diagnosis_code) setErrors({ ...errors, diagnosis_code: '' });
                }}
                placeholder="e.g. K35.8"
                aria-invalid={!!errors.diagnosis_code}
                aria-describedby={errors.diagnosis_code ? 'err-diagnosis-code' : undefined}
                className={`w-full bg-app-surface-elevated border rounded-xl px-3.5 py-2.5 text-app-primary font-mono focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary transition-colors ${
                  errors.diagnosis_code ? 'border-rose-500/80 bg-rose-500/[0.03]' : 'border-app-default hover:border-white/20'
                }`}
              />
              {errors.diagnosis_code && (
                <p id="err-diagnosis-code" className="text-[11px] text-rose-400 mt-1 flex items-center gap-1 font-mono">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.diagnosis_code}</span>
                </p>
              )}
            </div>

            <div>
              <label htmlFor="form-subtotal" className="block text-app-muted mb-1.5 font-medium">
                Subtotal (₹) {!file && <span className="text-amber-primary">*</span>}
              </label>
              <input
                id="form-subtotal"
                type="number"
                step="any"
                value={formData.subtotal !== undefined ? formData.subtotal : ''}
                onChange={(e) => {
                  const val = e.target.value === '' ? '' : parseFloat(e.target.value);
                  setFormData({ ...formData, subtotal: val });
                  if (errors.subtotal) setErrors({ ...errors, subtotal: '' });
                }}
                placeholder="0.00"
                aria-invalid={!!errors.subtotal}
                aria-describedby={errors.subtotal ? 'err-subtotal' : undefined}
                className={`w-full bg-app-surface-elevated border rounded-xl px-3.5 py-2.5 text-app-primary font-mono focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary transition-colors ${
                  errors.subtotal ? 'border-rose-500/80 bg-rose-500/[0.03]' : 'border-app-default hover:border-white/20'
                }`}
              />
              {errors.subtotal && (
                <p id="err-subtotal" className="text-[11px] text-rose-400 mt-1 flex items-center gap-1 font-mono">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.subtotal}</span>
                </p>
              )}
            </div>

            <div>
              <label htmlFor="form-total-claimed" className="block text-app-muted mb-1.5 font-medium">
                Total Claimed (₹) {!file && <span className="text-amber-primary">*</span>}
              </label>
              <input
                id="form-total-claimed"
                type="number"
                step="any"
                value={formData.total_claimed !== undefined ? formData.total_claimed : ''}
                onChange={(e) => {
                  const val = e.target.value === '' ? '' : parseFloat(e.target.value);
                  setFormData({ ...formData, total_claimed: val });
                  if (errors.total_claimed) setErrors({ ...errors, total_claimed: '' });
                }}
                placeholder="0.00"
                aria-invalid={!!errors.total_claimed}
                aria-describedby={errors.total_claimed ? 'err-total-claimed' : undefined}
                className={`w-full bg-app-surface-elevated border rounded-xl px-3.5 py-2.5 text-app-primary font-mono font-bold focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary transition-colors ${
                  errors.total_claimed ? 'border-rose-500/80 bg-rose-500/[0.03]' : 'border-app-default hover:border-white/20'
                }`}
              />
              {errors.total_claimed && (
                <p id="err-total-claimed" className="text-[11px] text-rose-400 mt-1 flex items-center gap-1 font-mono">
                  <AlertCircle className="w-3 h-3 shrink-0" />
                  <span>{errors.total_claimed}</span>
                </p>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3.5 rounded-xl bg-amber-primary hover:bg-amber-bright text-black font-semibold text-xs sm:text-sm transition-all shadow-md shadow-amber-primary/20 disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer"
          >
            {submitting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-black" />
                <span>Uploading Document & Registering Claim with Multi-Agent Pipeline...</span>
              </>
            ) : (
              <span>Submit Claim for Multi-Agent Scrutiny</span>
            )}
          </button>
        </GlowCard>
      </form>
    </div>
  );
};
