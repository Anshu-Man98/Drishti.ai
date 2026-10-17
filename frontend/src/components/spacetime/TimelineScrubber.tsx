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
    <div
      aria-label="Trajectory replay controls"
      className="bg-app-elevated border border-app-default rounded-[20px] p-4 shadow-2xl space-y-3 backdrop-blur-md"
      style={{
        backgroundColor: 'var(--bg-elevated)',
      }}
      data-testid="timeline-scrubber-panel"
    >
      {/* Top Bar: Playback Controls & Timestamp Display */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        {/* Play / Pause / Reset / Speed Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onTogglePlay}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-amber-primary hover:bg-amber-bright text-black font-semibold text-xs transition-all shadow-md shadow-amber-primary/20"
            title={isPlaying ? 'Pause Replay (Space)' : 'Play Trajectory Replay (Space)'}
            aria-label={isPlaying ? 'Pause Replay' : 'Play Trajectory Replay'}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-black" />}
            <span>{isPlaying ? 'Pause' : 'Replay'}</span>
          </button>

          <button
            type="button"
            onClick={onReset}
            className="p-1.5 rounded-xl bg-app-surface hover:bg-app-elevated border border-app-default text-app-muted hover:text-app-primary transition-colors"
            title="Reset to Stop #1 (Home)"
            aria-label="Reset to Stop #1"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          {/* Speed Selectors (1x, 2x, 5x) */}
          <div className="flex items-center bg-app-surface p-0.5 rounded-xl border border-app-default text-xs font-mono">
            {[1, 2, 5].map((spd) => (
              <button
                key={spd}
                type="button"
                onClick={() => onChangeSpeed(spd)}
                className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                  playbackSpeed === spd
                    ? 'bg-amber-primary text-black shadow-xs font-bold'
                    : 'text-app-muted hover:text-app-primary'
                }`}
                title={`Playback speed ${spd}x`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>

        {/* Current Simulated Event Display */}
        {currentEvent && (
          <div className="flex items-center gap-3 text-xs flex-wrap">
            <span
              data-testid="scrubber-stop-badge"
              className="px-2.5 py-0.5 rounded-full bg-amber-500/15 dark:bg-amber-500/20 text-[#B8741A] dark:text-[#FFC15A] font-mono font-bold border border-amber-500/30"
            >
              Stop #{currentIndex + 1} of {events.length}
            </span>
            <span
              data-testid="scrubber-timestamp"
              className="font-mono text-app-primary font-semibold"
            >
              {formatDateTime(currentEvent.ts)}
            </span>
            <span
              data-testid="scrubber-place"
              className="text-app-secondary font-medium truncate max-w-[220px]"
              title={currentEvent.place}
            >
              {currentEvent.place}
            </span>
          </div>
        )}
      </div>

      {/* Discrete Timeline Scrubber Rail */}
      <div
        className="relative pt-2 pb-1 focus:outline-none focus:ring-1 focus:ring-amber-primary/50 rounded-lg cursor-pointer"
        role="slider"
        tabIndex={0}
        aria-label="Timeline position"
        aria-valuemin={1}
        aria-valuemax={events.length}
        aria-valuenow={currentIndex + 1}
        aria-valuetext={`Stop ${currentIndex + 1} of ${events.length}: ${currentEvent?.place || ''}`}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault();
            if (currentIndex > 0) onSelectIndex(currentIndex - 1);
          } else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault();
            if (currentIndex < events.length - 1) onSelectIndex(currentIndex + 1);
          } else if (e.key === 'Home') {
            e.preventDefault();
            onReset();
          } else if (e.key === 'End') {
            e.preventDefault();
            onSelectIndex(events.length - 1);
          }
        }}
      >
        {/* Progress Fill Bar */}
        <div className="relative w-full h-2 bg-black/15 dark:bg-white/15 rounded-full overflow-hidden border border-app-default">
          <div
            className="h-full bg-amber-primary transition-all duration-300"
            style={{
              width: `${events.length > 1 ? (currentIndex / (events.length - 1)) * 100 : 0}%`,
            }}
          />
        </div>

        {/* Individual Stop Dots */}
        <div className="flex items-center justify-between absolute top-1.5 left-0 right-0 px-0.5">
          {events.map((ev, idx) => {
            const isReached = idx <= currentIndex;
            const isCurrent = idx === currentIndex;

            return (
              <button
                key={idx}
                type="button"
                onClick={() => onSelectIndex(idx)}
                className={`w-4 h-4 rounded-full border-2 transition-all transform -translate-y-1 focus:outline-none focus:ring-2 focus:ring-amber-primary ${
                  isCurrent
                    ? 'bg-[#F5A524] border-white dark:border-black scale-125 shadow-md shadow-amber-primary/50'
                    : isReached
                    ? 'bg-[#F5A524] border-app-surface'
                    : 'bg-app-surface border-app-strong hover:border-amber-primary/60'
                }`}
                title={`Stop #${idx + 1}: ${ev?.place || ''} (${formatDateTime(ev?.ts)})`}
                aria-label={`Jump to Stop #${idx + 1}: ${ev?.place || ''}`}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
};
