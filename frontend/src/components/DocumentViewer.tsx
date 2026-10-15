import React, { useState, useRef, useEffect } from 'react';
import {
  ZoomIn, ZoomOut, RotateCcw, ChevronLeft, ChevronRight,
  Eye, AlertTriangle, Layers, FileText, CheckCircle2, ShieldAlert
} from 'lucide-react';
import { Finding, ExtractedEntity, Severity } from '../types';
import { getClaimPageImageUrl } from '../services/api';

interface DocumentViewerProps {
  claimId: string;
  pageCount?: number;
  findings?: Finding[];
  entities?: ExtractedEntity[];
  activeFindingId?: string | null;
  onSelectFinding?: (findingId: string) => void;
}

interface HoveredInfo {
  id: string;
  title: string;
  subtitle?: string;
  severity?: Severity;
  confidence?: number;
  source?: string;
  x: number;
  y: number;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  claimId,
  pageCount = 1,
  findings = [],
  entities = [],
  activeFindingId,
  onSelectFinding
}) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [showAllFields, setShowAllFields] = useState(false);
  const [revealHiddenLayer, setRevealHiddenLayer] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [hovered, setHovered] = useState<HoveredInfo | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const activeRectRef = useRef<SVGRectElement>(null);

  // Auto-scroll to active finding rectangle when selected
  useEffect(() => {
    if (activeFindingId && activeRectRef.current) {
      activeRectRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
        inline: 'center'
      });
    }
  }, [activeFindingId, currentPage]);

  const totalPages = Math.max(1, pageCount);

  const hasHiddenInjections = findings.some((f) =>
    (f.evidence || []).some((ev) => ev.layer === 'hidden')
  );

  // Collect boxes for current page
  // 1. Finding evidence boxes (visible layer)
  const findingBoxes = findings.flatMap((f) => {
    return (f.evidence || [])
      .filter((ev) => (ev.page || 1) === currentPage && ev.bbox && ev.bbox.length === 4 && ev.layer !== 'hidden')
      .map((ev, evIdx) => ({
        id: `${f.finding_id}-${evIdx}`,
        findingId: f.finding_id,
        isFinding: true,
        bbox: ev.bbox as [number, number, number, number],
        severity: f.severity,
        title: f.title,
        subtitle: ev.quote || f.explanation,
        confidence: f.confidence,
        isActive: f.finding_id === activeFindingId
      }));
  });

  // 1b. Planted hidden injection boxes (shown only when revealHiddenLayer is toggled)
  const hiddenBoxes = revealHiddenLayer
    ? findings.flatMap((f) => {
        return (f.evidence || [])
          .filter((ev) => (ev.page || 1) === currentPage && ev.bbox && ev.bbox.length === 4 && ev.layer === 'hidden')
          .map((ev, evIdx) => ({
            id: `hidden-${f.finding_id}-${evIdx}`,
            findingId: f.finding_id,
            isFinding: true,
            bbox: ev.bbox as [number, number, number, number],
            severity: f.severity,
            title: `Quarantined Injection: ${f.title}`,
            subtitle: ev.quote || f.explanation,
            confidence: f.confidence,
            isActive: f.finding_id === activeFindingId
          }));
      })
    : [];

  // 2. Extracted entity boxes (if showAllFields is enabled)
  const entityBoxes = showAllFields
    ? entities
        .filter((e) => (e.page || 1) === currentPage && e.bbox && e.bbox.length === 4)
        .map((e, idx) => ({
          id: `entity-${idx}`,
          findingId: undefined,
          isFinding: false,
          bbox: e.bbox as [number, number, number, number],
          severity: undefined,
          title: `Field: ${e.field_name.replace(/_/g, ' ')}`,
          subtitle: e.text,
          confidence: e.confidence,
          source: e.source,
          isActive: false
        }))
    : [];

  const getSeverityColors = (sev?: Severity, isActive?: boolean) => {
    if (isActive) {
      return {
        stroke: '#38bdf8', // bright sky-blue
        fill: 'rgba(56, 189, 248, 0.35)',
        className: 'stroke-[3] drop-shadow-[0_0_8px_rgba(56,189,248,0.8)] animate-pulse'
      };
    }
    switch (sev) {
      case 'critical':
        return {
          stroke: '#ef4444',
          fill: 'rgba(239, 68, 68, 0.28)',
          className: 'stroke-2 hover:stroke-[3] transition-all'
        };
      case 'high':
        return {
          stroke: '#f97316',
          fill: 'rgba(249, 115, 22, 0.28)',
          className: 'stroke-2 hover:stroke-[3] transition-all'
        };
      case 'medium':
        return {
          stroke: '#eab308',
          fill: 'rgba(234, 179, 8, 0.25)',
          className: 'stroke-2 hover:stroke-[3] transition-all'
        };
      case 'low':
        return {
          stroke: '#3b82f6',
          fill: 'rgba(59, 130, 246, 0.22)',
          className: 'stroke-2 hover:stroke-[3] transition-all'
        };
      case 'info':
        return {
          stroke: '#06b6d4',
          fill: 'rgba(6, 182, 212, 0.18)',
          className: 'stroke-2 hover:stroke-[3] transition-all'
        };
      default:
        // Entity box
        return {
          stroke: '#94a3b8',
          fill: 'rgba(148, 163, 184, 0.12)',
          className: 'stroke-1 stroke-dashed hover:stroke-[2] transition-all'
        };
    }
  };

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 25, 200));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 25, 75));
  const handleResetZoom = () => setZoom(100);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-xl space-y-4 flex flex-col h-full">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800 text-xs">
        {/* Left: Title & Page Selector */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5 font-bold text-white">
            <FileText className="w-4 h-4 text-blue-400" />
            <span>Document AI Viewer</span>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center space-x-1 bg-slate-950 px-2 py-1 rounded-lg border border-slate-800">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                className="p-1 hover:text-white disabled:text-slate-600 disabled:hover:text-slate-600"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span className="font-mono text-slate-300 px-1">
                {currentPage} / {totalPages}
              </span>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                className="p-1 hover:text-white disabled:text-slate-600 disabled:hover:text-slate-600"
              >
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Right: Toggle Flags vs All Fields & Zoom Controls */}
        <div className="flex items-center space-x-2">
          {/* Toggle Button */}
          <button
            onClick={() => setShowAllFields(!showAllFields)}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium transition-colors ${
              showAllFields
                ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle between showing only flagged anomalies or all Document AI extracted fields"
          >
            {showAllFields ? <Layers className="w-3.5 h-3.5 text-blue-400" /> : <Eye className="w-3.5 h-3.5" />}
            <span>{showAllFields ? 'Showing All Fields' : 'Flags Only'}</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-800 text-slate-300 font-mono">
              {showAllFields ? entityBoxes.length + findingBoxes.length : findingBoxes.length}
            </span>
          </button>

          {/* Reveal Hidden Layer Toggle Button (Feature A1) */}
          <button
            onClick={() => setRevealHiddenLayer(!revealHiddenLayer)}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-semibold transition-all ${
              revealHiddenLayer
                ? 'bg-fuchsia-600/25 border-fuchsia-500 text-fuchsia-300 shadow-md shadow-fuchsia-500/20 ring-1 ring-fuchsia-500'
                : hasHiddenInjections
                ? 'bg-fuchsia-950/40 border-fuchsia-800/80 text-fuchsia-400 hover:bg-fuchsia-900/40 animate-pulse'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle revealing hidden text prompt injections buried in document layers"
          >
            <ShieldAlert className="w-3.5 h-3.5 text-fuchsia-400" />
            <span>{revealHiddenLayer ? 'Hidden Layer Revealed' : 'Reveal Hidden Layer'}</span>
            {hasHiddenInjections && (
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-fuchsia-500/30 text-fuchsia-200 font-mono font-bold">
                ALERT
              </span>
            )}
          </button>

          {/* Zoom Buttons */}
          <div className="flex items-center space-x-1 bg-slate-950 px-1.5 py-1 rounded-lg border border-slate-800 text-slate-400">
            <button
              onClick={handleZoomOut}
              className="p-1 hover:text-white"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="font-mono text-[11px] px-1 text-slate-300">{zoom}%</span>
            <button
              onClick={handleZoomIn}
              className="p-1 hover:text-white"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleResetZoom}
              className="p-1 hover:text-white border-l border-slate-800 pl-1.5 ml-0.5"
              title="Reset Zoom"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Document Display Area */}
      <div
        ref={containerRef}
        className="relative flex-1 min-h-[480px] max-h-[700px] overflow-auto bg-slate-950 rounded-xl border border-slate-800/80 p-2 flex justify-center items-start"
      >
        <div
          className="relative transition-all duration-150 inline-block shadow-2xl"
          style={{ width: `${zoom}%`, maxWidth: zoom <= 100 ? '100%' : 'none' }}
        >
          {/* Rendered 150 DPI Page Image */}
          <img
            src={getClaimPageImageUrl(claimId, currentPage)}
            alt={`Claim Document Page ${currentPage}`}
            className="w-full h-auto rounded block select-none bg-white"
            onLoad={() => {
              setImageLoaded(true);
              setImageError(false);
            }}
            onError={() => {
              setImageError(true);
              setImageLoaded(false);
            }}
          />

          {/* SVG Bounding Boxes Overlay */}
          {imageLoaded && (
            <svg
              className="absolute inset-0 w-full h-full pointer-events-none"
              viewBox="0 0 1000 1000"
              preserveAspectRatio="none"
            >
              {/* 1. Entity Boxes (when enabled) */}
              {entityBoxes.map((box) => {
                const [x0, y0, x1, y1] = box.bbox;
                const x = x0 * 1000;
                const y = y0 * 1000;
                const w = Math.max(4, (x1 - x0) * 1000);
                const h = Math.max(4, (y1 - y0) * 1000);
                const colors = getSeverityColors(undefined, false);

                return (
                  <rect
                    key={box.id}
                    x={x}
                    y={y}
                    width={w}
                    height={h}
                    fill={colors.fill}
                    stroke={colors.stroke}
                    strokeDasharray="4 2"
                    className={`${colors.className} pointer-events-auto cursor-pointer`}
                    onMouseEnter={() =>
                      setHovered({
                        id: box.id,
                        title: box.title,
                        subtitle: box.subtitle,
                        confidence: box.confidence,
                        source: box.source,
                        x: x0,
                        y: y0
                      })
                    }
                    onMouseLeave={() => setHovered(null)}
                  />
                );
              })}

              {/* 2. Finding Evidence Boxes */}
              {findingBoxes.map((box) => {
                const [x0, y0, x1, y1] = box.bbox;
                const x = x0 * 1000;
                const y = y0 * 1000;
                const w = Math.max(4, (x1 - x0) * 1000);
                const h = Math.max(4, (y1 - y0) * 1000);
                const colors = getSeverityColors(box.severity, box.isActive);

                return (
                  <rect
                    key={box.id}
                    ref={box.isActive ? activeRectRef : undefined}
                    x={x}
                    y={y}
                    width={w}
                    height={h}
                    fill={colors.fill}
                    stroke={colors.stroke}
                    className={`${colors.className} pointer-events-auto cursor-pointer`}
                    onClick={() => {
                      if (box.findingId && onSelectFinding) {
                        onSelectFinding(box.findingId);
                      }
                    }}
                    onMouseEnter={() =>
                      setHovered({
                        id: box.id,
                        title: box.title,
                        subtitle: box.subtitle,
                        severity: box.severity,
                        confidence: box.confidence,
                        x: x0,
                        y: y0
                      })
                    }
                    onMouseLeave={() => setHovered(null)}
                  />
                );
              })}

              {/* 3. Planted Hidden Injection Boxes (Magenta at Real Coordinates - Feature A1) */}
              {hiddenBoxes.map((box) => {
                const [x0, y0, x1, y1] = box.bbox;
                const x = x0 * 1000;
                const y = y0 * 1000;
                const w = Math.max(90, (x1 - x0) * 1000);
                const h = Math.max(22, (y1 - y0) * 1000);

                return (
                  <g key={box.id} className="pointer-events-auto">
                    <rect
                      x={x}
                      y={y}
                      width={w}
                      height={h}
                      fill="rgba(217, 70, 239, 0.32)"
                      stroke="#d946ef"
                      strokeWidth="3"
                      strokeDasharray="6 3"
                      className="drop-shadow-[0_0_12px_rgba(217,70,239,0.85)] animate-pulse cursor-pointer"
                      onClick={() => {
                        if (box.findingId && onSelectFinding) {
                          onSelectFinding(box.findingId);
                        }
                      }}
                      onMouseEnter={() =>
                        setHovered({
                          id: box.id,
                          title: "🚨 Planted Prompt Injection (Quarantined)",
                          subtitle: box.subtitle,
                          severity: "critical",
                          confidence: 1.0,
                          source: "injection_detector",
                          x: x0,
                          y: y0
                        })
                      }
                      onMouseLeave={() => setHovered(null)}
                    />
                    <foreignObject
                      x={Math.max(10, Math.min(x, 600))}
                      y={Math.max(10, y - 65)}
                      width={420}
                      height={65}
                      className="overflow-visible pointer-events-none"
                    >
                      <div className="bg-fuchsia-950/95 text-fuchsia-100 border-2 border-fuchsia-400 p-2 rounded-lg text-[10px] font-mono leading-tight shadow-2xl backdrop-blur-md">
                        <span className="text-[9px] font-bold uppercase text-fuchsia-300 block mb-0.5 tracking-wider">
                          🚨 Planted Instruction Buried at Coordinates:
                        </span>
                        <p className="line-clamp-2 font-semibold text-white">"{box.subtitle}"</p>
                      </div>
                    </foreignObject>
                  </g>
                );
              })}
            </svg>
          )}

          {/* Hover Tooltip Overlay */}
          {hovered && (
            <div
              className="absolute z-20 pointer-events-none transition-all duration-75 transform -translate-y-full -translate-x-1/2 left-0 top-0 mb-2"
              style={{
                left: `${Math.min(Math.max(hovered.x * 100, 15), 85)}%`,
                top: `${hovered.y * 100}%`
              }}
            >
              <div className="bg-slate-900/95 backdrop-blur-md border border-slate-700 text-white rounded-lg p-2.5 shadow-2xl text-[11px] max-w-xs space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-bold font-mono text-slate-100 flex items-center space-x-1 truncate">
                    {hovered.severity ? (
                      <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
                    ) : (
                      <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                    )}
                    <span>{hovered.title}</span>
                  </span>
                  {hovered.severity && (
                    <span
                      className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                        hovered.severity === 'critical'
                          ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                          : hovered.severity === 'high'
                          ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                          : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                      }`}
                    >
                      {hovered.severity}
                    </span>
                  )}
                </div>

                {hovered.subtitle && (
                  <p className="text-slate-300 text-[10px] leading-tight line-clamp-2">
                    {hovered.subtitle}
                  </p>
                )}

                <div className="flex items-center justify-between text-[9px] text-slate-400 pt-1 border-t border-slate-800">
                  {hovered.source && <span>Source: {hovered.source}</span>}
                  {hovered.confidence !== undefined && (
                    <span className="font-mono text-blue-400">
                      Confidence: {(hovered.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Loading or Error State */}
          {!imageLoaded && !imageError && (
            <div className="p-12 text-center text-slate-500 text-xs">
              Rendering high-resolution document...
            </div>
          )}

          {imageError && (
            <div className="p-12 text-center space-y-2 text-slate-400 text-xs">
              <AlertTriangle className="w-6 h-6 text-amber-400 mx-auto" />
              <p>Document preview unavailable or processing.</p>
            </div>
          )}
        </div>
      </div>

      {/* Legend Footer */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-800 text-[11px] text-slate-400">
        <div className="flex items-center space-x-3">
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-500/40 border border-rose-500"></span>
            <span>Critical</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-orange-500/40 border border-orange-500"></span>
            <span>High Risk</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-500/40 border border-amber-500"></span>
            <span>Medium</span>
          </span>
          {showAllFields && (
            <span className="flex items-center space-x-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-slate-700 border border-dashed border-slate-400"></span>
              <span>Extracted Field</span>
            </span>
          )}
        </div>
        <span className="text-[10px] text-slate-500">
          Click any flag or card to focus citation
        </span>
      </div>
    </div>
  );
};
