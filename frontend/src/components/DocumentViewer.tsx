import React, { useState, useRef, useEffect, useMemo } from 'react';
import clsx from 'clsx';
import {
  ZoomIn, ZoomOut, RotateCcw, ChevronLeft, ChevronRight,
  Eye, AlertTriangle, Layers, FileText, CheckCircle2, ShieldAlert
} from 'lucide-react';
import { Finding, ExtractedEntity, Severity } from '../types';
import { fetchClaimPageBlob } from '../services/api';

export interface PaddedBbox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  width: number;
  height: number;
  wasExpanded: boolean;
}

/**
 * Ensures degenerate, hairline, or tiny bounding boxes from Document AI / PyPDF
 * are padded to a minimum visible height (>= 14px) and visible width, clamped within [0, 1].
 */
export function padHairlineBbox(
  bbox: [number, number, number, number],
  pageWidthPx = 1000,
  pageHeightPx = 1000,
  minHeightPx = 14,
  minWidthPx = 120
): PaddedBbox {
  let [x0, y0, x1, y1] = bbox;
  if (x0 > x1) [x0, x1] = [x1, x0];
  if (y0 > y1) [y0, y1] = [y1, y0];

  const minHeightNorm = minHeightPx / pageHeightPx;
  const minWidthNorm = minWidthPx / pageWidthPx;

  let heightNorm = y1 - y0;
  let widthNorm = x1 - x0;
  let wasExpanded = false;

  if (heightNorm < minHeightNorm) {
    const pad = (minHeightNorm - heightNorm) / 2;
    y0 = Math.max(0, y0 - pad);
    y1 = Math.min(1, y0 + minHeightNorm);
    if (y1 >= 1) {
      y0 = Math.max(0, 1 - minHeightNorm);
    }
    heightNorm = y1 - y0;
    wasExpanded = true;
  }

  if (widthNorm < minWidthNorm) {
    const pad = (minWidthNorm - widthNorm) / 2;
    x0 = Math.max(0, x0 - pad);
    x1 = Math.min(1, x0 + minWidthNorm);
    if (x1 >= 1) {
      x0 = Math.max(0, 1 - minWidthNorm);
    }
    widthNorm = x1 - x0;
    wasExpanded = true;
  }

  return {
    x0,
    y0,
    x1,
    y1,
    width: widthNorm,
    height: heightNorm,
    wasExpanded,
  };
}

export interface HiddenTextRun {
  id: string;
  findingId: string;
  page: number;
  bbox: [number, number, number, number] | null;
  quote: string;
  reason?: string;
  hasBbox: boolean;
}

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
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageLoading, setImageLoading] = useState(true);
  const [imageError, setImageError] = useState<string | null>(null);
  const [hovered, setHovered] = useState<HoveredInfo | null>(null);

  const containerRef = useRef<HTMLDivElement>(null);
  const activeRectRef = useRef<SVGRectElement>(null);

  // Authenticated document page image fetching with Blob Object URL management
  useEffect(() => {
    let isCancelled = false;
    let createdUrl: string | null = null;

    setImageLoaded(false);
    setImageLoading(true);
    setImageError(null);
    setImageUrl(null);

    const loadPage = async () => {
      try {
        const blob = await fetchClaimPageBlob(claimId, currentPage);
        if (isCancelled) return;
        const objectUrl = URL.createObjectURL(blob);
        createdUrl = objectUrl;
        setImageUrl(objectUrl);
        setImageLoading(false);
      } catch (err: any) {
        if (isCancelled) return;
        setImageError(err.message || 'Failed to load page image');
        setImageLoading(false);
        setImageLoaded(false);
      }
    };

    loadPage();

    return () => {
      isCancelled = true;
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [claimId, currentPage]);

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

  // Collect all hidden text runs across findings
  const hiddenRuns = useMemo<HiddenTextRun[]>(() => {
    return findings.flatMap((f) => {
      const hiddenEv = (f.evidence || []).filter(
        (ev) => ev.layer === 'hidden' || f.agent === 'injection' || f.check_id === 'hidden_text_instruction'
      );
      if (hiddenEv.length > 0) {
        return hiddenEv.map((ev, evIdx) => ({
          id: `${f.finding_id}-${evIdx}`,
          findingId: f.finding_id,
          page: ev.page || 1,
          bbox: ev.bbox && ev.bbox.length === 4 ? (ev.bbox as [number, number, number, number]) : null,
          quote: ev.quote || f.explanation || f.title,
          reason: f.computed_details?.reason || (ev.bbox ? 'rendered hidden text' : 'metadata payload'),
          hasBbox: Boolean(ev.bbox && ev.bbox.length === 4),
        }));
      }
      if (f.agent === 'injection' || f.check_id === 'hidden_text_instruction') {
        return [{
          id: `${f.finding_id}-0`,
          findingId: f.finding_id,
          page: 1,
          bbox: null,
          quote: f.explanation || f.title,
          reason: f.computed_details?.reason || 'metadata payload',
          hasBbox: false,
        }];
      }
      return [];
    });
  }, [findings]);

  const hasHiddenInjections = hiddenRuns.length > 0;
  const [pulsingRunId, setPulsingRunId] = useState<string | null>(null);

  const handleJumpToHiddenRun = (run: HiddenTextRun) => {
    if (run.page !== currentPage) {
      setCurrentPage(run.page);
    }
    setPulsingRunId(run.id);

    setTimeout(() => {
      const el = document.getElementById(`hidden-overlay-${run.id}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 100);

    setTimeout(() => {
      setPulsingRunId(null);
    }, 3000);
  };

  const handleToggleRevealHidden = () => {
    if (!hasHiddenInjections) return;
    const nextVal = !revealHiddenLayer;
    setRevealHiddenLayer(nextVal);
    if (nextVal) {
      const firstWithBbox = hiddenRuns.find((r) => r.hasBbox);
      if (firstWithBbox) {
        handleJumpToHiddenRun(firstWithBbox);
      }
    }
  };

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
    <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 shadow-2xs backdrop-blur-md space-y-4 flex flex-col">
      {/* Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-white/8 text-xs">
        {/* Left: Title & Page Selector */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5 font-bold text-text-primary">
            <FileText className="w-4 h-4 text-amber-primary" />
            <span>Document AI Viewer</span>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center space-x-1 bg-surface-elevated px-2 py-1 rounded-lg border border-white/10">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                className="p-1 hover:text-text-primary disabled:text-muted disabled:hover:text-muted"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
              </button>
              <span className="font-mono text-text-primary px-1">
                {currentPage} / {totalPages}
              </span>
              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                className="p-1 hover:text-text-primary disabled:text-muted disabled:hover:text-muted"
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
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border text-xs font-medium transition-colors ${
              showAllFields
                ? 'bg-amber-primary/15 border-amber-primary/40 text-amber-primary'
                : 'bg-surface-elevated border-white/10 text-muted hover:text-text-primary'
            }`}
            title="Toggle between showing only flagged anomalies or all Document AI extracted fields"
          >
            {showAllFields ? <Layers className="w-3.5 h-3.5 text-amber-primary" /> : <Eye className="w-3.5 h-3.5" />}
            <span>{showAllFields ? 'Showing All Fields' : 'Flags Only'}</span>
            <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-surface text-text-secondary font-mono border border-white/5">
              {showAllFields ? entityBoxes.length + findingBoxes.length : findingBoxes.length}
            </span>
          </button>

          {/* Reveal Hidden Layer Toggle Button (Feature A1) */}
          <button
            disabled={!hasHiddenInjections}
            onClick={handleToggleRevealHidden}
            className={clsx(
              "flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-semibold transition-all",
              !hasHiddenInjections && "opacity-40 cursor-not-allowed bg-slate-900/30 border-slate-800 text-slate-500",
              hasHiddenInjections && revealHiddenLayer && "bg-rose-600/25 border-rose-500 text-rose-300 shadow-md shadow-rose-500/20 ring-1 ring-rose-500",
              hasHiddenInjections && !revealHiddenLayer && "bg-rose-950/40 border-rose-800/80 text-rose-400 hover:bg-rose-900/40 animate-pulse cursor-pointer"
            )}
            title={!hasHiddenInjections ? "No hidden text found in this document" : "Toggle revealing hidden text prompt injections buried in document layers"}
            aria-label={!hasHiddenInjections ? "No hidden text found in this document" : "Reveal Hidden Layer"}
          >
            <ShieldAlert className={clsx("w-3.5 h-3.5", hasHiddenInjections ? "text-rose-400" : "text-slate-500")} />
            <span>{revealHiddenLayer ? 'Hidden Layer Revealed' : 'Reveal Hidden Layer'}</span>
            {hasHiddenInjections && (
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-rose-500/30 text-rose-200 font-mono font-bold">
                {hiddenRuns.length}
              </span>
            )}
          </button>

          {/* Zoom Buttons */}
          <div className="flex items-center space-x-1 bg-surface-elevated px-2 py-1 rounded-xl border border-white/10 text-muted">
            <button
              onClick={handleZoomOut}
              className="p-1 hover:text-text-primary transition-colors"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <span className="font-mono text-[11px] px-1 text-text-primary">{zoom}%</span>
            <button
              onClick={handleZoomIn}
              className="p-1 hover:text-text-primary transition-colors"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleResetZoom}
              className="p-1 hover:text-text-primary border-l border-white/10 pl-1.5 ml-0.5 transition-colors"
              title="Reset Zoom"
            >
              <RotateCcw className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* Hidden text found (N) Banner */}
      {revealHiddenLayer && hasHiddenInjections && (
        <div
          data-testid="hidden-text-banner"
          className="bg-rose-950/80 border-2 border-rose-500 rounded-xl p-3.5 space-y-2.5 shadow-xl backdrop-blur-md animate-in fade-in slide-in-from-top-1 duration-200"
        >
          <div className="flex items-center justify-between gap-2 border-b border-rose-500/30 pb-2">
            <div className="flex items-center space-x-2">
              <ShieldAlert className="w-4 h-4 text-rose-400 animate-pulse" />
              <span className="font-bold text-white text-xs tracking-wide">
                Hidden text found ({hiddenRuns.length})
              </span>
            </div>
            <span className="text-[10px] font-mono uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-rose-500/30 text-rose-200 border border-rose-500/40">
              Quarantined Injection Layer
            </span>
          </div>

          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
            {hiddenRuns.map((run, idx) => (
              <div
                key={run.id}
                className="bg-black/75 border border-rose-500/35 rounded-lg p-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-1.5 py-0.5 rounded bg-rose-900/60 text-rose-200 font-mono text-[10px] font-bold">
                      Run #{idx + 1}
                    </span>
                    {run.hasBbox ? (
                      <span className="text-[11px] font-mono text-rose-300">
                        Page {run.page} • Physical Bounding Box Located
                      </span>
                    ) : (
                      <span className="text-[11px] font-mono text-amber-300 font-semibold">
                        Hidden text detected in document metadata (page {run.page}, location unavailable)
                      </span>
                    )}
                  </div>
                  <p className="font-mono text-[11px] text-rose-100 bg-rose-950/50 p-2 rounded border border-rose-500/25 break-all select-all font-medium">
                    "{run.quote}"
                  </p>
                </div>

                {run.hasBbox && (
                  <button
                    onClick={() => handleJumpToHiddenRun(run)}
                    className="shrink-0 flex items-center justify-center space-x-1 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-medium text-xs shadow-md transition-colors cursor-pointer"
                    title={`Jump to hidden text overlay on Page ${run.page}`}
                  >
                    <span>Jump to</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Main Document Display Area */}
      <div
        ref={containerRef}
        className="relative flex-1 min-h-[480px] max-h-[700px] overflow-auto bg-black/60 rounded-xl border border-white/8 p-2 flex justify-center items-start"
      >
        <div
          className="relative transition-all duration-150 inline-block shadow-2xl"
          style={{ width: `${zoom}%`, maxWidth: zoom <= 100 ? '100%' : 'none' }}
        >
          {/* Rendered 150 DPI Page Image */}
          {imageUrl && !imageError && (
            <img
              src={imageUrl}
              alt={`Claim Document Page ${currentPage}`}
              className={`w-full h-auto rounded block select-none bg-white transition-opacity duration-150 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
              onLoad={() => {
                setImageLoaded(true);
                setImageError(null);
              }}
              onError={() => {
                setImageError('Failed to display page image.');
                setImageLoaded(false);
              }}
            />
          )}

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

            </svg>
          )}

          {/* Hidden Layer Overlays (HTML layer: guaranteed visible, min-height >= 14px, high contrast label) */}
          {revealHiddenLayer &&
            hiddenRuns
              .filter((run) => run.page === currentPage && run.hasBbox && run.bbox)
              .map((run) => {
                const padded = padHairlineBbox(run.bbox!, 1000, 1000, 16, 140);
                const isPulsing = pulsingRunId === run.id;

                return (
                  <button
                    type="button"
                    key={run.id}
                    id={`hidden-overlay-${run.id}`}
                    data-testid="hidden-layer-overlay"
                    aria-label={`Hidden layer text: ${run.quote}`}
                    className={clsx(
                      "absolute pointer-events-auto cursor-pointer transition-all duration-300 rounded-xs text-left",
                      "border-2 border-dashed border-red-500 bg-red-500/20",
                      "shadow-[0_0_15px_rgba(239,68,68,0.7)]",
                      isPulsing && "ring-4 ring-rose-400 ring-offset-2 ring-offset-black scale-105"
                    )}
                    style={{
                      left: `${padded.x0 * 100}%`,
                      top: `${padded.y0 * 100}%`,
                      width: `${padded.width * 100}%`,
                      height: `${padded.height * 100}%`,
                      minHeight: '16px',
                      minWidth: '90px',
                      zIndex: 25,
                    }}
                    onClick={() => {
                      if (run.findingId && onSelectFinding) {
                        onSelectFinding(run.findingId);
                      }
                    }}
                  >
                    {/* High contrast monospace label chip */}
                    <div className="absolute -top-7 left-0 z-30 flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-950 text-white border border-red-500 text-[10px] font-mono font-bold shadow-2xl whitespace-nowrap pointer-events-none select-none">
                      <span className="w-2 h-2 rounded-full bg-red-500 animate-ping inline-block" />
                      <span className="text-red-400 font-extrabold tracking-wide">HIDDEN LAYER:</span>
                      <span className="max-w-[220px] sm:max-w-[340px] truncate text-white">
                        {run.quote}
                      </span>
                    </div>
                  </button>
                );
              })}

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

          {/* Real loading state */}
          {imageLoading && (
            <div className="p-16 text-center text-slate-400 text-xs flex flex-col items-center justify-center space-y-3">
              <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              <p className="font-medium text-slate-300">Loading high-resolution document page {currentPage}...</p>
            </div>
          )}

          {/* Clear error state */}
          {imageError && !imageLoading && (
            <div className="p-12 text-center space-y-2 text-slate-400 text-xs">
              <AlertTriangle className="w-6 h-6 text-amber-400 mx-auto" />
              <p className="font-semibold text-slate-200">Document preview unavailable</p>
              <p className="text-rose-400 text-[11px] font-mono">{imageError}</p>
            </div>
          )}
        </div>
      </div>

      {/* Legend Footer */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-app-default text-[11px] text-app-muted">
        <div className="flex items-center space-x-3">
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-500/40 border border-rose-500"></span>
            <span className="text-app-primary">Critical</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-orange-500/40 border border-orange-500"></span>
            <span className="text-app-primary">High Risk</span>
          </span>
          <span className="flex items-center space-x-1">
            <span className="w-2.5 h-2.5 rounded-sm bg-amber-500/40 border border-amber-500"></span>
            <span className="text-app-primary">Medium</span>
          </span>
          {showAllFields && (
            <span className="flex items-center space-x-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-stone-300 dark:bg-slate-700 border border-dashed border-stone-500 dark:border-slate-400"></span>
              <span className="text-app-primary">Extracted Field</span>
            </span>
          )}
        </div>
        <span className="text-[10px] text-app-muted">
          Click any flag or card to focus citation
        </span>
      </div>
    </div>
  );
};
