"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { ChartPayload } from "@/types/journal";

interface MoodLineChartProps {
  data: ChartPayload;
  className?: string;
}

/** Custom tooltip styled to match the glass design system. */
function MoodTooltip({
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
        Mood: <span style={{ color: "#6366F1" }}>{payload[0].value}</span>
      </p>
    </div>
  );
}

export default function MoodLineChart({ data, className }: MoodLineChartProps) {
  const points = data.series?.[0]?.data ?? [];

  if (points.length === 0) {
    return (
      <div className={`flex items-center justify-center text-ink-muted text-sm ${className ?? ""}`}>
        No mood data available yet.
      </div>
    );
  }

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
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
            domain={[0, 10]}
            tick={{ fontSize: 11, fill: "var(--text-secondary, #a1a1aa)" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<MoodTooltip />} />

          {/* Neutral mood reference line */}
          <ReferenceLine
            y={6}
            stroke="#6366F1"
            strokeOpacity={0.3}
            strokeDasharray="4 4"
            label={{
              value: "Neutral",
              position: "insideTopRight",
              fill: "#6366F1",
              fontSize: 10,
              opacity: 0.6,
            }}
          />

          <Line
            type="monotone"
            dataKey="y"
            stroke="#6366F1"
            strokeWidth={2.5}
            dot={{ r: 3, fill: "#6366F1", strokeWidth: 0 }}
            activeDot={{
              r: 5,
              fill: "#6366F1",
              stroke: "rgba(99,102,241,0.3)",
              strokeWidth: 6,
            }}
            animationDuration={800}
            animationEasing="ease-out"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
