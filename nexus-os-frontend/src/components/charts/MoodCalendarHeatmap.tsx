"use client";

import CalendarHeatmap from "react-calendar-heatmap";
import type { ChartPayload } from "@/types/journal";
import "react-calendar-heatmap/dist/styles.css";

interface MoodCalendarHeatmapProps {
  data: ChartPayload;
  year: number;
  className?: string;
}

/**
 * Maps a mood value (1-10) to a Tailwind-compatible CSS class.
 * Values go from red (low mood) through yellow to green (high mood).
 */
function classForValue(value: { date: string; count: number } | null): string {
  if (!value || value.count == null) return "fill-zinc-800/30";

  const v = value.count;
  if (v <= 2) return "fill-red-500";
  if (v <= 3) return "fill-red-400";
  if (v <= 4) return "fill-orange-400";
  if (v <= 5) return "fill-amber-400";
  if (v <= 6) return "fill-yellow-400";
  if (v <= 7) return "fill-lime-400";
  if (v <= 8) return "fill-green-400";
  if (v <= 9) return "fill-emerald-400";
  return "fill-emerald-500";
}

export default function MoodCalendarHeatmap({
  data,
  year,
  className,
}: MoodCalendarHeatmapProps) {
  const rawPoints = data.series?.[0]?.data ?? [];

  // Map the series data to the shape CalendarHeatmap expects
  const values = rawPoints.map((d) => ({
    date: d.date as string,
    count: d.value as number,
  }));

  if (values.length === 0) {
    return (
      <div className={`flex items-center justify-center text-ink-muted text-sm ${className ?? ""}`}>
        No calendar data available for {year}.
      </div>
    );
  }

  return (
    <div className={className}>
      <CalendarHeatmap
        startDate={new Date(`${year}-01-01`)}
        endDate={new Date(`${year}-12-31`)}
        values={values}
        classForValue={classForValue as (value: unknown) => string}
        showWeekdayLabels
        gutterSize={3}
        titleForValue={(value) => {
          if (!value) return "No data";
          const v = value as { date: string; count: number };
          return `${v.date}: mood ${v.count}/10`;
        }}
      />
    </div>
  );
}
