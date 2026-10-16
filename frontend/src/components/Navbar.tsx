import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, Upload, FileText, Activity } from 'lucide-react';
import { fetchHealthStatus, HealthStatus } from '../services/api';

export const Navbar: React.FC = () => {
  const location = useLocation();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHealthStatus()
      .then((data) => {
        setHealth(data);
        setLoading(false);
      })
      .catch(() => {
        setHealth(null);
        setLoading(false);
      });
  }, []);

  const navItems = [
    { label: 'Claims Audit', path: '/', icon: FileText },
    { label: 'Upload Claim', path: '/upload', icon: Upload },
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center space-x-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 p-0.5 shadow-lg shadow-blue-500/20">
            <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
              <Shield className="w-5 h-5 text-blue-400 group-hover:scale-110 transition-transform" />
            </div>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-tight text-white">FinShield</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-mono">Drishti.ai</span>
            </div>
            <p className="text-xs text-slate-400">Multi-Agent Insurance Fraud Copilot</p>
          </div>
        </Link>

        <nav className="flex items-center space-x-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-sm shadow-blue-500/25'
                    : 'text-slate-300 hover:text-white hover:bg-slate-800'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="hidden md:flex items-center space-x-3 text-xs">
          {loading ? (
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-slate-800/80 text-slate-400 border border-slate-700">
              <Activity className="w-3.5 h-3.5 animate-spin text-slate-400" />
              <span>Connecting...</span>
            </div>
          ) : health && health.status === 'healthy' && health.all_healthy ? (
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md border bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>All Cloud Services Healthy ({health.models?.flash || 'Gemini'})</span>
            </div>
          ) : health ? (
            <div
              className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md border bg-amber-500/10 text-amber-400 border-amber-500/20"
              title={JSON.stringify(health.dependencies || {})}
            >
              <span className="w-2 h-2 rounded-full bg-amber-400"></span>
              <span>Cloud Services Degraded</span>
            </div>
          ) : (
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              <span>Backend Disconnected</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
