import React from 'react';
import {
  Scan,
  Shield,
  Layers,
  MapPin,
  TrendingUp,
  Cpu,
  Fingerprint,
  Database,
  Sparkles,
} from 'lucide-react';

export { Badge, type BadgeVariant, type BadgeProps } from '../ui/Badge';

/**
 * Agent Identifier Badge
 */
export const AgentBadge: React.FC<{ agent: string; className?: string }> = ({ agent, className = '' }) => {
  const getAgentMeta = (name: string) => {
    switch (name.toLowerCase()) {
      case 'forensics':
        return { label: 'Forensics', icon: Scan, color: 'text-amber-primary bg-amber-primary/10 border-amber-primary/30' };
      case 'policy':
        return { label: 'Policy Engine', icon: Shield, color: 'text-amber-primary bg-amber-primary/10 border-amber-primary/30' };
      case 'crossref':
        return { label: 'Cross-Insurer', icon: Layers, color: 'text-amber-primary bg-amber-primary/10 border-amber-primary/30' };
      case 'spacetime':
        return { label: 'Spacetime', icon: MapPin, color: 'text-amber-primary bg-amber-primary/10 border-amber-primary/30' };
      case 'ml':
        return { label: 'BQ ML', icon: TrendingUp, color: 'text-amber-bright bg-amber-primary/10 border-amber-primary/30' };
      case 'injection':
        return { label: 'Prompt Shield', icon: Cpu, color: 'text-rose-400 bg-rose-500/10 border-rose-500/20' };
      case 'provenance':
        return { label: 'Provenance', icon: Fingerprint, color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' };
      case 'rag':
        return { label: 'Pattern retrieval', icon: Database, color: 'text-amber-primary bg-amber-primary/10 border-amber-primary/30' };
      default:
        return { label: name, icon: Sparkles, color: 'text-muted bg-white/5 border-white/10' };
    }
  };

  const meta = getAgentMeta(agent);
  const Icon = meta.icon;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium border ${meta.color} ${className}`}>
      <Icon className="w-3 h-3 shrink-0" />
      <span>{meta.label}</span>
    </span>
  );
};
