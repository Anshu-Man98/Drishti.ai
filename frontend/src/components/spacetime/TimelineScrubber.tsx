import React from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';
import { TimelineEvent } from '../../types';
import { formatDateTime } from '../../utils/formatters';

interface TimelineScrubberProps {
  events: TimelineEvent[];
  currentIndex: number;
  onSelectIndex: (idx: number) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  playbackSpeed: number;
  onChangeSpeed: (speed: number) => void;
  onReset: () => void;
}

export const TimelineScrubber: React.FC<TimelineScrubberProps> = ({
  events,
  currentIndex,
  onSelectIndex,
  isPlaying,
  onTogglePlay,
  playbackSpeed,
  onChangeSpeed,
  onReset,
}) => {
  const currentEvent = events[currentIndex] || events[0];

  return (
    <div className="bg-surface/90 backdrop-blur-md border border-white/10 rounded-[20px] p-4 shadow-xl space-y-3">
      {/* Top Bar: Playback Controls & Timestamp Display */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        {/* Play / Pause / Reset / Speed Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onTogglePlay}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-primary hover:bg-amber-bright text-black font-semibold text-xs transition-all shadow-md shadow-amber-primary/20"
            title={isPlaying ? 'Pause Replay' : 'Play Trajectory Replay'}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-black" />}
            <span>{isPlaying ? 'Pause' : 'Replay'}</span>
          </button>

          <button
            type="button"
            onClick={onReset}
            className="p-1.5 rounded-xl bg-surface-elevated hover:bg-surface border border-white/10 text-muted hover:text-text-primary transition-colors"
            title="Reset to Stop #1"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          {/* Speed Selectors (1x, 2x, 5x) */}
          <div className="flex items-center bg-surface-elevated p-0.5 rounded-xl border border-white/10 text-xs font-mono">
            {[1, 2, 5].map((spd) => (
              <button
                key={spd}
                type="button"
                onClick={() => onChangeSpeed(spd)}
                className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                  playbackSpeed === spd
                    ? 'bg-amber-primary text-black shadow-xs'
                    : 'text-muted hover:text-text-primary'
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>

        {/* Current Simulated Event Display */}
        {currentEvent && (
          <div className="flex items-center gap-3 text-xs">
            <span className="px-2.5 py-0.5 rounded-full bg-amber-primary/10 text-amber-primary font-mono font-bold border border-amber-primary/25">
              Stop #{currentIndex + 1} of {events.length}
            </span>
            <span className="font-mono text-text-primary font-medium">
              {formatDateTime(currentEvent.ts)}
            </span>
            <span className="text-text-secondary truncate max-w-[200px]" title={currentEvent.place}>
              {currentEvent.place}
            </span>
          </div>
        )}
      </div>

      {/* Discrete Timeline Scrubber Rail */}
      <div className="relative pt-2 pb-1">
        {/* Progress Fill Bar */}
        <div className="relative w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-amber-primary transition-all duration-300"
            style={{
              width: `${events.length > 1 ? (currentIndex / (events.length - 1)) * 100 : 0}%`,
            }}
          />
        </div>

        {/* Individual Stop Dots */}
        <div className="flex items-center justify-between absolute top-1 left-0 right-0 px-0.5">
          {events.map((_, idx) => {
            const isReached = idx <= currentIndex;
            const isCurrent = idx === currentIndex;

            return (
              <button
                key={idx}
                type="button"
                onClick={() => onSelectIndex(idx)}
                className={`w-3.5 h-3.5 rounded-full border-2 transition-all transform -translate-y-0.5 ${
                  isCurrent
                    ? 'bg-amber-primary border-amber-bright scale-125 shadow-md shadow-amber-primary/50'
                    : isReached
                    ? 'bg-amber-primary border-surface'
                    : 'bg-surface-elevated border-white/20 hover:border-amber-primary/40'
                }`}
                title={`Jump to Stop #${idx + 1}`}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};
