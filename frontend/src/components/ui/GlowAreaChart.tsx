import React, { useId, useState, useRef } from 'react';
import clsx from 'clsx';
import { useMotionProgress } from '../../utils/motion';

export interface DataPoint {
  label: string;
  value: number;
  formattedValue?: string;
  sublabel?: string;
}

export interface GlowAreaChartProps {
  data: DataPoint[];
  title?: string;
  selector?: React.ReactNode;
  height?: number;
  className?: string;
  valuePrefix?: string;
  valueSuffix?: string;
  emptyMessage?: string;
  animate?: boolean;
}

/**
 * GlowAreaChart - The signature Nexa-style "Attack Trend" glowing line and area chart.
 * Features:
 * - Glowing warm golden-amber stroke (#F5A524)
 * - Faded vertical gradient area fill fading into black canvas
 * - Interactive hover crosshair and sleek floating dark tooltip
 * - Minimalist axes with tabular values
 * - Draw-in animation on initial render (respects prefers-reduced-motion)
 * - Clear empty state when data has zero or insufficient points
 */
export const GlowAreaChart: React.FC<GlowAreaChartProps> = ({
  data,
  title,
  selector,
  height = 180,
  className,
  valuePrefix = '',
  valueSuffix = '',
  emptyMessage = 'No trend data available for this range',
  animate = true,
}) => {
  const gradientId = useId();
  const filterId = useId();
  const svgRef = useRef<SVGSVGElement | null>(null);

  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const progress = useMotionProgress({ duration: 900, enabled: animate });

  if (!data || data.length === 0) {
    return (
      <div className={clsx('flex flex-col h-full', className)}>
        {title && (
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold tracking-wide text-app-primary">{title}</h3>
            {selector}
          </div>
        )}
        <div
          role="status"
          aria-label={emptyMessage}
          className="flex-1 flex flex-col items-center justify-center p-8 rounded-xl border border-white/[0.06] bg-white/[0.02] text-app-muted text-xs text-center"
        >
          <div className="w-8 h-8 rounded-full border border-white/10 flex items-center justify-center mb-2 text-app-muted/60">
            ~
          </div>
          <p>{emptyMessage}</p>
        </div>
      </div>
    );
  }

  // Chart Dimensions
  const padding = { top: 16, right: 16, bottom: 28, left: 16 };
  const viewBoxWidth = 600;
  const viewBoxHeight = height;

  const chartWidth = viewBoxWidth - padding.left - padding.right;
  const chartHeight = viewBoxHeight - padding.top - padding.bottom;

  const values = data.map((d) => d.value);
  const minVal = Math.min(...values);
  const maxVal = Math.max(...values);
  const valRange = maxVal - minVal === 0 ? 1 : maxVal - minVal;

  const points = data.map((d, i) => {
    const x = padding.left + (i / Math.max(1, data.length - 1)) * chartWidth;
    const y = padding.top + chartHeight - ((d.value - minVal) / valRange) * chartHeight;
    return { x, y, data: d };
  });

  // Construct SVG Path
  const linePathD = points.reduce((acc, p, i) => {
    return i === 0 ? `M ${p.x.toFixed(1)} ${p.y.toFixed(1)}` : `${acc} L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
  }, '');

  const areaPathD = `
    ${linePathD}
    L ${points[points.length - 1].x.toFixed(1)} ${padding.top + chartHeight}
    L ${points[0].x.toFixed(1)} ${padding.top + chartHeight}
    Z
  `;

  let estimatedLength = 0;
  for (let i = 1; i < points.length; i++) {
    const dx = points[i].x - points[i - 1].x;
    const dy = points[i].y - points[i - 1].y;
    estimatedLength += Math.sqrt(dx * dx + dy * dy);
  }
  estimatedLength = Math.max(10, estimatedLength);

  const strokeDashoffset = animate ? estimatedLength * (1 - progress) : 0;
  const areaOpacity = animate ? progress : 1;

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const relativeX = e.clientX - rect.left;
    const svgX = (relativeX / rect.width) * viewBoxWidth;

    // Find closest point
    let closestIdx = 0;
    let minDistance = Infinity;
    points.forEach((p, idx) => {
      const dist = Math.abs(p.x - svgX);
      if (dist < minDistance) {
        minDistance = dist;
        closestIdx = idx;
      }
    });

    setHoverIndex(closestIdx);
  };

  const activePoint = hoverIndex !== null ? points[hoverIndex] : null;

  return (
    <div className={clsx('flex flex-col select-none relative', className)}>
      {/* Chart Header */}
      {(title || selector) && (
        <div className="flex items-center justify-between mb-3 px-1">
          {title && <h3 className="text-sm font-semibold tracking-wide text-app-primary">{title}</h3>}
          {selector && <div className="text-xs">{selector}</div>}
        </div>
      )}

      {/* SVG Container */}
      <div className="relative w-full overflow-hidden">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${viewBoxWidth} ${viewBoxHeight}`}
          className="w-full h-auto overflow-visible cursor-crosshair"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoverIndex(null)}
          role="img"
          aria-label={title ? `${title} Chart` : 'Trend line chart'}
        >
          <defs>
            {/* Area Gradient: amber at top, fades to 0% at bottom */}
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#F5A524" stopOpacity="0.28" />
              <stop offset="60%" stopColor="#F5A524" stopOpacity="0.06" />
              <stop offset="100%" stopColor="#F5A524" stopOpacity="0.0" />
            </linearGradient>

            {/* Glowing Stroke Filter */}
            <filter id={filterId} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="glow" />
              <feMerge>
                <feMergeNode in="glow" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Horizontal Baseline / Gridline */}
          <line
            x1={padding.left}
            y1={padding.top + chartHeight}
            x2={viewBoxWidth - padding.right}
            y2={padding.top + chartHeight}
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth="1"
          />

          {/* Area Fill */}
          <path
            d={areaPathD}
            fill={`url(#${gradientId})`}
            style={{ opacity: areaOpacity }}
          />

          {/* Outer Glowing Stroke */}
          <path
            d={linePathD}
            fill="none"
            stroke="#FFC15A"
            strokeWidth="2"
            opacity={0.6 * areaOpacity}
            strokeDasharray={estimatedLength}
            strokeDashoffset={strokeDashoffset}
            filter={`url(#${filterId})`}
          />

          {/* Sharp Core Stroke */}
          <path
            d={linePathD}
            fill="none"
            stroke="#F5A524"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={estimatedLength}
            strokeDashoffset={strokeDashoffset}
          />

          {/* Hover Crosshair & Indicator */}
          {activePoint && (
            <g className="transition-opacity duration-150">
              {/* Vertical Crosshair Line */}
              <line
                x1={activePoint.x}
                y1={padding.top}
                x2={activePoint.x}
                y2={padding.top + chartHeight}
                stroke="rgba(245, 165, 36, 0.35)"
                strokeWidth="1"
                strokeDasharray="3 3"
              />

              {/* Glowing Outer Dot */}
              <circle
                cx={activePoint.x}
                cy={activePoint.y}
                r="7"
                fill="rgba(14, 14, 13, 0.9)"
                stroke="#FFC15A"
                strokeWidth="2"
              />

              {/* Inner Dot */}
              <circle
                cx={activePoint.x}
                cy={activePoint.y}
                r="3"
                fill="#FFC15A"
              />
            </g>
          )}

          {/* X-Axis Tick Labels (First, Mid, Last) */}
          {points.length > 0 && (
            <g className="fill-app-muted text-[10px] font-mono select-none">
              <text x={points[0].x} y={viewBoxHeight - 6} textAnchor="start">
                {points[0].data.label}
              </text>
              {points.length > 2 && (
                <text
                  x={points[Math.floor(points.length / 2)].x}
                  y={viewBoxHeight - 6}
                  textAnchor="middle"
                >
                  {points[Math.floor(points.length / 2)].data.label}
                </text>
              )}
              <text x={points[points.length - 1].x} y={viewBoxHeight - 6} textAnchor="end">
                {points[points.length - 1].data.label}
              </text>
            </g>
          )}
        </svg>

        {/* Floating Tooltip Box */}
        {activePoint && (
          <div
            className="absolute pointer-events-none z-20 px-3 py-1.5 rounded-lg bg-[#141413]/95 border border-amber-primary/30 shadow-lg -translate-x-1/2 -translate-y-full text-xs font-mono"
            style={{
              left: `${(activePoint.x / viewBoxWidth) * 100}%`,
              top: `${(activePoint.y / viewBoxHeight) * 100 - 10}%`,
            }}
          >
            <div className="text-amber-primary font-bold">
              {valuePrefix}
              {activePoint.data.formattedValue || activePoint.data.value.toLocaleString()}
              {valueSuffix}
            </div>
            <div className="text-[10px] text-app-muted">{activePoint.data.label}</div>
          </div>
        )}
      </div>
    </div>
  );
};
