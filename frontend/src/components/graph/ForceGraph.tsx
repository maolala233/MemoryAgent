"use client";

/**
 * 纯 SVG 力导向图组件（零外部依赖）：
 *  - 节点：圆形 + 标签
 *  - 边：折线 + 关系文字
 *  - 力：spring（邻居吸引）+ 中心引力 + 库仑排斥
 *  - 交互：节点拖拽、滚轮缩放、空白处平移
 *  - 回调：onNodeClick / onEdgeClick
 *
 * 用法：
 *   <ForceGraph
 *     nodes={[{id, label, color, group}]}
 *     edges={[{source, target, label, color}]}
 *     centerId="..."          // 高亮中心节点
 *     onNodeClick={(n) => ...}
 *     onEdgeClick={(e) => ...}
 *   />
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/shared/Icon";

export interface GraphNode {
  id: string;
  label: string;
  /** 节点颜色（hex）。不传则按 group 分配。 */
  color?: string;
  /** 节点分组（用于颜色与图例）。如 "Entity" / "Document" / "Event" */
  group?: string;
  /** 节点大小（半径），默认 22 */
  size?: number;
}

export interface GraphEdge {
  id?: string;
  source: string;
  target: string;
  label?: string;
  color?: string;
}

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fx?: number;  // 拖拽时固定坐标
  fy?: number;
}

const GROUP_PALETTE: Record<string, string> = {
  entity: "#3b82f6",     // blue
  document: "#10b981",   // green
  event: "#f59e0b",      // amber
  summary: "#a855f7",    // purple
  default: "#6b7280",    // gray
};

function colorFor(n: GraphNode): string {
  if (n.color) return n.color;
  const g = (n.group || "default").toLowerCase();
  return GROUP_PALETTE[g] || GROUP_PALETTE.default;
}

function colorForEdge(e: GraphEdge): string {
  if (e.color) return e.color;
  return "#94a3b8";  // slate-400
}

interface ForceGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  centerId?: string;
  width?: number;
  height?: number;
  onNodeClick?: (n: GraphNode) => void;
  onEdgeClick?: (e: GraphEdge) => void;
}

export function ForceGraph({
  nodes: inputNodes,
  edges: inputEdges,
  centerId,
  width = 900,
  height = 560,
  onNodeClick,
  onEdgeClick,
}: ForceGraphProps) {
  // 视图变换（缩放 / 平移）
  const [view, setView] = useState({ x: 0, y: 0, k: 1 });
  const svgRef = useRef<SVGSVGElement | null>(null);
  const draggingNodeRef = useRef<string | null>(null);
  const panningRef = useRef<{ x: number; y: number } | null>(null);

  // 节点/边索引（id -> node）
  const [tick, setTick] = useState(0);

  // 模拟节点
  const simNodesRef = useRef<SimNode[]>([]);
  // 用 ref 同步最新 props 供每帧读取
  const inputNodesRef = useRef<GraphNode[]>(inputNodes);
  const inputEdgesRef = useRef<GraphEdge[]>(inputEdges);
  const centerIdRef = useRef<string | undefined>(centerId);
  useEffect(() => {
    inputNodesRef.current = inputNodes;
    inputEdgesRef.current = inputEdges;
    centerIdRef.current = centerId;
  }, [inputNodes, inputEdges, centerId]);

  // 重建模拟节点（id 变化时重置位置）
  useEffect(() => {
    const old = new Map(simNodesRef.current.map((n) => [n.id, n]));
    const cx = width / 2;
    const cy = height / 2;
    simNodesRef.current = (inputNodes || []).map((n, i) => {
      const prev = old.get(n.id);
      const safeN = n || { id: `__placeholder_${i}`, label: "", group: "default" };
      const total = Math.max(1, (inputNodes || []).length);
      const angle = (i / total) * Math.PI * 2;
      const startX = prev?.x ?? cx + Math.cos(angle) * 120;
      const startY = prev?.y ?? cy + Math.sin(angle) * 120;
      return {
        ...safeN,
        id: safeN.id,
        x: Number.isFinite(startX) ? startX : cx,
        y: Number.isFinite(startY) ? startY : cy,
        vx: 0,
        vy: 0,
      } as SimNode;
    });
    setTick((t) => t + 1);
  }, [inputNodes, width, height]);

  // 力导布局主循环
  useEffect(() => {
    let raf = 0;
    let alpha = 1.0;
    const tickLoop = () => {
      const nodes = simNodesRef.current;
      if (nodes.length > 0) {
        const cx = width / 2;
        const cy = height / 2;
        // 自适应参数：节点越多 → 排斥力/弹簧距离越大
        const N = nodes.length;
        const restLen = Math.min(220, 130 + Math.sqrt(N) * 8);   // 邻居距离
        const repulse = Math.min(12000, 4500 + N * 60);          // 排斥强度
        // 1) 库仑排斥（所有节点两两）
        for (let i = 0; i < N; i++) {
          for (let j = i + 1; j < N; j++) {
            const a = nodes[i];
            const b = nodes[j];
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            let d2 = dx * dx + dy * dy;
            if (d2 < 1) d2 = 1;
            const d = Math.sqrt(d2);
            const force = repulse / d2;
            const fx = (dx / d) * force;
            const fy = (dy / d) * force;
            a.vx -= fx;
            a.vy -= fy;
            b.vx += fx;
            b.vy += fy;
          }
        }
        // 2) spring（邻居吸引）
        const edges = inputEdgesRef.current;
        const k = 0.035;  // 弹簧刚度（越小越松）
        for (const e of edges) {
          const a = nodes.find((n) => n.id === e.source);
          const b = nodes.find((n) => n.id === e.target);
          if (!a || !b) continue;
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 1;
          const diff = (d - restLen) * k;
          const fx = (dx / d) * diff;
          const fy = (dy / d) * diff;
          a.vx += fx;
          a.vy += fy;
          b.vx -= fx;
          b.vy -= fy;
        }
        // 3) 中心引力
        for (const n of nodes) {
          n.vx += (cx - n.x) * 0.008;
          n.vy += (cy - n.y) * 0.008;
        }
        // 4) 中心节点额外吸引力（更紧凑）— 只在 N 较少时启用，避免大图全堆中间
        if (centerIdRef.current && N <= 30) {
          const c = nodes.find((n) => n.id === centerIdRef.current);
          if (c) {
            for (const n of nodes) {
              if (n === c) continue;
              n.vx += (c.x - n.x) * 0.003;
              n.vy += (c.y - n.y) * 0.003;
            }
          }
        }
        // 5) 阻尼 + 位置更新
        const damping = 0.82;
        for (const n of nodes) {
          if (n.fx != null && n.fy != null) {
            n.x = n.fx;
            n.y = n.fy;
            n.vx = 0;
            n.vy = 0;
            continue;
          }
          n.vx *= damping;
          n.vy *= damping;
          n.x += n.vx;
          n.y += n.vy;
          // 边界
          n.x = Math.max(40, Math.min(width - 40, n.x));
          n.y = Math.max(40, Math.min(height - 40, n.y));
        }
        // alpha 衰减（更快收敛）
        alpha *= 0.985;
      }
      setTick((t) => t + 1);
      raf = requestAnimationFrame(tickLoop);
    };
    raf = requestAnimationFrame(tickLoop);
    return () => cancelAnimationFrame(raf);
  }, [width, height]);

  // 鼠标事件：屏幕坐标 → 视图坐标
  const toView = (clientX: number, clientY: number) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return { x: clientX, y: clientY };
    return {
      x: (clientX - rect.left - view.x) / view.k,
      y: (clientY - rect.top - view.y) / view.k,
    };
  };

  const onMouseDown = (e: React.MouseEvent, n?: SimNode) => {
    if (n) {
      draggingNodeRef.current = n.id;
      n.fx = n.x;
      n.fy = n.y;
    } else {
      panningRef.current = { x: e.clientX - view.x, y: e.clientY - view.y };
    }
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (draggingNodeRef.current) {
      const p = toView(e.clientX, e.clientY);
      const n = simNodesRef.current.find((nn) => nn.id === draggingNodeRef.current);
      if (n) {
        n.fx = p.x;
        n.fy = p.y;
      }
    } else if (panningRef.current) {
      // 先把 pan 状态快照下来，避免 React 调度期间 panningRef.current 被 onMouseUp 置空
      const pan = panningRef.current;
      setView((v) => ({
        ...v,
        x: e.clientX - pan.x,
        y: e.clientY - pan.y,
      }));
    }
  };
  const onMouseUp = () => {
    if (draggingNodeRef.current) {
      const n = simNodesRef.current.find((nn) => nn.id === draggingNodeRef.current);
      if (n) {
        n.fx = undefined;
        n.fy = undefined;
      }
      draggingNodeRef.current = null;
    }
    panningRef.current = null;
  };
  // 滚轮缩放：使用 native non-passive 监听，preventDefault 才能阻止外层页面滚动
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();   // 阻止外层滚动
      e.stopPropagation();
      const rect = el.getBoundingClientRect();
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      setView((v) => {
        const newK = Math.max(0.2, Math.min(4, v.k * delta));
        // 缩放时保持鼠标位置稳定
        const x = px - (px - v.x) * (newK / v.k);
        const y = py - (py - v.y) * (newK / v.k);
        return { k: newK, x, y };
      });
    };
    // {passive: false} 才能 preventDefault
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // 自动 fit-to-view
  const fitView = () => setView({ x: 0, y: 0, k: 1 });
  const zoomIn = () => setView((v) => ({ ...v, k: Math.min(4, v.k * 1.2) }));
  const zoomOut = () => setView((v) => ({ ...v, k: Math.max(0.2, v.k * 0.8) }));

  // 节点点击：放开鼠标时若没移动才触发
  const clickStartRef = useRef<{ x: number; y: number; id: string } | null>(null);
  const onNodeMouseDown = (e: React.MouseEvent, n: SimNode) => {
    e.stopPropagation();
    clickStartRef.current = { x: e.clientX, y: e.clientY, id: n.id };
    onMouseDown(e, n);
  };
  const onNodeMouseUp = (e: React.MouseEvent, n: GraphNode) => {
    e.stopPropagation();
    if (clickStartRef.current && clickStartRef.current.id === n.id) {
      const dx = e.clientX - clickStartRef.current.x;
      const dy = e.clientY - clickStartRef.current.y;
      if (Math.sqrt(dx * dx + dy * dy) < 4) {
        onNodeClick?.(n);
      }
    }
    clickStartRef.current = null;
  };

  // 当前帧用的节点位置（取 ref 快照，触发重渲）
  const renderedNodes = useMemo(() => (simNodesRef.current || []).filter(Boolean), [tick, inputNodes]);

  if (!inputNodes || inputNodes.length === 0) {
    return (
      <div
        className="bg-surface border border-border rounded-xl flex items-center justify-center"
        style={{ height }}
      >
        <div className="text-center text-on-surface-variant">
          <Icon name="hub" className="text-[40px] mx-auto opacity-50" />
          <p className="mt-2 text-body-sm">暂无图谱数据</p>
        </div>
      </div>
    );
  }

  // 节点按 group 收集，用于图例
  const groups = useMemo(() => {
    const set = new Set<string>();
    for (const n of inputNodes) {
      if (n && n.group) set.add(n.group);
    }
    return Array.from(set);
  }, [inputNodes]);

  // 截断标签
  const truncate = (s: string | null | undefined, n: number) => {
    const safe = s == null ? "" : String(s);
    return safe.length > n ? safe.slice(0, n) + "…" : safe;
  };

  // 工具：把屏幕坐标 → 节点坐标（用于找到鼠标下的节点）
  const nodeById = useMemo(() => {
    const m = new Map<string, SimNode>();
    for (const n of renderedNodes) {
      if (n && n.id != null) m.set(String(n.id), n);
    }
    return m;
  }, [renderedNodes, tick]);

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden relative" style={{ height }}>
      {/* 工具栏 */}
      <div className="absolute top-2 right-2 z-10 flex flex-col gap-1 bg-surface/90 border border-border rounded p-1">
        <button
          onClick={zoomIn}
          className="w-7 h-7 rounded hover:bg-surface-container-low text-on-surface flex items-center justify-center"
          title="放大"
        >
          <Icon name="add" className="text-[16px]" />
        </button>
        <button
          onClick={zoomOut}
          className="w-7 h-7 rounded hover:bg-surface-container-low text-on-surface flex items-center justify-center"
          title="缩小"
        >
          <Icon name="remove" className="text-[16px]" />
        </button>
        <button
          onClick={fitView}
          className="w-7 h-7 rounded hover:bg-surface-container-low text-on-surface flex items-center justify-center"
          title="重置视图"
        >
          <Icon name="center_focus_strong" className="text-[16px]" />
        </button>
      </div>
      {/* 图例 */}
      {groups.length > 1 && (
        <div className="absolute top-2 left-2 z-10 bg-surface/90 border border-border rounded px-2 py-1.5 flex flex-wrap gap-2 max-w-[60%]">
          {groups.map((g) => (
            <span key={g} className="inline-flex items-center gap-1 text-label-sm text-on-surface">
              <span
                className="w-2.5 h-2.5 rounded-full"
                style={{ background: GROUP_PALETTE[g] || GROUP_PALETTE.default }}
              />
              {g}
            </span>
          ))}
        </div>
      )}
      {/* 统计 */}
      <div className="absolute bottom-2 left-2 z-10 bg-surface/90 border border-border rounded px-2 py-1 text-label-sm text-on-surface-variant">
        {inputNodes.length} 节点 / {inputEdges.length} 边
      </div>
      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ cursor: panningRef.current ? "grabbing" : "grab", userSelect: "none" }}
        onMouseDown={(e) => onMouseDown(e)}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          {/* 边 */}
          {inputEdges.map((e, i) => {
            const a = e && e.source != null ? nodeById.get(String(e.source)) : undefined;
            const b = e && e.target != null ? nodeById.get(String(e.target)) : undefined;
            if (!a || !b || a == null || b == null) return null;
            const color = colorForEdge(e);
            const ax = Number.isFinite(a.x) ? a.x : width / 2;
            const ay = Number.isFinite(a.y) ? a.y : height / 2;
            const bx = Number.isFinite(b.x) ? b.x : width / 2;
            const by = Number.isFinite(b.y) ? b.y : height / 2;
            const mx = (ax + bx) / 2;
            const my = (ay + by) / 2;
            return (
              <g
                key={e.id || `${e.source}-${e.target}-${i}`}
                style={{ cursor: onEdgeClick ? "pointer" : "default" }}
                onClick={(ev) => {
                  ev.stopPropagation();
                  onEdgeClick?.(e);
                }}
              >
                <line
                  x1={ax}
                  y1={ay}
                  x2={bx}
                  y2={by}
                  stroke={color}
                  strokeWidth={1.4}
                  strokeOpacity={0.7}
                />
                {e.label && view.k > 0.6 && (
                  <g transform={`translate(${mx} ${my})`}>
                    <rect
                      x={-((String(e.label).length * 6) / 2 + 4)}
                      y={-8}
                      width={String(e.label).length * 6 + 8}
                      height={16}
                      rx={4}
                      fill="var(--surface, #fff)"
                      stroke={color}
                      strokeWidth={0.8}
                      opacity={0.95}
                    />
                    <text
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fontSize={10}
                      fill="var(--on-surface, #1f2937)"
                    >
                      {truncate(e.label, 14)}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
          {/* 节点 */}
          {renderedNodes.map((n) => {
            if (!n || n.id == null) return null;
            const r = n.size ?? 22;
            const c = colorFor(n);
            const isCenter = centerId && n.id === centerId;
            const nx = Number.isFinite(n.x) ? n.x : width / 2;
            const ny = Number.isFinite(n.y) ? n.y : height / 2;
            return (
              <g
                key={String(n.id)}
                transform={`translate(${nx} ${ny})`}
                style={{ cursor: "pointer" }}
                onMouseDown={(e) => onNodeMouseDown(e, n)}
                onMouseUp={(e) => onNodeMouseUp(e, n)}
              >
                {isCenter && (
                  <circle r={r + 8} fill={c} fillOpacity={0.18} />
                )}
                <circle
                  r={r}
                  fill={c}
                  fillOpacity={0.85}
                  stroke={isCenter ? "#1f2937" : "#fff"}
                  strokeWidth={isCenter ? 2.5 : 1.5}
                />
                {n.group && (
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize={9}
                    fontWeight="bold"
                    fill="#fff"
                    pointerEvents="none"
                  >
                    {(n.group[0] || "?").toUpperCase()}
                  </text>
                )}
                {view.k > 0.4 && (
                  <g transform={`translate(0 ${r + 12})`}>
                    {/* 标签背景 */}
                    <rect
                      x={-((truncate(n.label, 18).length * 6) / 2 + 4)}
                      y={-8}
                      width={truncate(n.label, 18).length * 6 + 8}
                      height={16}
                      rx={3}
                      fill="var(--surface, #fff)"
                      stroke={c}
                      strokeWidth={0.6}
                      opacity={0.95}
                    />
                    <text
                      textAnchor="middle"
                      dominantBaseline="middle"
                      fontSize={10.5}
                      fill="var(--on-surface, #1f2937)"
                      pointerEvents="none"
                    >
                      {truncate(n.label, 18)}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
