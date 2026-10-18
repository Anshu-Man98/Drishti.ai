import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useAssistant } from '../../context/AssistantContext';
import { ClaimChatPickerModal } from '../common/ClaimChatPickerModal';

interface AppShellProps {
  children: React.ReactNode;
}

/**
 * AppShell - Nexa-inspired layout container.
 * Features:
 * - Near-black background with soft warm golden-amber light beam cascading from top-center
 * - Floating rounded black glass sidebar with gap
 * - Floating rounded top bar with search, notification alert dot, sun/moon pill, and user chip
 * - Responsive mobile drawer navigation
 */
export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('finshield-sidebar-collapsed') === 'true';
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const { isClaimPickerOpen, closeClaimPicker } = useAssistant();
  const navigate = useNavigate();
  const location = useLocation();

  const currentClaimId = (() => {
    const m = location.pathname.match(/^\/claims\/([^/]+)$/);
    return m ? m[1] : null;
  })();

  const handleToggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('finshield-sidebar-collapsed', String(next));
      return next;
    });
  };

  return (
    <div className="min-h-screen bg-app-base text-app-primary flex flex-col font-sans transition-colors duration-200 relative overflow-x-hidden">
      {/* Nexa Soft Warm Golden-Amber Light Beam cascading from top-center */}
      <div className="light-beam-bg" aria-hidden="true" />
      <div className="beam-grain" aria-hidden="true" />

      {/* Floating Collapsible / Responsive Sidebar */}
      <Sidebar
        collapsed={collapsed}
        onToggleCollapse={handleToggleCollapse}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />

      {/* Main Content Area */}
      <div
        className={`flex-1 flex flex-col transition-all duration-300 ease-in-out px-4 sm:px-6 lg:px-8 py-4 relative z-10 ${
          collapsed ? 'lg:pl-28' : 'lg:pl-72'
        }`}
      >
        <TopBar onOpenMobile={() => setMobileOpen(true)} />

        <main className="flex-1 w-full max-w-7xl mx-auto">
          {children}
        </main>

        <footer className="mt-12 py-6 border-t border-white/[0.06] text-center text-xs text-app-muted flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-primary" />
            <span>Drishti.ai — Google Cloud BFSI Claims Intelligence</span>
          </div>
          <span className="font-mono text-[11px] text-app-muted/70">
            GCP drishti-demo • Vertex AI & Document AI
          </span>
        </footer>
      </div>

      {/* Claim Picker Dialog for Assistant (on non-claim routes) */}
      <ClaimChatPickerModal
        isOpen={isClaimPickerOpen}
        onClose={closeClaimPicker}
        currentClaimId={currentClaimId}
        onSelectClaim={(claimId) => {
          closeClaimPicker();
          navigate(`/claims/${claimId}?chat=open`);
        }}
      />
    </div>
  );
};
