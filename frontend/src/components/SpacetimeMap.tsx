import React, { useState, useMemo, useEffect } from 'react';
import {
  APIProvider,
  Map,
  AdvancedMarker,
  Pin,
} from '@vis.gl/react-google-maps';
import {
  ShieldAlert,
  ExternalLink,
  User,
  Stethoscope,
  Gauge,
} from 'lucide-react';
import { TimelineEvent } from '../types';
import { formatDateTime, formatDoctor } from '../utils/formatters';
import { SpeedometerGauge } from './spacetime/SpeedometerGauge';
import { TimelineScrubber } from './spacetime/TimelineScrubber';
import { MapPolyline } from './spacetime/MapPolyline';
import { MapBoundsFitter } from './spacetime/MapBoundsFitter';

interface SpacetimeMapProps {
  timeline: TimelineEvent[];
  claimId: string;
  onOpenDocument?: (docId?: string) => void;
  apiKey?: string;
  mapId?: string;
}

export interface TransitLeg {
  index: number;
  fromEvent: TimelineEvent;
  toEvent: TimelineEvent;
  distanceKm: number;
  availableMinutes: number;
  availableHours: number;
  requiredHours: number;
  speedKmH: number;
  isImpossible: boolean;
  fromCity: string;
  toCity: string;
}

// Deterministic Haversine Great-Circle Distance (matching backend/tools/geo.py)
function calculateHaversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  if (lat1 === lat2 && lon1 === lon2) return 0;
  if ((lat1 === 0 && lon1 === 0) || (lat2 === 0 && lon2 === 0)) return 0;

  const R = 6371.0;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

// Deterministic Minimum Travel Hours (matching backend/tools/geo.py)
function calculateMinTravelHours(km: number): number {
  if (km <= 0) return 0;
  if (km <= 300) {
    return Math.round((km / 80.0) * 100) / 100;
  }
  return Math.round((2.5 + km / 700.0) * 100) / 100;
}

export const SpacetimeMap: React.FC<SpacetimeMapProps> = ({
  timeline,
  claimId: _claimId,
  onOpenDocument,
  apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '',
  mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID',
}) => {
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);

  // Compute transit legs between consecutive chronological events
  const legs: TransitLeg[] = useMemo(() => {
    if (!timeline || timeline.length < 2) return [];

    const computedLegs: TransitLeg[] = [];
    for (let i = 1; i < timeline.length; i++) {
      const from = timeline[i - 1];
      const to = timeline[i];

      const distanceKm = calculateHaversineKm(from.lat, from.lng, to.lat, to.lng);
      const fromTime = new Date(from.ts).getTime();
      const toTime = new Date(to.ts).getTime();
      const diffMs = Math.max(1000, toTime - fromTime);
      const availableMinutes = Math.round(diffMs / (1000 * 60));
      const availableHours = diffMs / (1000 * 3600);
      const speedKmH = Math.round((distanceKm / (availableHours || 0.01)) * 10) / 10;
      const requiredHours = calculateMinTravelHours(distanceKm);
      const isImpossible = availableHours < requiredHours;

      computedLegs.push({
        index: i,
        fromEvent: from,
        toEvent: to,
        distanceKm,
        availableMinutes,
        availableHours: Math.round(availableHours * 10) / 10,
        requiredHours,
        speedKmH,
        isImpossible,
        fromCity: from.place.split(',')[0].trim(),
        toCity: to.place.split(',')[0].trim(),
      });
    }

    return computedLegs;
  }, [timeline]);

  // Selected leg corresponds to arrival leg for current stop (index > 0)
  const activeLeg = useMemo(() => {
    if (currentIndex === 0) return null;
    return legs.find((l) => l.index === currentIndex) || null;
  }, [currentIndex, legs]);

  // Handle animation timer during play
  useEffect(() => {
    if (!isPlaying) return;

    const intervalMs = Math.max(800, 3000 / playbackSpeed);
    const timer = setInterval(() => {
      setCurrentIndex((prev) => {
        if (prev >= timeline.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, intervalMs);

    return () => clearInterval(timer);
  }, [isPlaying, playbackSpeed, timeline.length]);

  const hasImpossibleLeg = legs.some((l) => l.isImpossible);

  // If no API key configured, display clear fail-loud message
  if (!apiKey) {
    return (
      <div className="bg-surface/80 border border-white/8 rounded-[20px] p-8 text-center space-y-4 backdrop-blur-md">
        <ShieldAlert className="w-10 h-10 text-rose-400 mx-auto" />
        <h3 className="text-base font-bold text-text-primary">
          Google Maps API Key Required
        </h3>
        <p className="text-xs text-text-secondary max-w-md mx-auto leading-relaxed">
          The vector spacetime trajectory engine requires a valid Google Maps API Key. Please set{' '}
          <code className="text-rose-400 font-mono font-bold">
            VITE_GOOGLE_MAPS_API_KEY
          </code>{' '}
          in <code className="font-mono text-amber-primary">frontend/.env.local</code>.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-amber-primary/20 rounded-[20px] shadow-2xs overflow-hidden space-y-0 backdrop-blur-md">
      {/* Top Banner Alert if Impossible Travel is detected */}
      {hasImpossibleLeg && (
        <div className="bg-rose-50 dark:bg-rose-950/40 border-b border-rose-200 dark:border-rose-900/50 border-l-4 border-l-rose-600 dark:border-l-rose-500 p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-rose-100 dark:bg-rose-500/20 border border-rose-300 dark:border-rose-500/30 flex items-center justify-center text-rose-700 dark:text-rose-400 shrink-0">
              <ShieldAlert className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h4 className="text-xs sm:text-sm font-bold text-rose-950 dark:text-rose-100">
                Critical Spacetime Trajectory Violation Detected
              </h4>
              <p className="text-xs text-rose-900/85 dark:text-rose-200/90 leading-relaxed">
                Attending physician logged admitting patients in distant locations within transit times that violate basic physics.
              </p>
            </div>
          </div>
          <span className="text-[10px] sm:text-xs font-mono font-bold px-2.5 py-1 rounded-full bg-rose-100 dark:bg-rose-500/20 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-500/30 self-start sm:self-auto">
            SPACETIME ANOMALY
          </span>
        </div>
      )}

      {/* Main Grid: Google Map (8 cols) + Physics Gauge & Timeline (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-0 divide-y lg:divide-y-0 lg:divide-x divide-white/8">
        {/* Left Column: Real Google Map Container (8 cols) - framed in black card with amber-tinted border */}
        <div className="lg:col-span-8 flex flex-col h-[700px] relative">
          <APIProvider apiKey={apiKey}>
            <Map
              mapId={mapId}
              defaultCenter={{ lat: 23.5937, lng: 78.9629 }}
              defaultZoom={5}
              gestureHandling="greedy"
              disableDefaultUI={false}
              className="w-full h-full"
            >
              <MapBoundsFitter events={timeline} />

              {/* Render Polylines for each transit leg */}
              {legs.map((leg) => {
                const isSelectedLeg = activeLeg?.index === leg.index;
                const path = [
                  { lat: leg.fromEvent.lat, lng: leg.fromEvent.lng },
                  { lat: leg.toEvent.lat, lng: leg.toEvent.lng },
                ];

                return (
                  <MapPolyline
                    key={leg.index}
                    path={path}
                    strokeColor={leg.isImpossible ? '#ef4444' : '#F5A524'}
                    strokeOpacity={isSelectedLeg ? 1.0 : 0.75}
                    strokeWeight={leg.isImpossible ? 4.5 : isSelectedLeg ? 4 : 2.5}
                    geodesic={true}
                  />
                );
              })}

              {/* Render Advanced Markers for each Event */}
              {timeline.map((ev, i) => {
                const isSelected = currentIndex === i;
                const isCurrentStop = currentIndex === i;
                const isDoctor = ev.actor.startsWith('DOC-');

                return (
                  <AdvancedMarker
                    key={i}
                    position={{ lat: ev.lat, lng: ev.lng }}
                    onClick={() => {
                      setCurrentIndex(i);
                      setIsPlaying(false);
                    }}
                    title={`${ev.place} (${formatDateTime(ev.ts)})`}
                  >
                    <Pin
                      background={isCurrentStop ? '#F5A524' : isDoctor ? '#B8741A' : '#78716C'}
                      borderColor="#ffffff"
                      glyphColor="#ffffff"
                      scale={isSelected ? 1.3 : 1.0}
                    >
                      <span className="text-[10px] font-bold font-mono text-white">#{i + 1}</span>
                    </Pin>
                  </AdvancedMarker>
                );
              })}
            </Map>
          </APIProvider>

          {/* Floating Timeline Scrubber at bottom of Map */}
          <div className="absolute bottom-4 left-4 right-4 z-10">
            <TimelineScrubber
              events={timeline}
              currentIndex={currentIndex}
              onSelectIndex={(idx) => {
                setCurrentIndex(idx);
                setIsPlaying(false);
              }}
              isPlaying={isPlaying}
              onTogglePlay={() => setIsPlaying((p) => !p)}
              playbackSpeed={playbackSpeed}
              onChangeSpeed={setPlaybackSpeed}
              onReset={() => {
                setCurrentIndex(0);
                setIsPlaying(false);
              }}
            />
          </div>
        </div>

        {/* Right Column: Physics Readout & Stop Log (4 cols) */}
        <div className="lg:col-span-4 p-5 space-y-5 overflow-y-auto max-h-[700px] bg-surface/50">
          {/* Active Arriving Leg Speedometer / Gauge */}
          {activeLeg ? (
            <SpeedometerGauge
              speedKmH={activeLeg.speedKmH}
              distanceKm={activeLeg.distanceKm}
              availableMinutes={activeLeg.availableMinutes}
              requiredHours={activeLeg.requiredHours}
              isImpossible={activeLeg.isImpossible}
              fromCity={activeLeg.fromCity}
              toCity={activeLeg.toCity}
            />
          ) : (
            <div className="bg-surface-elevated/70 border border-white/8 rounded-[20px] p-5 shadow-2xs space-y-3">
              <div className="flex items-center justify-between border-b border-white/8 pb-3">
                <div className="flex items-center gap-2">
                  <Gauge className="w-4 h-4 text-amber-primary" />
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-text-primary">
                    Spacetime Physics & Velocity Gauge
                  </h3>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
                  Origin Node
                </span>
              </div>
              <div className="p-4 rounded-xl bg-amber-primary/5 border border-amber-primary/20 text-center space-y-1">
                <div className="text-xs font-bold text-text-primary">
                  Departure Origin: {timeline[0]?.place || 'Stop #1'}
                </div>
                <p className="text-[11px] text-text-secondary">
                  First chronological event recorded in trajectory. No inbound transit leg.
                </p>
              </div>
            </div>
          )}

          {/* Chronological Event Cards */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-white/8 pb-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-muted">
                Spacetime Event Logs ({timeline.length})
              </h4>
              <span className="text-[10px] font-mono text-muted">
                Chronological Trail
              </span>
            </div>

            <div className="space-y-2.5">
              {timeline.map((ev, i) => {
                const isSelected = currentIndex === i;
                const isDoctor = ev.actor.startsWith('DOC-');
                const matchingLeg = legs.find((l) => l.index === i);

                return (
                  <div
                    key={i}
                    className={`w-full text-left p-3 rounded-xl border transition-all space-y-2 ${
                      isSelected
                        ? 'bg-amber-primary/10 border-amber-primary/50 shadow-2xs ring-1 ring-amber-primary/40'
                        : 'bg-app-surface-elevated border-app-default hover:border-amber-primary/30'
                    }`}
                  >
                    <div
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        setCurrentIndex(i);
                        setIsPlaying(false);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setCurrentIndex(i);
                          setIsPlaying(false);
                        }
                      }}
                      className="cursor-pointer space-y-1.5 focus:outline-none focus-visible:ring-1 focus-visible:ring-amber-primary rounded-lg select-none"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-start gap-1.5 min-w-0 flex-1">
                          <span
                            className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold font-mono text-black shrink-0 mt-0.5 ${
                              isSelected ? 'bg-amber-primary font-bold' : 'bg-app-muted/40 text-app-primary'
                            }`}
                          >
                            {i + 1}
                          </span>
                          <span className="text-xs font-bold text-app-primary break-words">
                            {ev.place}
                          </span>
                        </div>

                        {matchingLeg?.isImpossible && (
                          <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-rose-500/10 text-rose-700 dark:text-rose-400 border border-rose-500/25 shrink-0 whitespace-nowrap">
                            IMPOSSIBLE
                          </span>
                        )}
                      </div>

                      <div className="text-[11px] text-app-secondary flex items-center justify-between">
                        <span className="flex items-center gap-1">
                          {isDoctor ? (
                            <Stethoscope className="w-3 h-3 text-amber-bright" />
                          ) : (
                            <User className="w-3 h-3 text-amber-primary" />
                          )}
                          <span>{isDoctor ? formatDoctor(ev.actor) : ev.actor}</span>
                        </span>
                        <span className="font-mono text-[10px] text-app-muted">{formatDateTime(ev.ts)}</span>
                      </div>

                      <p className="text-[11px] text-app-secondary leading-relaxed break-words">
                        {ev.description}
                      </p>
                    </div>

                    {ev.doc_id && onOpenDocument && (
                      <div className="pt-1.5 flex justify-end border-t border-app-default/50">
                        <button
                          type="button"
                          onClick={() => onOpenDocument(ev.doc_id)}
                          className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-primary hover:text-amber-bright hover:underline cursor-pointer"
                        >
                          <span>Inspect Linked Claim ({ev.doc_id})</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
