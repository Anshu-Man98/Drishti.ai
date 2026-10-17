import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, CheckCircle2, AlertCircle, Sparkles, FileText, Cpu, ShieldCheck, FileCheck } from 'lucide-react';
import { uploadClaim } from '../services/api';
import { GlowCard } from '../components/ui/GlowCard';

const GOLDEN_PRESETS = [
  {
    key: 'G1',
    name: 'G1: Clean Claim (Max Hospital)',
    desc: 'Laparoscopic appendectomy, standard room rent, exact mathematics.',
    data: {
      policy_id: 'POL-AROGYA-88124',
      insurer_id: 'INS-HDFC',
      claimant_id: 'CLMNT-8921',
      claimant_name: 'Rohan Verma',
      claimant_phone: '+91-9876543210',
      bank_account_hash: 'a1b2c3d4e5f60718',
      hospital_id: 'HOSP-101',
      hospital_name: 'Max Super Speciality Hospital',
      city: 'New Delhi',
      lat: 28.5284,
      lng: 77.2185,
      doctor_id: 'DOC-2045',
      admission_ts: '2026-03-12T09:30:00',
      discharge_ts: '2026-03-15T11:00:00',
      diagnosis_code: 'K35.8',
      subtotal: 71000.0,
      tax: 3550.0,
      total_claimed: 74550.0,
      line_items: [
        { description: 'Semi-Private Room Rent (3 days)', qty: 3, unit_price: 4000.0, amount: 12000.0 },
        { description: 'Laparoscopic Appendectomy Surgery & OT', qty: 1, unit_price: 45000.0, amount: 45000.0 },
        { description: 'Consultant Surgeon & Anesthetist Visit Fees', qty: 3, unit_price: 2000.0, amount: 6000.0 },
        { description: 'Post-Op Pharmacy & Antibiotic Consumables', qty: 1, unit_price: 8000.0, amount: 8000.0 }
      ]
    }
  },
  {
    key: 'G2',
    name: 'G2: Arithmetic Mismatch (Lifeline Hospital)',
    desc: 'Line items sum to ₹95,025, but invoice printed total is ₹1,12,500.',
    data: {
      policy_id: 'POL-CARE-55192',
      insurer_id: 'INS-STAR',
      claimant_id: 'CLMNT-3310',
      claimant_name: 'Sunita Sharma',
      claimant_phone: '+91-9820123456',
      bank_account_hash: 'f9e8d7c6b5a41234',
      hospital_id: 'HOSP-102',
      hospital_name: 'Lifeline Super Speciality Hospital',
      city: 'Mumbai',
      lat: 19.0596,
      lng: 72.8295,
      doctor_id: 'DOC-2089',
      admission_ts: '2026-04-14T10:00:00',
      discharge_ts: '2026-04-18T15:00:00',
      diagnosis_code: 'I20.9',
      subtotal: 107142.86,
      tax: 5357.14,
      total_claimed: 112500.0,
      line_items: [
        { description: 'Hospital Room Rent (4 days)', qty: 4, unit_price: 4500.0, amount: 18000.0 },
        { description: 'ICU Nursing & Critical Care Monitoring', qty: 1, unit_price: 25000.0, amount: 25000.0 },
        { description: 'Cardiology Workup, ECG & 2D-Echo', qty: 1, unit_price: 32000.0, amount: 32000.0 },
        { description: 'In-Patient Pharmacy & Cardiac Infusions', qty: 1, unit_price: 15500.0, amount: 15500.0 }
      ]
    }
  },
  {
    key: 'G3',
    name: 'G3: Policy Cap Breach (Metro Institute)',
    desc: 'Room rent billed at ₹14,500/day vs Arogya Sanjeevani ₹5,000/day cap.',
    data: {
      policy_id: 'POL-AROGYA-33219',
      insurer_id: 'INS-ICICI',
      claimant_id: 'CLMNT-6520',
      claimant_name: 'Vikram Patel',
      claimant_phone: '+91-9845098765',
      bank_account_hash: '1122334455667788',
      hospital_id: 'HOSP-103',
      hospital_name: 'Metro Healthcare Institute',
      city: 'Bengaluru',
      lat: 12.9784,
      lng: 77.6408,
      doctor_id: 'DOC-2031',
      admission_ts: '2026-05-18T08:00:00',
      discharge_ts: '2026-05-22T12:00:00',
      diagnosis_code: 'K80.2',
      subtotal: 126500.0,
      tax: 6325.0,
      total_claimed: 132825.0,
      line_items: [
        { description: 'Super Deluxe Executive Suite Room (4 days)', qty: 4, unit_price: 14500.0, amount: 58000.0 },
        { description: 'Cholecystectomy Laparoscopic Procedure', qty: 1, unit_price: 42000.0, amount: 42000.0 },
        { description: 'Surgeon & Anesthesia Professional Charges', qty: 1, unit_price: 15000.0, amount: 15000.0 },
        { description: 'OT Consumables & Surgical Disposables', qty: 1, unit_price: 11500.0, amount: 11500.0 }
      ]
    }
  },
  {
    key: 'G6',
    name: 'G6: Forged Total & Font Metadata',
    desc: 'Total row altered in mismatched font, image editor artifacts flagged.',
    data: {
      policy_id: 'POL-AROGYA-77112',
      insurer_id: 'INS-HDFC',
      claimant_id: 'CLMNT-1200',
      claimant_name: 'Amit Kulkarni',
      claimant_phone: '+91-9890123456',
      bank_account_hash: '556677889900aabb',
      hospital_id: 'HOSP-106',
      hospital_name: 'CarePlus Medical Center',
      city: 'Pune',
      lat: 18.5283,
      lng: 73.8402,
      doctor_id: 'DOC-2051',
      admission_ts: '2026-08-02T10:00:00',
      discharge_ts: '2026-08-05T13:00:00',
      diagnosis_code: 'A09',
      subtotal: 85238.10,
      tax: 4261.90,
      total_claimed: 89500.0,
      line_items: [
        { description: 'General Ward Bed Charges (3 days)', qty: 3, unit_price: 2500.0, amount: 7500.0 },
        { description: 'Conservative Medical Management for Colitis', qty: 1, unit_price: 12000.0, amount: 12000.0 },
        { description: 'Consultant Physician Daily Visits', qty: 3, unit_price: 1500.0, amount: 4500.0 },
        { description: 'IV Fluids & Injectable Antibiotics', qty: 1, unit_price: 6000.0, amount: 6000.0 }
      ]
    }
  }
];

export const UploadClaim: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<any>(GOLDEN_PRESETS[0].data);
  const [selectedPreset, setSelectedPreset] = useState<string>(GOLDEN_PRESETS[0].key);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleApplyPreset = (presetKey: string) => {
    setSelectedPreset(presetKey);
    const p = GOLDEN_PRESETS.find((x) => x.key === presetKey);
    if (p) {
      setFormData(p.data);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const data = new FormData();
      Object.entries(formData).forEach(([key, value]) => {
        if (key === 'line_items') {
          data.append('line_items_json', JSON.stringify(value));
        } else {
          data.append(key, String(value));
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
        <h1 className="text-2xl font-bold text-text-primary tracking-tight">
          Register New Health Insurance Claim
        </h1>
        <p className="text-xs sm:text-sm text-text-muted mt-1">
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
                        : 'bg-surface-elevated text-text-muted border border-white/8'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <span
                    className={`text-xs font-semibold ${
                      st.current ? 'text-amber-primary' : 'text-text-muted'
                    }`}
                  >
                    {st.title}
                  </span>
                </div>
                <p className="text-[11px] text-text-faint pl-9 hidden sm:block">
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

      {/* Quick Load Golden Presets */}
      <GlowCard className="p-4 sm:p-5 space-y-3">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-amber-primary">
          <Sparkles className="w-3.5 h-3.5 text-amber-primary" />
          <span>Quick Benchmark Presets (Golden Benchmark Claims)</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {GOLDEN_PRESETS.map((p) => {
            const isSelected = selectedPreset === p.key;
            return (
              <button
                key={p.key}
                type="button"
                onClick={() => handleApplyPreset(p.key)}
                className={`p-3.5 rounded-xl border text-left transition-all ${
                  isSelected
                    ? 'bg-amber-primary/10 border-amber-primary text-text-primary shadow-xs'
                    : 'bg-surface-elevated/60 border-white/8 text-text-muted hover:border-amber-primary/30 hover:text-text-primary'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-text-primary">{p.name}</span>
                  {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-amber-primary shrink-0" />}
                </div>
                <p className="text-[11px] text-text-muted mt-1 leading-snug">{p.desc}</p>
              </button>
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
            <span className="block text-xs font-semibold uppercase tracking-wider text-text-muted">
              Hospital Invoice PDF / Bill Document
            </span>
            <div className="border-2 border-dashed border-amber-primary/30 hover:border-amber-primary/60 rounded-[20px] p-6 sm:p-8 text-center transition-colors bg-surface">
              <Upload className="w-8 h-8 text-amber-primary/70 mx-auto mb-2" />
              <p className="text-xs sm:text-sm text-text-primary font-medium">
                {file ? file.name : 'Select or drag hospital invoice PDF here'}
              </p>
              <p className="text-[11px] text-text-faint mt-1">Accepts PDF, PNG, JPG (up to 15MB)</p>
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg"
                onChange={(e) => e.target.files && setFile(e.target.files[0])}
                className="hidden"
                id="file-upload"
              />
              <label
                htmlFor="file-upload"
                className="mt-3 inline-block px-4 py-1.5 rounded-xl bg-surface-elevated hover:bg-surface-elevated/80 text-text-primary text-xs font-medium cursor-pointer transition-colors border border-amber-primary/30"
              >
                Browse Files
              </label>
            </div>
          </div>

          {/* Claim Core Metadata */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label htmlFor="form-policy-id" className="block text-text-muted mb-1 font-medium">Policy ID</label>
              <input
                id="form-policy-id"
                type="text"
                value={formData.policy_id}
                onChange={(e) => setFormData({ ...formData, policy_id: e.target.value })}
                className="w-full bg-surface-elevated border border-white/8 rounded-xl px-3.5 py-2.5 text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary"
                required
              />
            </div>
            <div>
              <label htmlFor="form-insurer-id" className="block text-text-muted mb-1 font-medium">Insurer ID</label>
              <input
                id="form-insurer-id"
                type="text"
                value={formData.insurer_id}
                onChange={(e) => setFormData({ ...formData, insurer_id: e.target.value })}
                className="w-full bg-surface-elevated border border-white/8 rounded-xl px-3.5 py-2.5 text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary"
                required
              />
            </div>
            <div>
              <label htmlFor="form-claimant-name" className="block text-text-muted mb-1 font-medium">Claimant Full Name</label>
              <input
                id="form-claimant-name"
                type="text"
                value={formData.claimant_name}
                onChange={(e) => setFormData({ ...formData, claimant_name: e.target.value })}
                className="w-full bg-surface-elevated border border-white/8 rounded-xl px-3.5 py-2.5 text-text-primary focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary"
                required
              />
            </div>
            <div>
              <label htmlFor="form-hospital-name" className="block text-text-muted mb-1 font-medium">Hospital Provider Name</label>
              <input
                id="form-hospital-name"
                type="text"
                value={formData.hospital_name}
                onChange={(e) => setFormData({ ...formData, hospital_name: e.target.value })}
                className="w-full bg-surface-elevated border border-white/8 rounded-xl px-3.5 py-2.5 text-text-primary focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary"
                required
              />
            </div>
            <div>
              <label htmlFor="form-provider-city" className="block text-text-muted mb-1 font-medium">Provider City</label>
              <input
                id="form-provider-city"
                type="text"
                value={formData.city}
                onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                className="w-full bg-surface-elevated border border-white/8 rounded-xl px-3.5 py-2.5 text-text-primary focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary"
                required
              />
            </div>
            <div>
              <label htmlFor="form-diagnosis-code" className="block text-text-muted mb-1 font-medium">Diagnosis Code (ICD-10)</label>
              <input
                id="form-diagnosis-code"
                type="text"
                value={formData.diagnosis_code}
                onChange={(e) => setFormData({ ...formData, diagnosis_code: e.target.value })}
                className="w-full bg-surface-elevated border border-white/8 rounded-xl px-3.5 py-2.5 text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary"
                required
              />
            </div>
            <div>
              <label htmlFor="form-subtotal" className="block text-text-muted mb-1 font-medium">Subtotal (₹)</label>
              <input
                id="form-subtotal"
                type="number"
                step="any"
                value={formData.subtotal}
                onChange={(e) => setFormData({ ...formData, subtotal: parseFloat(e.target.value) })}
                className="w-full bg-surface-elevated border border-white/8 rounded-xl px-3.5 py-2.5 text-text-primary font-mono focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary"
                required
              />
            </div>
            <div>
              <label htmlFor="form-total-claimed" className="block text-text-muted mb-1 font-medium">Total Claimed (₹)</label>
              <input
                id="form-total-claimed"
                type="number"
                step="any"
                value={formData.total_claimed}
                onChange={(e) => setFormData({ ...formData, total_claimed: parseFloat(e.target.value) })}
                className="w-full bg-surface-elevated border border-white/8 rounded-xl px-3.5 py-2.5 text-text-primary font-mono font-bold focus:outline-none focus:ring-1 focus:ring-amber-primary focus:border-amber-primary"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 rounded-xl bg-amber-primary hover:bg-amber-bright text-black font-semibold text-xs sm:text-sm transition-all shadow-md shadow-amber-primary/20 disabled:opacity-50"
          >
            {submitting ? 'Uploading & Registering Claim...' : 'Submit Claim for Multi-Agent Scrutiny'}
          </button>
        </GlowCard>
      </form>
    </div>
  );
};
