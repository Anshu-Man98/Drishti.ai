import React, { useEffect, useState } from 'react';
import { useLocation, Link } from 'react-router-dom';
import {
  Menu,
  ChevronRight,
  Bell,
  Sun,
  Moon,
  CheckCircle,
  User,
} from 'lucide-react';
import { useTheme } from '../../context/ThemeContext';
import { SearchBar } from '../ui/SearchBar';
import { fetchAnalyticsSummary } from '../../services/api';

interface TopBarProps {
  onOpenMobile: () => void;
}

/**
 * TopBar - Rounded floating panel inspired by the Nexa security dashboard.
 * Features:
 * - Dynamic breadcrumb navigation
 * - Search bar with clean dark input
 * - Notification bell with live amber dot when claims await review
 * - Nexa-style segmented sun/moon theme pill toggle
 * - Verified adjuster profile chip
 */
export const TopBar: React.FC<TopBarProps> = ({ onOpenMobile }) => {
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const path = location.pathname;

  const [searchQuery, setSearchQuery] = useState('');
  const [reviewCount, setReviewCount] = useState<number>(0);

  useEffect(() => {
    let isMounted = true;
    fetchAnalyticsSummary(false)
      .then((summary) => {
        if (isMounted && summary?.verdicts?.review !== undefined) {
          setReviewCount(summary.verdicts.review);
        }
      })
      .catch(() => {
        // Fail-silent on background notification poll
      });
    return () => {
      isMounted = false;
    };
  }, [location.pathname]);

  // Generate dynamic breadcrumbs
  const getBreadcrumbs = () => {
    if (path === '/') {
      return [{ label: 'Executive Overview', path: '/' }];
    }
    if (path === '/claims') {
      return [{ label: 'Claims Audit Queue', path: '/claims' }];
    }
    if (path.startsWith('/claims/')) {
      const claimId = path.split('/')[2];
      return [
        { label: 'Claims Queue', path: '/claims' },
        { label: claimId, path: `/claims/${claimId}` },
      ];
    }
    if (path === '/network') {
      return [{ label: 'Fraud Ring Network', path: '/network' }];
    }
    if (path === '/upload') {
      return [{ label: 'Upload & Ingest Bill', path: '/upload' }];
    }
    if (path === '/duel') {
      return [{ label: 'Adversarial Duel Arena', path: '/duel' }];
    }
    return [{ label: 'Portal', path }];
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <header className="h-16 rounded-[20px] bg-app-surface/90 backdrop-blur-md border border-white/[0.08] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.07)] px-4 sm:px-6 flex items-center justify-between sticky top-4 z-30 mb-6 transition-colors">
      {/* Left: Hamburger & Dynamic Breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobile}
          className="lg:hidden p-2 rounded-xl text-app-muted hover:text-app-primary hover:bg-white/[0.06] transition-colors"
          aria-label="Open mobile navigation"
        >
          <Menu className="w-5 h-5" />
        </button>

        <nav className="flex items-center gap-1.5 text-xs sm:text-sm select-none" aria-label="Breadcrumb">
          <Link
            to="/"
            className="text-app-muted hover:text-amber-primary font-medium transition-colors"
          >
            FinShield
          </Link>
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={crumb.path}>
              <ChevronRight className="w-3.5 h-3.5 text-app-muted/60 shrink-0" />
              {idx === breadcrumbs.length - 1 ? (
                <span className="font-semibold text-app-primary font-mono text-xs sm:text-sm truncate max-w-[200px] sm:max-w-none">
                  {crumb.label}
                </span>
              ) : (
                <Link
                  to={crumb.path}
                  className="text-app-muted hover:text-amber-primary font-medium transition-colors truncate"
                >
                  {crumb.label}
                </Link>
              )}
            </React.Fragment>
          ))}
        </nav>
      </div>

      {/* Right Controls: Global Search, Notification Bell, Theme Pill, User Chip */}
      <div className="flex items-center gap-2 sm:gap-3">
        {/* Global Search Bar */}
        <div className="hidden md:block w-48 lg:w-64">
          <SearchBar
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search claims, hospitals..."
          />
        </div>

        {/* Notification Bell (amber dot only when claims await review) */}
        <Link
          to="/claims?verdict=review"
          className="relative p-2 rounded-xl text-app-muted hover:text-app-primary hover:bg-white/[0.06] border border-white/[0.08] transition-colors cursor-pointer"
          title={reviewCount > 0 ? `${reviewCount} claims awaiting review` : 'Notifications'}
          aria-label={reviewCount > 0 ? `${reviewCount} claims awaiting review` : 'Notifications'}
        >
          <Bell className="w-4 h-4" />
          {reviewCount > 0 && (
            <span
              className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amber-primary shadow-[0_0_6px_rgba(245,165,36,0.8)]"
              aria-hidden="true"
            />
          )}
        </Link>

        {/* Nexa-style Segmented Sun/Moon Theme Toggle */}
        <div
          role="radiogroup"
          aria-label="Theme mode selector"
          className="p-1 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center gap-1 select-none"
        >
          <button
            type="button"
            role="radio"
            aria-checked={theme === 'light'}
            onClick={() => theme !== 'light' && toggleTheme()}
            className={`p-1 rounded-lg text-xs transition-all cursor-pointer ${
              theme === 'light'
                ? 'bg-amber-primary/20 text-amber-primary shadow-xs'
                : 'text-app-muted hover:text-app-primary'
            }`}
            title="Light Theme (Warm Paper)"
            aria-label="Light Theme"
          >
            <Sun className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={theme === 'dark'}
            onClick={() => theme !== 'dark' && toggleTheme()}
            className={`p-1 rounded-lg text-xs transition-all cursor-pointer ${
              theme === 'dark'
                ? 'bg-amber-primary/20 text-amber-primary shadow-xs'
                : 'text-app-muted hover:text-app-primary'
            }`}
            title="Dark Theme (Amber & Black)"
            aria-label="Dark Theme"
          >
            <Moon className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Nexa User Profile Chip */}
        <div className="flex items-center gap-2.5 py-1 px-2.5 rounded-xl bg-white/[0.04] border border-white/[0.08] select-none">
          <div className="w-7 h-7 rounded-lg bg-amber-primary/14 border border-amber-primary/30 flex items-center justify-center text-amber-primary shrink-0">
            <User className="w-4 h-4" />
          </div>
          <div className="hidden sm:flex flex-col text-left">
            <span className="text-xs font-semibold text-app-primary leading-tight">
              Claims Officer
            </span>
            <div className="flex items-center gap-1 text-[10px] text-emerald-400 font-mono leading-tight">
              <span>Verified</span>
              <CheckCircle className="w-2.5 h-2.5" />
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
