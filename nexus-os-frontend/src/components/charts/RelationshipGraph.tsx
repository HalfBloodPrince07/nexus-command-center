"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { ChartPayload, GraphNode } from "@/types/journal";

interface RelationshipGraphProps {
  data: ChartPayload;
  onNodeClick?: (node: GraphNode) => void;
  className?: string;
  height?: number;
}

/**
 * 2D force-directed relationship graph.
 * Maps ChartPayload nodes/edges to the format expected by react-force-graph-2d.
 */
export default function RelationshipGraph({
  data,
  onNodeClick,
  className,
  height = 420,
}: RelationshipGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height });

  // Observe container width so the graph stays responsive
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        if (width > 0) {
          setDimensions({ width, height });
        }
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, [height]);

  // Build graph data from ChartPayload
  const graphData = {
    nodes: (data.nodes ?? []).map((n) => ({
      id: n.id,
      label: n.label,
      color: n.color ?? "#6366F1",
      size: n.size ?? 6,
      category: n.category,
      metadata: n.metadata,
    })),
    links: (data.edges ?? []).map((e) => ({
      source: e.source,
      target: e.target,
      label: e.label,
      color: e.color ?? "rgba(99,102,241,0.25)",
    })),
  };

  // Custom node rendering for labels + sized circles
  const paintNode = useCallback(
    (node: Record<string, unknown>, ctx: CanvasRenderingContext2D) => {
      const x = node.x as number;
      const y = node.y as number;
      const size = (node.size as number) ?? 6;
      const color = (node.color as string) ?? "#6366F1";
      const label = (node.label as string) ?? "";

      // Glow
      ctx.shadowColor = color;
      ctx.shadowBlur = 8;

      // Circle
      ctx.beginPath();
      ctx.arc(x, y, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      // Reset shadow
      ctx.shadowColor = "transparent";
      ctx.shadowBlur = 0;

      // Label
      if (label) {
        ctx.font = `${Math.max(3, size * 0.7)}px sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillStyle = "rgba(228,228,231,0.85)";
        ctx.fillText(label, x, y + size + 2);
      }
    },
    [],
  );

  const handleNodeClick = useCallback(
    (node: Record<string, unknown>) => {
      if (!onNodeClick) return;
      // Reconstruct GraphNode from the force-graph node object
      onNodeClick({
        id: node.id as string,
        label: node.label as string,
        size: node.size as number | undefined,
        color: node.color as string | undefined,
        category: node.category as string | undefined,
        metadata: node.metadata as Record<string, unknown> | undefined,
      });
    },
    [onNodeClick],
  );

  if (!data.nodes?.length) {
    return (
      <div
        className={`flex items-center justify-center text-ink-muted text-sm ${className ?? ""}`}
        style={{ height }}
      >
        No relationship data available yet.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={className}
      style={{ height, position: "relative", overflow: "hidden" }}
    >
      <ForceGraph2D
        width={dimensions.width}
        height={dimensions.height}
        graphData={graphData}
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={(node, color, ctx) => {
          const size = (node as Record<string, unknown>).size as number ?? 6;
          ctx.beginPath();
          ctx.arc(
            (node as Record<string, unknown>).x as number,
            (node as Record<string, unknown>).y as number,
            size + 2,
            0,
            2 * Math.PI,
          );
          ctx.fillStyle = color;
          ctx.fill();
        }}
        onNodeClick={handleNodeClick}
        linkColor={(link) => (link as Record<string, unknown>).color as string}
        linkWidth={1.5}
        backgroundColor="transparent"
        cooldownTicks={60}
      />
    </div>
  );
}
