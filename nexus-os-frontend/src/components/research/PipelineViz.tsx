"use client";

import { useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain, Search, Download, Layout, PenLine,
  Layers, ShieldCheck, Archive, FileOutput,
  CheckCircle2, AlertCircle, Clock, Loader2,
  FileText, FileType2, FileDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useResearchStore } from "@/stores/useResearchStore";
import type { PipelineAgentId, PipelineAgentState } from "@/types/research";

// ── Agent config ─────────────────────────────────────────────────────────────

const AGENT_ICONS: Record<PipelineAgentId, React.ElementType> = {
  Atlas:             Brain,
  Vector:            Search,
  Fetch:             Download,
  OutlineArchitect:  Layout,
  SectionDrafter:    PenLine,
  SynthesisDirector: Layers,
  Verity:            ShieldCheck,
  Scribe:            Archive,
  Exporter:          FileOutput,
};

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: PipelineAgentState["status"] }) {
  if (status === "complete") return <CheckCircle2 size={14} className="text-emerald-500" />;
  if (status === "error")    return <AlertCircle  size={14} className="text-red-400" />;
  if (status === "active")   return <Loader2 size={14} className="animate-spin text-indigo-400" />;
  return <Clock size={14} className="text-ink-muted/40" />;
}

function ProgressBar({ value, max, colorClass = "bg-indigo-500" }: {
  value: number; max: number; colorClass?: string;
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] text-ink-muted">{value} / {max}</span>
        <span className="text-[10px] text-ink-muted">{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-surface-secondary overflow-hidden">
        <motion.div
          className={cn("h-full rounded-full", colorClass)}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}

function SectionDrafterDetail() {
  const job = useResearchStore((s) => s.activeJob);
  const sp = job?.sectionProgress;
  if (!sp) return null;
  return (
    <div className="mt-2 space-y-1">
      {sp.currentTitle && (
        <p className="text-[11px] text-indigo-300 truncate" title={sp.currentTitle}>
          Current: <span className="font-medium">"{sp.currentTitle}"</span>
        </p>
      )}
      {sp.total > 0 && (
        <ProgressBar value={sp.done} max={sp.total} colorClass="bg-indigo-500" />
      )}
    </div>
  );
}

function VerityDetail() {
  const job = useResearchStore((s) => s.activeJob);
  const cp = job?.claimProgress;
  if (!cp) return null;
  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex gap-3 text-[10px]">
        <span className="text-emerald-400">✅ {cp.verified} verified</span>
        {cp.hallucinated > 0 && <span className="text-red-400">❌ {cp.hallucinated} hallucinated</span>}
        {cp.unverified > 0  && <span className="text-amber-400">⚠ {cp.unverified} unverified</span>}
      </div>
      {cp.total > 0 && (
        <ProgressBar
          value={cp.verified + cp.hallucinated + cp.unverified}
          max={cp.total}
          colorClass="bg-violet-500"
        />
      )}
    </div>
  );
}

function ExporterComplete() {
  const job = useResearchStore((s) => s.activeJob);
  const paths = job?.outputPaths;
  if (!paths || Object.keys(paths).length === 0) return null;
  const items = [
    { key: "pdf",  label: "PDF",      Icon: FileType2,  color: "text-red-400" },
    { key: "docx", label: "DOCX",     Icon: FileText,   color: "text-blue-400" },
    { key: "md",   label: "Markdown", Icon: FileDown,   color: "text-ink-secondary" },
  ] as const;
  return (
    <div className="mt-2 flex flex-wrap gap-2">
      {items.map(({ key, label, Icon, color }) =>
        (paths as any)[key] ? (
          <span key={key} className={cn("flex items-center gap-1 text-[10px] font-medium", color)}>
            <Icon size={11} />
            {label}
          </span>
        ) : null
      )}
    </div>
  );
}

// ── Agent row ─────────────────────────────────────────────────────────────────

function AgentRow({
  agent,
  isLast,
}: {
  agent: PipelineAgentState;
  isLast: boolean;
}) {
  const Icon = AGENT_ICONS[agent.id] ?? Brain;
  const isActive = agent.status === "active";
  const isDone   = agent.status === "complete";
  const isError  = agent.status === "error";

  return (
    <div className="flex gap-3">
      {/* Timeline spine */}
      <div className="flex flex-col items-center" style={{ minWidth: 28 }}>
        <motion.div
          animate={{
            backgroundColor: isActive ? "rgba(99,102,241,0.2)" : isDone ? "rgba(52,211,153,0.15)" : "transparent",
            boxShadow: isActive ? "0 0 12px rgba(99,102,241,0.4)" : "none",
          }}
          className={cn(
            "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border transition-colors",
            isActive && "border-indigo-400/70 text-indigo-400",
            isDone   && "border-emerald-400/50 text-emerald-400",
            isError  && "border-red-400/50 text-red-400",
            !isActive && !isDone && !isError && "border-border-subtle text-ink-muted/30",
          )}
        >
          <Icon size={13} strokeWidth={1.8} />
        </motion.div>
        {!isLast && (
          <div
            className={cn(
              "mt-1 w-px flex-1 transition-colors duration-700",
              isDone ? "bg-emerald-400/30" : "bg-border-subtle/50",
            )}
            style={{ minHeight: 12 }}
          />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 pb-3 min-w-0">
        <div className="flex items-center gap-2 py-0.5">
          <span className={cn(
            "text-[13px] font-semibold transition-colors",
            isActive ? "text-ink" : isDone ? "text-ink/80" : "text-ink-muted/50",
          )}>
            {agent.label}
          </span>
          <StatusIcon status={agent.status} />
          {agent.badge && (
            <span className={cn(
              "rounded-full px-1.5 py-0.5 text-[9px] font-semibold tracking-wide",
              isDone   ? "bg-emerald-500/15 text-emerald-400" : "bg-indigo-500/15 text-indigo-400",
            )}>
              {agent.badge}
            </span>
          )}
        </div>

        <AnimatePresence>
          {isActive && (
            <motion.div
              key="active-detail"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
              className="overflow-hidden"
            >
              <div className="mt-1 rounded-xl border border-indigo-400/20 bg-indigo-500/5 px-3 py-2">
                {agent.detail && (
                  <p className="text-[11px] text-ink-muted leading-relaxed">{agent.detail}</p>
                )}
                {agent.id === "SectionDrafter"   && <SectionDrafterDetail />}
                {agent.id === "Verity"            && <VerityDetail />}
              </div>
            </motion.div>
          )}
          {isDone && agent.id === "Exporter" && (
            <motion.div
              key="exporter-done"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.3 }}
            >
              <ExporterComplete />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ── Activity log ──────────────────────────────────────────────────────────────

function ActivityLog() {
  const logs = useResearchStore((s) => s.activeJob?.logs ?? []);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs.length]);

  if (logs.length === 0) return null;

  return (
    <div className="mt-3 rounded-xl border border-border-subtle/50 bg-surface-secondary/30 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border-subtle/40">
        <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-pulse" />
        <span className="text-[10px] font-semibold uppercase tracking-widest text-ink-muted">Activity</span>
      </div>
      <div className="max-h-[120px] overflow-y-auto px-3 py-2 space-y-1 scrollbar-thin">
        {logs.map((entry, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.18 }}
            className="flex items-start gap-2 text-[10px]"
          >
            <span className="flex-shrink-0 font-mono text-ink-muted/50">{entry.ts}</span>
            <span className="font-medium text-indigo-400/80 flex-shrink-0">{entry.agent}</span>
            <span className="text-ink-muted truncate">{entry.detail}</span>
          </motion.div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function PipelineViz() {
  const pipeline = useResearchStore((s) => s.activeJob?.pipeline ?? []);

  return (
    <div className="w-full">
      <div className="space-y-0">
        {pipeline.map((agent, i) => (
          <AgentRow key={agent.id} agent={agent} isLast={i === pipeline.length - 1} />
        ))}
      </div>
      <ActivityLog />
    </div>
  );
}
