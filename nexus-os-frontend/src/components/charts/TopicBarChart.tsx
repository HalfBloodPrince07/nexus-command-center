"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { ChartPayload } from "@/types/journal";

interface TopicBarChartProps {
  data: ChartPayload;
  className?: string;
}

/** Custom tooltip styled to match the glass design system. */
function TopicTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass-elevated rounded-xl px-3 py-2 text-xs shadow-glass">
      <p className="text-ink-secondary">{label}</p>
      <p className="font-semibold text-ink">
        Count: <span style={{ color: "#34D399" }}>{payload[0].value}</span>
      </p>
    </div>
  );
}

export default function TopicBarChart({ data, className }: TopicBarChartProps) {
  const series = data.series?.[0];
  const points = series?.data ?? [];

  if (points.length === 0) {
    return (
      <div className={`flex items-center justify-center text-ink-muted text-sm ${className ?? ""}`}>
        No topic data available yet.
      </div>
    );
  }

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={points}
          margin={{ top: 8, right: 12, left: -8, bottom: 4 }}
        >
          <CartesianGrid
            strokeDasharray="3 6"
            stroke="var(--glass-border)"
            vertical={false}
          />
          <XAxis
            dataKey="x"
            tick={{ fontSize: 11, fill: "var(--text-secondary, #a1a1aa)" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: "var(--text-secondary, #a1a1aa)" }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip content={<TopicTooltip />} />
          <Bar
            dataKey="y"
            fill="#34D399"
            radius={[6, 6, 0, 0]}
            animationDuration={800}
            animationEasing="ease-out"
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
