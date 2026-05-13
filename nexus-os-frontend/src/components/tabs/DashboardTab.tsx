"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  LayoutDashboard,
  Heart,
  BarChart3,
  Users,
  TrendingUp,
  Lightbulb,
  GitBranch,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useJournalStore } from "@/stores/useJournalStore";
import MoodLineChart from "@/components/charts/MoodLineChart";
import MoodCalendarHeatmap from "@/components/charts/MoodCalendarHeatmap";
import TopicBarChart from "@/components/charts/TopicBarChart";
import RelationshipGraph from "@/components/charts/RelationshipGraph";
import AgentNetworkPanel from "@/components/three/AgentNetworkPanel";

/* ── Sub-tab definitions ── */

const SUB_TABS = [
  { id: "overview" as const, label: "Overview", icon: LayoutDashboard },
  { id: "mood" as const, label: "Mood Charts", icon: Heart },
  { id: "analytics" as const, label: "Life Analytics", icon: BarChart3 },
  { id: "relationships" as const, label: "Relationships", icon: Users },
  { id: "agent-network" as const, label: "Agent Network", icon: GitBranch },
] as const;

type SubTab = (typeof SUB_TABS)[number]["id"];

/* ── Page transition variants ── */

const panelVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -8 },
};

/* ── DashboardTab ── */

export default function DashboardTab() {
  const [activeTab, setActiveTab] = useState<SubTab>("overview");

  const {
    moodTrend,
    moodCalendar,
    insights,
    relationshipsGraph,
    loadMoodTrend,
    loadMoodCalendar,
    loadInsights,
    loadRelationships,
  } = useJournalStore();

  // Load all dashboard data on mount
  useEffect(() => {
    loadMoodTrend(30);
    loadMoodCalendar();
    loadInsights(30);
    loadRelationships();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentYear = new Date().getFullYear();

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* ── Pill sub-tab bar ── */}
      <div className="flex flex-shrink-0 items-center gap-1 border-b border-border-subtle px-4 pt-3 pb-0">
        {SUB_TABS.map(({ id, label, icon: Icon }) => {
          const active = activeTab === id;
          return (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={cn(
                "relative flex items-center gap-2 rounded-t-xl px-4 py-2.5 text-sm font-medium transition-all",
                active ? "text-accent" : "text-ink-secondary hover:text-ink",
              )}
            >
              <Icon size={15} strokeWidth={1.8} />
              {label}
              {active && (
                <motion.div
                  layoutId="dashboardSubTab"
                  className="absolute inset-x-0 bottom-0 h-[2px] rounded-full bg-gradient-primary"
                  transition={{ type: "spring", stiffness: 400, damping: 35 }}
                />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Tab content ── */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            variants={panelVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="h-full"
          >
            {activeTab === "overview" && (
              <OverviewPanel
                moodTrend={moodTrend}
                insights={insights}
                relationshipsGraph={relationshipsGraph}
              />
            )}
            {activeTab === "mood" && (
              <MoodPanel
                moodTrend={moodTrend}
                moodCalendar={moodCalendar}
                currentYear={currentYear}
              />
            )}
            {activeTab === "analytics" && (
              <AnalyticsPanel insights={insights} />
            )}
            {activeTab === "relationships" && (
              <RelationshipsPanel graph={relationshipsGraph} />
            )}
            {activeTab === "agent-network" && <AgentNetworkPanel />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Overview Panel
   2x2 grid on desktop, stacked on mobile
──────────────────────────────────────────── */

function OverviewPanel({
  moodTrend,
  insights,
  relationshipsGraph,
}: {
  moodTrend: ReturnType<typeof useJournalStore.getState>["moodTrend"];
  insights: ReturnType<typeof useJournalStore.getState>["insights"];
  relationshipsGraph: ReturnType<typeof useJournalStore.getState>["relationshipsGraph"];
}) {
  const topInsights = insights.slice(0, 3);
  const nodeCount = relationshipsGraph?.nodes?.length ?? 0;

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {/* Mood trend (30 days) */}
      <div className="glass rounded-2xl p-5 shadow-glass">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <TrendingUp size={15} className="text-indigo-400" />
          Mood Trend (30d)
        </h3>
        {moodTrend ? (
          <MoodLineChart data={moodTrend} className="h-52" />
        ) : (
          <Skeleton label="Loading mood data..." />
        )}
      </div>

      {/* Top insights */}
      <div className="glass rounded-2xl p-5 shadow-glass">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
          <Lightbulb size={15} className="text-amber-400" />
          Top Insights
        </h3>
        {topInsights.length > 0 ? (
          <ul className="space-y-3">
            {topInsights.map((insight, i) => (
              <li
                key={i}
                className="glass-elevated rounded-xl p-3 text-xs text-ink-secondary"
              >
                <p className="mb-1 font-semibold text-ink">{insight.title}</p>
                <p className="line-clamp-2">{insight.description}</p>
                <div className="mt-1.5 flex items-center gap-3 text-ink-muted">
                  <span>
                    Confidence: {Math.round(insight.confidence * 100)}%
                  </span>
                  <span>Evidence: {insight.evidence_count}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <Skeleton label="No insights yet." />
        )}
      </div>

      {/* Relationships preview */}
      <div className="glass rounded-2xl p-5 shadow-glass md:col-span-2">
        <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-ink">
          <Users size={15} className="text-teal-400" />
          Relationships
        </h3>
        <p className="text-xs text-ink-muted">
          {nodeCount > 0
            ? `${nodeCount} people in your relationship graph`
            : "No relationship data yet."}
        </p>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Mood Panel
   MoodLineChart + MoodCalendarHeatmap side by side
──────────────────────────────────────────── */

function MoodPanel({
  moodTrend,
  moodCalendar,
  currentYear,
}: {
  moodTrend: ReturnType<typeof useJournalStore.getState>["moodTrend"];
  moodCalendar: ReturnType<typeof useJournalStore.getState>["moodCalendar"];
  currentYear: number;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div className="glass rounded-2xl p-5 shadow-glass">
        <h3 className="mb-3 text-sm font-semibold text-ink">
          Mood Over Time
        </h3>
        {moodTrend ? (
          <MoodLineChart data={moodTrend} className="h-64" />
        ) : (
          <Skeleton label="Loading mood trend..." />
        )}
      </div>

      <div className="glass rounded-2xl p-5 shadow-glass">
        <h3 className="mb-3 text-sm font-semibold text-ink">
          Mood Calendar ({currentYear})
        </h3>
        {moodCalendar ? (
          <MoodCalendarHeatmap
            data={moodCalendar}
            year={currentYear}
            className="h-64 [&_svg]:max-h-full"
          />
        ) : (
          <Skeleton label="Loading calendar..." />
        )}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Analytics Panel
   TopicBarChart from psychology patterns
──────────────────────────────────────────── */

function AnalyticsPanel({
  insights,
}: {
  insights: ReturnType<typeof useJournalStore.getState>["insights"];
}) {
  // Build a ChartPayload from insights for the bar chart
  const chartData: import("@/types/journal").ChartPayload = {
    id: "analytics-topics",
    type: "bar",
    title: "Psychology Patterns",
    series: [
      {
        name: "Topics",
        data: insights.map((ins) => ({
          x: ins.title.length > 20 ? ins.title.slice(0, 20) + "..." : ins.title,
          y: ins.evidence_count,
        })),
      },
    ],
  };

  return (
    <div className="glass rounded-2xl p-5 shadow-glass">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
        <BarChart3 size={15} className="text-emerald-400" />
        Psychology Patterns
      </h3>
      {insights.length > 0 ? (
        <TopicBarChart data={chartData} className="h-80" />
      ) : (
        <Skeleton label="No pattern data available yet." />
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────
   Relationships Panel
   Full RelationshipGraph
──────────────────────────────────────────── */

function RelationshipsPanel({
  graph,
}: {
  graph: ReturnType<typeof useJournalStore.getState>["relationshipsGraph"];
}) {
  return (
    <div className="glass rounded-2xl p-5 shadow-glass">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
        <Users size={15} className="text-teal-400" />
        Relationship Map
      </h3>
      {graph ? (
        <RelationshipGraph data={graph} height={500} className="w-full" />
      ) : (
        <Skeleton label="Loading relationship graph..." />
      )}
    </div>
  );
}

/* ─── Shared skeleton placeholder ─── */

function Skeleton({ label }: { label: string }) {
  return (
    <div className="flex h-32 items-center justify-center">
      <p className="text-sm text-ink-muted animate-pulse">{label}</p>
    </div>
  );
}
