import React from 'react';
import { Gauge, ShieldAlert, Plane, Car } from 'lucide-react';

interface SpeedometerGaugeProps {
  speedKmH: number;
  distanceKm: number;
  availableMinutes: number;
  requiredHours: number;
  isImpossible: boolean;
  fromCity: string;
  toCity: string;
}

export const SpeedometerGauge: React.FC<SpeedometerGaugeProps> = ({
  speedKmH,
  distanceKm,
  availableMinutes,
  requiredHours,
  isImpossible,
  fromCity,
  toCity,
}) => {
  // Max speed on gauge: 1500 km/h
  const maxSpeed = 1500;
  const clampedSpeed = Math.min(maxSpeed, Math.max(0, speedKmH));

  // Needle / Sweep angle: from -120 deg (0 km/h) to +120 deg (1500 km/h) -> 240 deg range
  const angle = -120 + (clampedSpeed / maxSpeed) * 240;

  const isAirFeasible = clampedSpeed > 120 && clampedSpeed <= 800 && !isImpossible;

  return (
    <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 shadow-2xs backdrop-blur-md space-y-4">
      <div className="flex items-center justify-between border-b border-white/8 pb-3">
        <div className="flex items-center gap-2">
          <Gauge className="w-4 h-4 text-amber-primary" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-primary">
            Spacetime Physics & Velocity Gauge
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary border border-amber-primary/25">
          Haversine Geodesic
        </span>
      </div>

      {/* Arriving Transit Leg Banner */}
      <div
        className={`p-2.5 rounded-xl border text-xs font-mono font-medium flex items-center justify-between flex-wrap gap-1 ${
          isImpossible
            ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            : 'bg-surface-elevated/70 border-white/8 text-text-primary'
        }`}
      >
        <span>Leg: {fromCity} → {toCity}</span>
        <span className="font-bold text-amber-primary">Required speed: {Math.round(speedKmH).toLocaleString()} km/h</span>
      </div>

      {/* Analog Arc Dial (Nexa Style with inner tick marks & glowing end-dot) */}
      <div className="flex flex-col items-center justify-center pt-2">
        <div className="relative w-64 h-40 flex items-center justify-center">
          <svg className="w-full h-full overflow-visible" viewBox="0 0 220 140">
            <defs>
              <linearGradient id="speedometerGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#10b981" />
                <stop offset="45%" stopColor="#F5A524" />
                <stop offset="75%" stopColor="#FFC15A" />
                <stop offset="100%" stopColor="#ef4444" />
              </linearGradient>
              <linearGradient id="speedometerDangerGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#ef4444" />
                <stop offset="100%" stopColor="#b91c1c" />
              </linearGradient>
              <filter id="gaugeDotGlow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor={isImpossible ? '#ef4444' : '#FFC15A'} floodOpacity="0.8" />
              </filter>
            </defs>

            {/* Background Track Arc */}
            <path
              d="M 30 120 A 80 80 0 1 1 190 120"
              fill="none"
              stroke="rgba(255, 255, 255, 0.08)"
              strokeWidth="10"
              strokeLinecap="round"
            />

            {/* Colored Dynamic Arc */}
            <path
              d="M 30 120 A 80 80 0 1 1 190 120"
              fill="none"
              stroke={isImpossible ? 'url(#speedometerDangerGradient)' : 'url(#speedometerGradient)'}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray="360"
              strokeDashoffset={Math.max(0, 360 - (clampedSpeed / maxSpeed) * 360)}
              className="transition-all duration-700 ease-out"
            />

            {/* Radial Inner Ticks */}
            {[0, 20, 40, 60, 80, 100].map((pct) => {
              const tickAngle = (-120 + (pct / 100) * 240) * (Math.PI / 180);
              const r1 = 66;
              const r2 = 72;
              const x1 = 110 + r1 * Math.sin(tickAngle);
              const y1 = 120 - r1 * Math.cos(tickAngle);
              const x2 = 110 + r2 * Math.sin(tickAngle);
              const y2 = 120 - r2 * Math.cos(tickAngle);
              return (
                <line
                  key={pct}
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke="rgba(255, 255, 255, 0.2)"
                  strokeWidth="1.5"
                />
              );
            })}

            {/* Speed Reference Mark Labels */}
            <text x="24" y="134" className="text-[9px] fill-muted font-mono" textAnchor="middle">
              0
            </text>
            <text x="50" y="62" className="text-[9px] fill-emerald-400 font-mono" textAnchor="middle">
              120
            </text>
            <text x="156" y="42" className="text-[9px] fill-amber-primary font-mono" textAnchor="middle">
              800
            </text>
            <text x="196" y="134" className="text-[9px] fill-rose-400 font-mono" textAnchor="middle">
              1500
            </text>

            {/* Needle Pivot & Indicator Line */}
            <g transform="translate(110, 120)">
              <line
                x1="0"
                y1="0"
                x2="0"
                y2="-70"
                stroke={isImpossible ? '#ef4444' : isAirFeasible ? '#FFC15A' : '#10b981'}
                strokeWidth="3.5"
                strokeLinecap="round"
                transform={`rotate(${angle})`}
                className="transition-transform duration-500 ease-out"
                filter="url(#gaugeDotGlow)"
              />
              <circle cx="0" cy="0" r="7" fill="#0E0E0D" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
              <circle
                cx="0"
                cy="0"
                r="3.5"
                fill={isImpossible ? '#ef4444' : isAirFeasible ? '#FFC15A' : '#10b981'}
              />
            </g>
          </svg>

          {/* Large Digital Speed Readout */}
          <div className="absolute bottom-1 text-center">
            <span
              className={`text-2xl font-black font-mono tracking-tight tabular-nums ${
                isImpossible
                  ? 'text-rose-400'
                  : isAirFeasible
                  ? 'text-amber-primary'
                  : 'text-emerald-400'
              }`}
            >
              {Math.round(clampedSpeed).toLocaleString()}
            </span>
            <span className="text-[11px] text-muted font-mono ml-1 font-semibold">km/h</span>
          </div>
        </div>

        {/* Speedometer Zone Subtitle */}
        <div className="mt-2 text-center">
          {isImpossible ? (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-bold animate-pulse">
              <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
              <span>IMPOSSIBLE VELOCITY ({Math.round(clampedSpeed)} km/h)</span>
            </div>
          ) : isAirFeasible ? (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-primary/10 border border-amber-primary/30 text-amber-primary text-xs font-semibold">
              <Plane className="w-3.5 h-3.5 text-amber-primary" />
              <span>Commercial Air Feasible ({Math.round(clampedSpeed)} km/h)</span>
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
              <Car className="w-3.5 h-3.5 text-emerald-400" />
              <span>Road Transit Feasible ({Math.round(clampedSpeed)} km/h)</span>
            </div>
          )}
        </div>
      </div>

      {/* Physics Breakdown Table */}
      <div className="grid grid-cols-2 gap-2 text-xs pt-1">
        <div className="p-3 rounded-xl bg-surface-elevated/70 border border-white/8">
          <span className="text-[10px] uppercase text-muted block font-semibold">
            Geodesic Distance
          </span>
          <span className="font-mono font-bold text-text-primary tabular-nums">
            {distanceKm.toLocaleString()} km
          </span>
          <p className="text-[10px] text-muted mt-0.5 truncate">
            {fromCity} → {toCity}
          </p>
        </div>

        <div className="p-3 rounded-xl bg-surface-elevated/70 border border-white/8">
          <span className="text-[10px] uppercase text-muted block font-semibold">
            Reported Transit Window
          </span>
          <span className="font-mono font-bold text-text-primary tabular-nums">
            {availableMinutes} min ({Math.round((availableMinutes / 60) * 10) / 10} h)
          </span>
          <p className="text-[10px] text-muted mt-0.5">
            Min required: {Math.round(requiredHours * 10) / 10} h
          </p>
        </div>
      </div>

      {/* Physics Explanation Formula */}
      <div className="p-3.5 rounded-xl bg-surface-elevated/50 border border-white/6 text-[11px] text-text-secondary space-y-1">
        <div className="flex items-center justify-between font-mono text-[10px] text-muted">
          <span>Formula: v = d / Δt</span>
          <span>Earth R = 6,371 km</span>
        </div>
        <p className="leading-relaxed">
          {isImpossible
            ? `Door-to-door transit between ${fromCity} and ${toCity} requires at least ${Math.round(
                requiredHours * 10
              ) / 10} hours including check-in and runway taxiing. Patient was admitted within only ${availableMinutes} minutes.`
            : `Transit time of ${availableMinutes} minutes between ${fromCity} and ${toCity} is within physical travel boundaries.`}
        </p>
      </div>
    </div>
  );
};
