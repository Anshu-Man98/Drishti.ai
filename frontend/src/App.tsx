import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { ClaimsList } from './pages/ClaimsList';
import { ClaimDetail } from './pages/ClaimDetail';
import { UploadClaim } from './pages/UploadClaim';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
        <Navbar />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<ClaimsList />} />
            <Route path="/claims/:id" element={<ClaimDetail />} />
            <Route path="/upload" element={<UploadClaim />} />
          </Routes>
        </main>
        <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-600">
          FinShield (Drishti.ai) — Google Cloud BFSI Intelligent Risk & Fraud Copilot
        </footer>
      </div>
    </BrowserRouter>
  );
};

export default App;
