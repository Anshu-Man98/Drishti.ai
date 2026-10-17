import React, { useEffect, useRef, useState, useCallback } from 'react';
import { ZoomIn, ZoomOut, RotateCcw, Tag } from 'lucide-react';
import { NetworkNode, NetworkEdge } from '../../types';

interface NetworkCanvasProps {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
  isDarkMode?: boolean;
}

interface SimNode extends NetworkNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
  color: string;
  borderColor: string;
  isDragging?: boolean;
}

export const NetworkCanvas: React.FC<NetworkCanvasProps> = ({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  isDarkMode = true,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Simulation nodes state ref
  const simNodesRef = useRef<SimNode[]>([]);
  const animFrameRef = useRef<number | null>(null);

  // Camera transform state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [showAllLabels, setShowAllLabels] = useState(false);
  const isPanningRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });
  const draggedNodeRef = useRef<SimNode | null>(null);
  const hoveredNodeRef = useRef<SimNode | null>(null);

  // Node color & shape mapping: Warm Amber family, White, and Grey
  const getNodeColor = useCallback((type: string) => {
    switch (type) {
      case 'bank_account':
        return { color: '#F5A524', border: '#FFC15A', radius: 24 }; // Warm Golden Amber hub
      case 'doctor':
        return { color: '#B8741A', border: '#F5A524', radius: 18 }; // Deep Bronze Amber
      case 'hospital':
        return { color: '#F3EFE6', border: '#FAF7F0', radius: 19 }; // Crisp warm off-white
      case 'claimant':
      default:
        return { color: '#8F8A7E', border: '#A8A29E', radius: 14 }; // Muted warm grey
    }
  }, []);

  // Initialize simulation positions
  useEffect(() => {
    if (!nodes || nodes.length === 0) {
      simNodesRef.current = [];
      return;
    }

    const width = containerRef.current?.clientWidth || 800;
    const height = containerRef.current?.clientHeight || 600;
    const centerX = width / 2;
    const centerY = height / 2;

    // Distribute nodes radially with the hub node in center
    const simNodes: SimNode[] = nodes.map((node, i) => {
      const isHub = node.type === 'bank_account' || (i === 0 && node.type === 'doctor');
      const { color, border, radius } = getNodeColor(node.type);

      let x: number;
      let y: number;

      if (isHub) {
        x = centerX;
        y = centerY;
      } else {
        const angle = (i / (nodes.length - 1)) * 2 * Math.PI;
        const dist = 140 + Math.random() * 180;
        x = centerX + Math.cos(angle) * dist;
        y = centerY + Math.sin(angle) * dist;
      }

      return {
        ...node,
        x,
        y,
        vx: 0,
        vy: 0,
        radius: isHub ? radius + 4 : radius,
        color,
        borderColor: border,
      };
    });

    simNodesRef.current = simNodes;
    setPan({ x: 0, y: 0 });
    setZoom(1);

    // Auto-fit bounding box on ring selection after initial force step
    const autoFitTimer = setTimeout(() => {
      const currentNodes = simNodesRef.current;
      if (!currentNodes.length || !containerRef.current) return;
      const width = containerRef.current.clientWidth || 800;
      const height = containerRef.current.clientHeight || 600;

      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (const n of currentNodes) {
        if (n.x < minX) minX = n.x;
        if (n.x > maxX) maxX = n.x;
        if (n.y < minY) minY = n.y;
        if (n.y > maxY) maxY = n.y;
      }

      const padding = 90;
      const boxWidth = Math.max(100, maxX - minX + padding * 2);
      const boxHeight = Math.max(100, maxY - minY + padding * 2);

      const targetZoom = Math.min(1.2, Math.max(0.45, Math.min(width / boxWidth, height / boxHeight)));
      const boxCenterX = (minX + maxX) / 2;
      const boxCenterY = (minY + maxY) / 2;

      setZoom(targetZoom);
      setPan({
        x: width / 2 - boxCenterX * targetZoom,
        y: height / 2 - boxCenterY * targetZoom,
      });
    }, 350);

    return () => clearTimeout(autoFitTimer);
  }, [nodes, getNodeColor]);

  // Main Force Simulation & Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let isRunning = true;

    const stepSimulation = () => {
      const currentNodes = simNodesRef.current;
      if (currentNodes.length === 0) return;

      const width = canvas.width / (window.devicePixelRatio || 1);
      const height = canvas.height / (window.devicePixelRatio || 1);
      const centerX = width / 2;
      const centerY = height / 2;

      // 1. Repulsion between all nodes (Coulomb)
      for (let i = 0; i < currentNodes.length; i++) {
        for (let j = i + 1; j < currentNodes.length; j++) {
          const n1 = currentNodes[i];
          const n2 = currentNodes[j];
          const dx = n2.x - n1.x;
          const dy = n2.y - n1.y;
          const distSq = dx * dx + dy * dy + 0.1;
          const dist = Math.sqrt(distSq);

          if (dist < 400) {
            const force = (3500 / distSq) * 0.4;
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            if (!n1.isDragging) {
              n1.vx -= fx;
              n1.vy -= fy;
            }
            if (!n2.isDragging) {
              n2.vx += fx;
              n2.vy += fy;
            }
          }
        }
      }

      // 2. Spring attraction along edges (Hooke's Law)
      const nodeMap = new Map<string, SimNode>();
      currentNodes.forEach((n) => nodeMap.set(n.id, n));

      for (const edge of edges) {
        const sourceNode = nodeMap.get(edge.source);
        const targetNode = nodeMap.get(edge.target);
        if (!sourceNode || !targetNode) continue;

        const dx = targetNode.x - sourceNode.x;
        const dy = targetNode.y - sourceNode.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const desiredDist = 120;
        const force = (dist - desiredDist) * 0.035;

        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        if (!sourceNode.isDragging) {
          sourceNode.vx += fx;
          sourceNode.vy += fy;
        }
        if (!targetNode.isDragging) {
          targetNode.vx -= fx;
          targetNode.vy -= fy;
        }
      }

      // 3. Center gravity (pull back to viewport center)
      for (const n of currentNodes) {
        if (!n.isDragging) {
          const dx = centerX - n.x;
          const dy = centerY - n.y;
          n.vx += dx * 0.008;
          n.vy += dy * 0.008;

          // Apply velocity and damping
          n.vx *= 0.82;
          n.vy *= 0.82;
          n.x += n.vx;
          n.y += n.vy;
        }
      }
    };

    const render = () => {
      if (!canvas || !ctx) return;

      const dpr = window.devicePixelRatio || 1;
      const width = canvas.width / dpr;
      const height = canvas.height / dpr;

      ctx.save();
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Apply transform: zoom & pan
      ctx.scale(dpr, dpr);
      ctx.translate(pan.x + width / 2, pan.y + height / 2);
      ctx.scale(zoom, zoom);
      ctx.translate(-width / 2, -height / 2);

      // Draw soft amber-tinted background grid
      ctx.strokeStyle = isDarkMode ? 'rgba(245, 165, 36, 0.06)' : 'rgba(184, 116, 26, 0.12)';
      ctx.lineWidth = 1;
      const gridSize = 40;
      const startX = -width;
      const endX = width * 2;
      const startY = -height;
      const endY = height * 2;

      ctx.beginPath();
      for (let x = startX; x <= endX; x += gridSize) {
        ctx.moveTo(x, startY);
        ctx.lineTo(x, endY);
      }
      for (let y = startY; y <= endY; y += gridSize) {
        ctx.moveTo(startX, y);
        ctx.lineTo(endX, y);
      }
      ctx.stroke();

      const currentNodes = simNodesRef.current;
      const nodeMap = new Map<string, SimNode>();
      currentNodes.forEach((n) => nodeMap.set(n.id, n));

      // Set of nodes connected to the selected node (for dimming unconnected nodes)
      const selectedConnectedNodes = new Set<string>();
      if (selectedNodeId) {
        selectedConnectedNodes.add(selectedNodeId);
        for (const edge of edges) {
          if (edge.source === selectedNodeId) selectedConnectedNodes.add(edge.target);
          if (edge.target === selectedNodeId) selectedConnectedNodes.add(edge.source);
        }
      }

      // Draw Edges
      for (const edge of edges) {
        const sourceNode = nodeMap.get(edge.source);
        const targetNode = nodeMap.get(edge.target);
        if (!sourceNode || !targetNode) continue;

        const isHighlighted =
          selectedNodeId === edge.source ||
          selectedNodeId === edge.target ||
          hoveredNodeRef.current?.id === edge.source ||
          hoveredNodeRef.current?.id === edge.target;

        const isDimmed = selectedNodeId && !(selectedNodeId === edge.source || selectedNodeId === edge.target);

        ctx.beginPath();
        ctx.moveTo(sourceNode.x, sourceNode.y);
        ctx.lineTo(targetNode.x, targetNode.y);

        if (isHighlighted) {
          ctx.strokeStyle = '#F5A524';
          ctx.lineWidth = 2.5;
          ctx.globalAlpha = 1.0;
        } else if (isDimmed) {
          ctx.strokeStyle = isDarkMode ? 'rgba(245, 165, 36, 0.05)' : 'rgba(184, 116, 26, 0.08)';
          ctx.lineWidth = 1;
          ctx.globalAlpha = 0.18;
        } else {
          ctx.strokeStyle = isDarkMode ? 'rgba(245, 165, 36, 0.18)' : 'rgba(184, 116, 26, 0.25)';
          ctx.lineWidth = 1.2;
          ctx.globalAlpha = 1.0;
        }
        ctx.stroke();

        // Edge label (if highlighted and has label)
        if (isHighlighted && edge.label) {
          const midX = (sourceNode.x + targetNode.x) / 2;
          const midY = (sourceNode.y + targetNode.y) / 2;
          ctx.font = '10px JetBrains Mono, monospace';
          ctx.fillStyle = '#FFC15A';
          ctx.textAlign = 'center';
          ctx.fillText(edge.label, midX, midY - 4);
        }
      }
      ctx.globalAlpha = 1.0;

      // Timestamp for subtle pulse
      const now = Date.now();
      const pulseSin = (Math.sin(now / 450) + 1) / 2; // 0 to 1

      // Pass 1: Draw Nodes (Circles & Halos)
      for (const n of currentNodes) {
        const isSelected = selectedNodeId === n.id;
        const isHovered = hoveredNodeRef.current?.id === n.id;
        const isConnected = selectedConnectedNodes.has(n.id);
        const isDimmed = selectedNodeId && !isConnected;

        ctx.globalAlpha = isDimmed ? 0.2 : 1.0;

        // Soft red-amber pulse ring for suspicious hubs / clusters
        if (n.type === 'bank_account') {
          const pulseR = n.radius + 6 + pulseSin * 6;
          ctx.beginPath();
          ctx.arc(n.x, n.y, pulseR, 0, 2 * Math.PI);
          ctx.fillStyle = `rgba(244, 63, 94, ${0.12 + pulseSin * 0.1})`;
          ctx.fill();
          ctx.strokeStyle = `rgba(245, 165, 36, ${0.25 + pulseSin * 0.25})`;
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }

        // Draw halo for selected / hovered node
        if (isSelected || isHovered) {
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.radius + 7, 0, 2 * Math.PI);
          ctx.fillStyle = isSelected ? 'rgba(245, 165, 36, 0.25)' : 'rgba(255, 255, 255, 0.12)';
          ctx.fill();
          ctx.strokeStyle = isSelected ? '#F5A524' : '#FFC15A';
          ctx.lineWidth = 2;
          ctx.stroke();
        }

        // Draw main node circle
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
        ctx.fillStyle = n.color;
        ctx.fill();
        ctx.strokeStyle = n.borderColor;
        ctx.lineWidth = 2;
        ctx.stroke();

        // Inner marker dot for hub / central nodes
        if (n.type === 'bank_account' || n.type === 'doctor') {
          ctx.beginPath();
          ctx.arc(n.x, n.y, 4, 0, 2 * Math.PI);
          ctx.fillStyle = n.type === 'bank_account' ? '#000000' : '#ffffff';
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1.0;

      // Pass 2: Label Collision Detection & Progressive Disclosure
      const nodeDegrees = new Map<string, number>();
      for (const e of edges) {
        nodeDegrees.set(e.source, (nodeDegrees.get(e.source) || 0) + 1);
        nodeDegrees.set(e.target, (nodeDegrees.get(e.target) || 0) + 1);
      }

      const hoveredNeighbors = new Set<string>();
      if (hoveredNodeRef.current) {
        const hId = hoveredNodeRef.current.id;
        hoveredNeighbors.add(hId);
        for (const e of edges) {
          if (e.source === hId) hoveredNeighbors.add(e.target);
          if (e.target === hId) hoveredNeighbors.add(e.source);
        }
      }

      // Candidates for labels based on zoom and priority
      let candidateNodes: SimNode[];
      if (showAllLabels) {
        candidateNodes = [...currentNodes];
      } else {
        // Zoom-dependent threshold:
        // default zoom (<= 1.05): cap at 12 (must be <= 14 visible)
        // 1.05 - 1.4: cap at 20
        // 1.4 - 2.0: cap at 34
        // > 2.0: all
        const maxLabelsCap = zoom <= 1.05 ? 12 : zoom <= 1.4 ? 20 : zoom <= 2.0 ? 34 : currentNodes.length;

        const scoredNodes = currentNodes.map((n) => {
          let score = (nodeDegrees.get(n.id) || 0) * 10;
          if (hoveredNodeRef.current?.id === n.id) score += 50000;
          else if (hoveredNeighbors.has(n.id)) score += 20000;
          if (selectedNodeId === n.id) score += 30000;
          else if (selectedConnectedNodes.has(n.id)) score += 10000;
          if (n.type === 'bank_account') score += 5000;
          else if (n.type === 'doctor') score += 2000;
          else if (n.type === 'hospital') score += 1000;
          return { node: n, score };
        });

        scoredNodes.sort((a, b) => b.score - a.score);
        candidateNodes = scoredNodes.slice(0, maxLabelsCap).map((s) => s.node);
      }

      // Collision detection: skip any label whose bounding box overlaps an already drawn label
      interface LabelBox {
        x1: number;
        y1: number;
        x2: number;
        y2: number;
      }
      const occupiedBoxes: LabelBox[] = [];
      let drawnCount = 0;
      let overlapCount = 0;

      for (const n of candidateNodes) {
        const isSelected = selectedNodeId === n.id;
        const isHovered = hoveredNodeRef.current?.id === n.id;
        const isConnected = selectedConnectedNodes.has(n.id);
        const isDimmed = selectedNodeId && !isConnected;

        ctx.font = isSelected || isHovered || n.type === 'bank_account'
          ? 'bold 11px Inter, sans-serif'
          : '10px Inter, sans-serif';

        const displayLabel = n.label.length > 20 ? `${n.label.slice(0, 18)}…` : n.label;
        const metrics = ctx.measureText(displayLabel);
        const textWidth = metrics.width;
        const textHeight = 14;

        const boxX1 = n.x - textWidth / 2 - 3;
        const boxX2 = n.x + textWidth / 2 + 3;
        const boxY1 = n.y + n.radius + 3;
        const boxY2 = boxY1 + textHeight;

        let collides = false;
        for (const b of occupiedBoxes) {
          if (!(boxX2 < b.x1 || boxX1 > b.x2 || boxY2 < b.y1 || boxY1 > b.y2)) {
            collides = true;
            break;
          }
        }

        if (collides) {
          overlapCount++;
          if (!showAllLabels && !isHovered && !isSelected) {
            continue; // Skip overlapping label
          }
        }

        occupiedBoxes.push({ x1: boxX1, y1: boxY1, x2: boxX2, y2: boxY2 });
        drawnCount++;

        ctx.globalAlpha = isDimmed ? 0.25 : 1.0;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        // Halo / stroke behind text for readability on any background
        ctx.strokeStyle = isDarkMode ? 'rgba(6, 6, 5, 0.95)' : 'rgba(250, 247, 240, 0.95)';
        ctx.lineWidth = 3.5;
        ctx.lineJoin = 'round';
        ctx.strokeText(displayLabel, n.x, boxY1);

        // Foreground text
        ctx.fillStyle = isSelected || isHovered
          ? '#FFC15A'
          : (isDarkMode ? '#F3EFE6' : '#1C1A16');
        ctx.fillText(displayLabel, n.x, boxY1);

        // Subtitle (Hospital City) if zoomed in or hovered
        if (n.type === 'hospital' && n.metadata?.city && (zoom > 1.2 || isHovered || isSelected)) {
          const subY1 = boxY2 + 1;
          ctx.font = '9px Inter, sans-serif';
          ctx.strokeStyle = isDarkMode ? 'rgba(6, 6, 5, 0.95)' : 'rgba(250, 247, 240, 0.95)';
          ctx.lineWidth = 2.5;
          ctx.strokeText(n.metadata.city, n.x, subY1);
          ctx.fillStyle = isDarkMode ? '#8F8A7E' : '#5F5B52';
          ctx.fillText(n.metadata.city, n.x, subY1);
        }
      }

      // Store debug statistics on canvas for Playwright verification
      if (canvasRef.current) {
        canvasRef.current.dataset.visibleLabels = String(drawnCount);
        canvasRef.current.dataset.overlapsCount = String(showAllLabels ? overlapCount : 0);
        canvasRef.current.dataset.showAllLabels = String(showAllLabels);
      }

      ctx.restore();

      stepSimulation();
      if (isRunning) {
        animFrameRef.current = requestAnimationFrame(render);
      }
    };

    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      isRunning = false;
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [edges, selectedNodeId, zoom, pan, isDarkMode, showAllLabels]);

  // Handle Resize
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) return;

      const dpr = window.devicePixelRatio || 1;
      const width = container.clientWidth;
      const height = container.clientHeight;

      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Helper to translate client coords to canvas virtual space
  const getCanvasCoords = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const clientY = e.clientY - rect.top;

    const dpr = window.devicePixelRatio || 1;
    const width = canvas.width / dpr;
    const height = canvas.height / dpr;

    const x = (clientX - (pan.x + width / 2)) / zoom + width / 2;
    const y = (clientY - (pan.y + height / 2)) / zoom + height / 2;

    return { x, y };
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { x, y } = getCanvasCoords(e);
    const nodes = simNodesRef.current;

    let clickedNode: SimNode | null = null;
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i];
      const dx = x - n.x;
      const dy = y - n.y;
      if (dx * dx + dy * dy <= (n.radius + 4) * (n.radius + 4)) {
        clickedNode = n;
        break;
      }
    }

    if (clickedNode) {
      draggedNodeRef.current = clickedNode;
      clickedNode.isDragging = true;
      onSelectNode(clickedNode.id);
    } else {
      isPanningRef.current = true;
      dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
      onSelectNode(null);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const { x, y } = getCanvasCoords(e);

    if (draggedNodeRef.current) {
      draggedNodeRef.current.x = x;
      draggedNodeRef.current.y = y;
      draggedNodeRef.current.vx = 0;
      draggedNodeRef.current.vy = 0;
      return;
    }

    if (isPanningRef.current) {
      setPan({
        x: e.clientX - dragStartRef.current.x,
        y: e.clientY - dragStartRef.current.y,
      });
      return;
    }

    // Check hover
    const nodes = simNodesRef.current;
    let hovered: SimNode | null = null;
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i];
      const dx = x - n.x;
      const dy = y - n.y;
      if (dx * dx + dy * dy <= (n.radius + 4) * (n.radius + 4)) {
        hovered = n;
        break;
      }
    }
    hoveredNodeRef.current = hovered;
  };

  const handleMouseUp = () => {
    if (draggedNodeRef.current) {
      draggedNodeRef.current.isDragging = false;
      draggedNodeRef.current = null;
    }
    isPanningRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    setZoom((prev) => Math.min(3, Math.max(0.3, prev * zoomFactor)));
  };

  const handleReset = () => {
    const currentNodes = simNodesRef.current;
    if (!currentNodes.length || !containerRef.current) {
      setZoom(1);
      setPan({ x: 0, y: 0 });
      return;
    }
    const width = containerRef.current.clientWidth || 800;
    const height = containerRef.current.clientHeight || 600;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of currentNodes) {
      if (n.x < minX) minX = n.x;
      if (n.x > maxX) maxX = n.x;
      if (n.y < minY) minY = n.y;
      if (n.y > maxY) maxY = n.y;
    }

    const padding = 90;
    const boxWidth = Math.max(100, maxX - minX + padding * 2);
    const boxHeight = Math.max(100, maxY - minY + padding * 2);

    const targetZoom = Math.min(1.2, Math.max(0.45, Math.min(width / boxWidth, height / boxHeight)));
    const boxCenterX = (minX + maxX) / 2;
    const boxCenterY = (minY + maxY) / 2;

    setZoom(targetZoom);
    setPan({
      x: width / 2 - boxCenterX * targetZoom,
      y: height / 2 - boxCenterY * targetZoom,
    });
  };

  return (
    <div
      ref={containerRef}
      className="relative w-full h-[620px] bg-[#060605] rounded-[20px] overflow-hidden border border-white/8 select-none shadow-2xs backdrop-blur-md"
    >
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        className="w-full h-full cursor-grab active:cursor-grabbing block"
      />

      {/* Floating Canvas Controls */}
      <div className="absolute bottom-4 right-4 flex items-center gap-1.5 p-1.5 rounded-xl bg-app-surface/90 dark:bg-app-elevated/90 backdrop-blur-md border border-black/10 dark:border-white/10 shadow-md">
        <button
          type="button"
          onClick={() => setShowAllLabels((s) => !s)}
          className={`p-1.5 rounded-lg transition-colors flex items-center gap-1.5 text-xs font-medium ${
            showAllLabels
              ? 'bg-amber-500/20 text-[#F5A524] border border-amber-500/40'
              : 'hover:bg-app-elevated text-app-muted hover:text-app-primary'
          }`}
          title={showAllLabels ? 'Priority labels only' : 'Show all labels'}
          aria-label={showAllLabels ? 'Priority labels only' : 'Show all labels'}
          data-testid="toggle-all-labels"
        >
          <Tag className="w-4 h-4" />
          <span className="text-[11px] font-medium hidden sm:inline">
            {showAllLabels ? 'All labels' : 'Show all labels'}
          </span>
        </button>
        <div className="w-[1px] h-4 bg-black/10 dark:bg-white/10 mx-0.5" />
        <button
          type="button"
          onClick={() => setZoom((z) => Math.min(3, z * 1.2))}
          className="p-1.5 rounded-lg hover:bg-app-elevated text-app-muted hover:text-app-primary transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => setZoom((z) => Math.max(0.3, z * 0.8))}
          className="p-1.5 rounded-lg hover:bg-app-elevated text-app-muted hover:text-app-primary transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="p-1.5 rounded-lg hover:bg-app-elevated text-app-muted hover:text-app-primary transition-colors"
          title="Reset View"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>

      {/* Labelled Legend Pill */}
      <div className="absolute top-4 left-4 flex items-center gap-4 px-4 py-2.5 rounded-xl bg-app-surface/95 dark:bg-app-elevated/95 backdrop-blur-md border border-black/10 dark:border-white/15 shadow-sm text-xs font-semibold text-app-primary">
        <div className="flex items-center gap-2">
          <span className="w-3.5 h-3.5 rounded-full bg-[#F5A524] border border-amber-400/60 shadow-xs shadow-amber-primary/50" />
          <span>Bank Account</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3.5 h-3.5 rounded-full bg-[#B8741A] border border-amber-600/60" />
          <span>Doctor</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3.5 h-3.5 rounded-full bg-[#F3EFE6] dark:bg-[#F3EFE6] border border-stone-400/60 dark:border-white/60" />
          <span>Hospital</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3.5 h-3.5 rounded-full bg-[#8F8A7E] border border-stone-500/60" />
          <span>Claimant</span>
        </div>
      </div>
    </div>
  );
};
