import React, { useState, useMemo } from 'react';
import {
  MapPin, Clock, AlertTriangle,
  ExternalLink, ArrowRight, ShieldAlert, Navigation
} from 'lucide-react';
import { TimelineEvent } from '../types';

interface SpacetimeMapProps {
  timeline: TimelineEvent[];
  claimId: string;
  onOpenDocument?: (docId?: string) => void;
}

interface LegInfo {
  index: number;
  fromEvent: TimelineEvent;
  toEvent: TimelineEvent;
  km: number;
  availableMinutes: number;
  requiredHours: number;
  isImpossible: boolean;
  label: string;
}

function calculateHaversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  if (lat1 === lat2 && lon1 === lon2) return 0;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(6371 * c);
}

export const SpacetimeMap: React.FC<SpacetimeMapProps> = ({
  timeline,
  claimId,
  onOpenDocument
}) => {
  const [selectedEventIndex, setSelectedEventIndex] = useState<number | null>(0);

  // Compute transit legs between consecutive events for the same actor
  const legs = useMemo<LegInfo[]>(() => {
    const calculatedLegs: LegInfo[] = [];
    if (!timeline || timeline.length < 2) return calculatedLegs;

    // Group events by actor
    const actorGroups: Record<string, TimelineEvent[]> = {};
    timeline.forEach((ev) => {
      actorGroups[ev.actor] = actorGroups[ev.actor] || [];
      actorGroups[ev.actor].push(ev);
    });

    Object.values(actorGroups).forEach((evList) => {
      for (let i = 0; i < evList.length - 1; i++) {
        const from = evList[i];
        const to = evList[i + 1];

        const km = calculateHaversineKm(from.lat, from.lng, to.lat, to.lng);
        const msDiff = Math.abs(new Date(to.ts).getTime() - new Date(from.ts).getTime());
        const availableMinutes = Math.round(msDiff / 60000);
        const availableHours = availableMinutes / 60;
        const requiredHours = km <= 300 ? km / 80 : 2.5 + km / 700;

        const isImpossible = km >= 5 && availableHours < requiredHours;
        const label = isImpossible
          ? `${km.toLocaleString()} km in ${availableMinutes} min (Impossible)`
          : `${km.toLocaleString()} km in ${availableMinutes} min`;

        calculatedLegs.push({
          index: calculatedLegs.length,
          fromEvent: from,
          toEvent: to,
          km,
          availableMinutes,
          requiredHours,
          isImpossible,
          label
        });
      }
    });

    return calculatedLegs;
  }, [timeline]);

  // Geospatial bounds for coordinate-to-SVG projection
  // Coordinates for India roughly: Lat 8 to 33, Lng 68 to 92
  const mapBounds = useMemo(() => {
    if (!timeline || timeline.length === 0) {
      return { minLat: 8, maxLat: 33, minLng: 68, maxLng: 92 };
    }
    const lats = timeline.map((e) => e.lat).filter((l) => l !== 0);
    const lngs = timeline.map((e) => e.lng).filter((l) => l !== 0);

    const minLat = Math.min(...lats, 12);
    const maxLat = Math.max(...lats, 30);
    const minLng = Math.min(...lngs, 70);
    const maxLng = Math.max(...lngs, 85);

    const padLat = Math.max(2, (maxLat - minLat) * 0.25);
    const padLng = Math.max(2, (maxLng - minLng) * 0.25);

    return {
      minLat: minLat - padLat,
      maxLat: maxLat + padLat,
      minLng: minLng - padLng,
      maxLng: maxLng + padLng
    };
  }, [timeline]);

  // Projection helper: Lat/Lng -> SVG (X, Y) 800x600 viewBox
  const projectToSvg = (lat: number, lng: number): [number, number] => {
    const svgWidth = 800;
    const svgHeight = 550;
    const padding = 50;

    const x = padding + ((lng - mapBounds.minLng) / (mapBounds.maxLng - mapBounds.minLng)) * (svgWidth - 2 * padding);
    // Y is inverted because latitude goes North (up), but SVG Y goes down
    const y = svgHeight - padding - ((lat - mapBounds.minLat) / (mapBounds.maxLat - mapBounds.minLat)) * (svgHeight - 2 * padding);

    return [Math.round(x), Math.round(y)];
  };

  const hasImpossibleLeg = legs.some((l) => l.isImpossible);

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden space-y-0">
      {/* Top Banner Alert if Impossible Travel is detected */}
      {hasImpossibleLeg && (
        <div className="bg-rose-500/15 border-b border-rose-500/30 p-4 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-rose-500/20 border border-rose-500/40 flex items-center justify-center text-rose-400 shrink-0">
              <ShieldAlert className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-rose-300">
                Critical Spacetime Violation Detected
              </h4>
              <p className="text-xs text-rose-200/80">
                Attending doctor billed overlapping in-patient procedures across distant locations beyond physical transit feasibility.
              </p>
            </div>
          </div>
          <span className="text-xs font-mono font-bold px-2.5 py-1 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
            CRITICAL SEVERITY
          </span>
        </div>
      )}

      {/* Main Container: Map on Left (7 cols), Vertical Timeline on Right (5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 divide-y lg:divide-y-0 lg:divide-x divide-slate-800">
        {/* Interactive GIS Map Canvas */}
        <div className="lg:col-span-7 p-6 flex flex-col justify-between bg-slate-950/70 relative">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <Navigation className="w-4 h-4 text-blue-400" />
              <h3 className="text-sm font-bold text-white">Geospatial Transit Trajectory</h3>
            </div>
            <div className="flex items-center space-x-3 text-[11px] font-mono">
              <span className="flex items-center space-x-1 text-emerald-400">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                <span>Feasible Leg</span>
              </span>
              <span className="flex items-center space-x-1 text-rose-400">
                <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping"></span>
                <span>Impossible Leg</span>
              </span>
            </div>
          </div>

          {/* SVG Map Canvas */}
          <div className="relative w-full aspect-[4/3] rounded-2xl bg-slate-900/90 border border-slate-800/80 overflow-hidden flex items-center justify-center shadow-inner">
            {/* Background Grid Pattern */}
            <svg className="absolute inset-0 w-full h-full opacity-15 pointer-events-none">
              <defs>
                <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#60a5fa" strokeWidth="0.5" />
                </pattern>
              </defs>
              <rect width="100%" height="100%" fill="url(#grid)" />
            </svg>

            {/* GIS SVG Canvas */}
            <svg viewBox="0 0 800 550" className="w-full h-full relative z-10">
              <defs>
                {/* Impossible Leg Pulsing Glow Filter */}
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="3" result="blur" />
                  <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <marker
                  id="arrow-green"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 8 5 L 0 9 z" fill="#10b981" />
                </marker>
                <marker
                  id="arrow-red"
                  viewBox="0 0 10 10"
                  refX="6"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 8 5 L 0 9 z" fill="#f43f5e" />
                </marker>
              </defs>

              {/* Polylines for transit legs */}
              {legs.map((leg) => {
                const [x1, y1] = projectToSvg(leg.fromEvent.lat, leg.fromEvent.lng);
                const [x2, y2] = projectToSvg(leg.toEvent.lat, leg.toEvent.lng);

                const midX = (x1 + x2) / 2;
                const midY = (y1 + y2) / 2;

                return (
                  <g key={`leg-${leg.index}`}>
                    {/* Shadow / Glow line */}
                    {leg.isImpossible && (
                      <line
                        x1={x1}
                        y1={y1}
                        x2={x2}
                        y2={y2}
                        stroke="#f43f5e"
                        strokeWidth="8"
                        strokeOpacity="0.4"
                        className="animate-pulse"
                      />
                    )}

                    {/* Actual trajectory line */}
                    <line
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke={leg.isImpossible ? '#f43f5e' : '#10b981'}
                      strokeWidth={leg.isImpossible ? 3.5 : 2.5}
                      strokeDasharray={leg.isImpossible ? '6 4' : 'none'}
                      markerEnd={leg.isImpossible ? 'url(#arrow-red)' : 'url(#arrow-green)'}
                    />

                    {/* Distance & Time Label Badge at Midpoint */}
                    <g transform={`translate(${midX}, ${midY})`}>
                      <rect
                        x="-105"
                        y="-14"
                        width="210"
                        height="28"
                        rx="14"
                        fill={leg.isImpossible ? '#881337' : '#064e3b'}
                        stroke={leg.isImpossible ? '#f43f5e' : '#10b981'}
                        strokeWidth="1.5"
                        className={leg.isImpossible ? 'animate-bounce' : ''}
                      />
                      <text
                        x="0"
                        y="4"
                        textAnchor="middle"
                        fill="#ffffff"
                        fontSize="11"
                        fontWeight="bold"
                        fontFamily="monospace"
                      >
                        {leg.label}
                      </text>
                    </g>
                  </g>
                );
              })}

              {/* Numbered Event Markers */}
              {timeline.map((event, idx) => {
                const [x, y] = projectToSvg(event.lat, event.lng);
                const isSelected = selectedEventIndex === idx;
                const isDoctor = event.actor.toLowerCase().includes('dr') || event.actor.toLowerCase().includes('doctor');

                return (
                  <g
                    key={`marker-${idx}`}
                    transform={`translate(${x}, ${y})`}
                    onClick={() => setSelectedEventIndex(idx)}
                    className="cursor-pointer group"
                  >
                    {/* Pulsing ring for selected event */}
                    {isSelected && (
                      <circle
                        r="22"
                        fill="none"
                        stroke="#38bdf8"
                        strokeWidth="2.5"
                        strokeOpacity="0.8"
                        className="animate-ping"
                      />
                    )}

                    {/* Marker Outer Circle */}
                    <circle
                      r="16"
                      fill={isDoctor ? (hasImpossibleLeg ? '#e11d48' : '#2563eb') : '#059669'}
                      stroke="#ffffff"
                      strokeWidth="2"
                      className="shadow-lg transition-transform group-hover:scale-125"
                    />

                    {/* Marker Number */}
                    <text
                      x="0"
                      y="4"
                      textAnchor="middle"
                      fill="#ffffff"
                      fontSize="11"
                      fontWeight="bold"
                      fontFamily="monospace"
                    >
                      {idx + 1}
                    </text>

                    {/* Place Label Hover Tooltip */}
                    <text
                      x="0"
                      y="-22"
                      textAnchor="middle"
                      fill="#f1f5f9"
                      fontSize="10"
                      fontWeight="bold"
                      className="drop-shadow-md select-none pointer-events-none"
                    >
                      {event.place.split(',')[0]}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          <p className="text-[11px] text-slate-500 mt-3 text-center">
            Click any numbered pin or timeline card to review timestamp details and source documents.
          </p>
        </div>

        {/* Vertical Timeline Beside Map */}
        <div className="lg:col-span-5 p-6 space-y-4 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2 mb-3">
              <Clock className="w-4 h-4 text-cyan-400" />
              <span>Chrono-Spacetime Sequence ({timeline.length} Events)</span>
            </h3>

            {/* Timeline Cards in Time Order */}
            <div className="relative pl-6 space-y-4 before:content-[''] before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
              {timeline.map((event, idx) => {
                const isSelected = selectedEventIndex === idx;
                const isDoctor = event.actor.toLowerCase().includes('dr') || event.actor.toLowerCase().includes('doctor');
                const legAfter = legs.find((l) => l.fromEvent === event);

                return (
                  <div
                    key={idx}
                    onClick={() => setSelectedEventIndex(idx)}
                    className={`relative p-3.5 rounded-xl border transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-slate-900 border-sky-500 ring-1 ring-sky-500 shadow-lg shadow-sky-500/10'
                        : 'bg-slate-950 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    {/* Time indicator bullet */}
                    <div
                      className={`absolute -left-[27px] top-4 w-5 h-5 rounded-full border-2 border-slate-950 flex items-center justify-center text-[10px] font-bold font-mono text-white ${
                        isDoctor ? (hasImpossibleLeg ? 'bg-rose-600' : 'bg-blue-600') : 'bg-emerald-600'
                      }`}
                    >
                      {idx + 1}
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-bold text-white font-mono flex items-center space-x-1.5">
                          <Clock className="w-3 h-3 text-slate-400" />
                          <span>{new Date(event.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                          <span className="text-slate-500">({new Date(event.ts).toLocaleDateString([], { month: 'short', day: 'numeric' })})</span>
                        </span>
                        <span
                          className={`text-[9px] uppercase font-bold px-2 py-0.2 rounded border ${
                            isDoctor
                              ? 'bg-blue-500/15 text-blue-400 border-blue-500/30'
                              : 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          }`}
                        >
                          {event.actor}
                        </span>
                      </div>

                      <p className="text-xs font-semibold text-slate-200">{event.description || event.place}</p>
                      <p className="text-[11px] text-slate-400 flex items-center space-x-1">
                        <MapPin className="w-3 h-3 text-slate-500 shrink-0" />
                        <span className="truncate">{event.place}</span>
                      </p>

                      {/* Transit Leg alert between this and next event */}
                      {legAfter && (
                        <div
                          className={`mt-2 p-2 rounded-lg text-[10px] font-mono flex items-center justify-between border ${
                            legAfter.isImpossible
                              ? 'bg-rose-950/60 text-rose-300 border-rose-500/40 animate-pulse'
                              : 'bg-slate-900 text-slate-400 border-slate-800'
                          }`}
                        >
                          <div className="flex items-center space-x-1.5">
                            {legAfter.isImpossible ? (
                              <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                            ) : (
                              <ArrowRight className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                            )}
                            <span className="font-bold">Next Leg: {legAfter.label}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Action button to open source document */}
          <div className="pt-4 border-t border-slate-800 flex items-center justify-between text-xs">
            <span className="text-slate-400">
              Claim ID: <span className="font-mono text-white font-bold">{claimId}</span>
            </span>
            {onOpenDocument && (
              <button
                onClick={() => onOpenDocument(timeline[selectedEventIndex || 0]?.doc_id)}
                className="inline-flex items-center space-x-1.5 text-blue-400 hover:text-blue-300 font-medium"
              >
                <span>View Source Document</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
