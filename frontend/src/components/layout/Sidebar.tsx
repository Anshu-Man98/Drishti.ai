import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  Shield,
  LayoutDashboard,
  FileText,
  Network,
  UploadCloud,
  Swords,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
  X,
  ExternalLink,
  Bot,
} from 'lucide-react';
import { LiveDot } from '../ui/LiveDot';
import { ScoringModal } from '../common/ScoringModal';
import { useAssistant } from '../../context/AssistantContext';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

/**
 * Sidebar - Floating rounded black glass sidebar following the Nexa aesthetic.
 * Features:
 * - Floating rounded card with gap from viewport edge
 * - Golden amber brand icon and typography
 * - Tactile active nav pill with amber glowing icon
 * - System status card at the bottom with "How scoring works" modal link
 * - Fully accessible and responsive mobile drawer
 */
export const Sidebar: React.FC<SidebarProps> = ({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
}) => {
  const location = useLocation();
  const { openAssistant } = useAssistant();
  const [isScoringModalOpen, setIsScoringModalOpen] = useState(false);

  const navItems = [
    { label: 'Dashboard', path: '/', icon: LayoutDashboard },
    { label: 'Claims Queue', path: '/claims', icon: FileText },
    { label: 'Fraud Network', path: '/network', icon: Network },
    { label: 'Upload Claim', path: '/upload', icon: UploadCloud },
    { label: 'Duel Arena', path: '/duel', icon: Swords },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <button
          type="button"
          aria-label="Close navigation sidebar"
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 lg:hidden border-none p-0 cursor-default"
          onClick={onCloseMobile}
        />
      )}

      {/* Floating Sidebar Aside */}
      <aside
        className={`fixed top-4 bottom-4 left-4 z-50 flex flex-col rounded-[20px] bg-app-surface/95 backdrop-blur-md border border-white/[0.08] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.07),0_8px_32px_rgba(0,0,0,0.5)] transition-all duration-300 ease-in-out
          ${collapsed ? 'w-20' : 'w-64'}
          ${mobileOpen ? 'translate-x-0' : '-translate-x-[calc(100%+1.5rem)] lg:translate-x-0'}
        `}
      >
        {/* Brand Header */}
        <div
          className={`border-b border-white/[0.06] shrink-0 transition-all duration-300 ease-in-out ${
            collapsed
              ? 'h-20 py-2.5 px-2 flex flex-col items-center justify-center gap-1.5'
              : 'h-16 px-4 flex items-center justify-between'
          }`}
        >
          <NavLink
            to="/"
            onClick={onCloseMobile}
            className={`flex items-center select-none group transition-all ${
              collapsed ? 'justify-center p-0' : 'gap-3 overflow-hidden'
            }`}
          >
            {/* Amber Shield Logo Mark */}
            <div className="w-9 h-9 rounded-xl bg-amber-primary/14 border border-amber-primary/35 flex items-center justify-center text-amber-primary shadow-[0_0_14px_-2px_rgba(245,165,36,0.35)] shrink-0 transition-transform group-hover:scale-105">
              <Shield className="w-5 h-5 fill-amber-primary/20" />
            </div>

            {!collapsed && (
              <div className="flex flex-col min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-semibold text-base tracking-tight text-app-primary">
                    Drishti
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
                    AI
                  </span>
                </div>
                <span className="text-[11px] text-app-muted truncate font-mono">
                  Claims Intelligence
                </span>
              </div>
            )}
          </NavLink>

          {/* Mobile Close Button */}
          <button
            onClick={onCloseMobile}
            className="lg:hidden p-1.5 rounded-lg text-app-muted hover:text-app-primary hover:bg-white/[0.06] transition-colors"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>

          {/* Desktop Collapse Toggle */}
          <button
            onClick={onToggleCollapse}
            className={`hidden lg:flex items-center justify-center rounded-lg text-app-muted hover:text-app-primary hover:bg-white/[0.06] focus:outline-none focus:ring-2 focus:ring-amber-primary/50 transition-all cursor-pointer ${
              collapsed
                ? 'w-9 h-5.5 bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.08] shadow-2xs'
                : 'w-7 h-7'
            }`}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? (
              <ChevronRight className="w-3.5 h-3.5 text-amber-primary" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Navigation Items */}
        <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1.5">
          <div className={`px-2 pb-1.5 text-[10px] font-mono uppercase tracking-wider text-app-muted/70 ${collapsed ? 'text-center' : ''}`}>
            {collapsed ? '—' : 'Operations'}
          </div>

          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path);

            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={onCloseMobile}
                title={collapsed ? item.label : undefined}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs sm:text-sm font-medium transition-all select-none ${
                  isActive
                    ? 'bg-white/[0.08] text-app-primary border border-white/[0.12] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06),0_2px_8px_rgba(0,0,0,0.3)]'
                    : 'text-app-muted hover:text-app-primary hover:bg-white/[0.03] border border-transparent'
                }`}
              >
                <Icon
                  className={`w-4 h-4 shrink-0 transition-colors ${
                    isActive ? 'text-amber-primary text-glow-amber' : 'text-app-muted'
                  }`}
                />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </NavLink>
            );
          })}

          {/* AI Case Assistant Button */}
          <div className="pt-2 mt-2 border-t border-app-border">
            <button
              type="button"
              onClick={() => {
                onCloseMobile();
                openAssistant();
              }}
              title={collapsed ? 'Case Assistant (⌘K or /)' : undefined}
              aria-label="Open Case Assistant"
              className={`w-full flex items-center py-2.5 rounded-xl text-xs sm:text-sm font-medium transition-all select-none text-app-primary hover:bg-stone-200/60 dark:hover:bg-white/[0.04] border border-amber-700/30 dark:border-amber-primary/20 bg-amber-500/10 dark:bg-amber-primary/5 group cursor-pointer ${
                collapsed ? 'justify-center px-0' : 'gap-3 px-3'
              }`}
            >
              <Bot className="w-4 h-4 shrink-0 text-amber-800 dark:text-amber-primary group-hover:scale-105 transition-transform" />
              {!collapsed && (
                <div className="flex-1 flex items-center justify-between min-w-0">
                  <span className="truncate font-semibold text-app-primary group-hover:text-amber-800 dark:group-hover:text-amber-primary transition-colors">
                    Case Assistant
                  </span>
                  <kbd className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-700/10 dark:bg-white/10 text-amber-900 dark:text-app-muted border border-amber-700/20 dark:border-white/10">
                    ⌘K
                  </kbd>
                </div>
              )}
            </button>
          </div>
        </div>

        {/* Sidebar Footer: System Status Card (Nexa bottom card position, NOT an upsell) */}
        {!collapsed ? (
          <div className="p-3 border-t border-white/[0.06] shrink-0">
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.07] space-y-2.5 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <LiveDot color="emerald" size="sm" pulse={true} />
                  <span className="text-[11px] font-semibold text-app-primary tracking-tight">System Online</span>
                </div>
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.06] text-app-muted">
                  GCP
                </span>
              </div>

              <div className="text-[11px] text-app-muted leading-tight font-mono">
                drishti-demo / BigQuery & Vertex AI
              </div>

              <button
                type="button"
                onClick={() => setIsScoringModalOpen(true)}
                className="w-full mt-1 px-2.5 py-1.5 rounded-lg bg-amber-primary/10 border border-amber-primary/30 text-amber-primary hover:bg-amber-primary/18 hover:border-amber-primary/45 transition-colors text-[11px] font-medium flex items-center justify-between cursor-pointer"
              >
                <div className="flex items-center gap-1.5">
                  <HelpCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>How scoring works</span>
                </div>
                <ExternalLink className="w-3 h-3 opacity-70" />
              </button>
            </div>
          </div>
        ) : (
          <div className="p-3 border-t border-white/[0.06] flex flex-col items-center gap-2 shrink-0">
            <LiveDot color="emerald" size="sm" pulse={true} />
            <button
              type="button"
              onClick={() => setIsScoringModalOpen(true)}
              className="p-1.5 rounded-lg text-amber-primary hover:bg-white/[0.06]"
              title="How scoring works"
              aria-label="How scoring works"
            >
              <HelpCircle className="w-4 h-4" />
            </button>
          </div>
        )}
      </aside>

      {/* Scoring Explanation Modal */}
      <ScoringModal
        isOpen={isScoringModalOpen}
        onClose={() => setIsScoringModalOpen(false)}
      />
    </>
  );
};
