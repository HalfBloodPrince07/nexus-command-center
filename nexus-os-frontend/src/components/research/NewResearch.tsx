"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FlaskConical, BookOpen, AlertCircle, Loader2,
  Sparkles, ShieldCheck, FileOutput, Hash,
} from "lucide-react";
import { useResearchStore } from "@/stores/useResearchStore";
import { startResearch } from "@/lib/researchApi";
import { dispatchResearchStart } from "@/hooks/useWebSocket";
import GlassCard from "@/components/ui/GlassCard";
import PipelineViz from "./PipelineViz";
import { generateId } from "@/lib/utils";

export default function NewResearch() {
  const [topic, setTopic] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const { activeJob, startJob, setActiveSubTab } = useResearchStore();

  const isRunning  = activeJob?.status === "running";
  const isComplete = activeJob?.status === "complete";
  const isFailed   = activeJob?.status === "failed";

  const handleSubmit = async () => {
    const trimmed = topic.trim();
    if (!trimmed || submitting || isRunning) return;
    setSubmitting(true);
    setStartError(null);
    try {
      const sessionId = generateId();
      const { job_id, slug } = await startResearch(trimmed, sessionId);
      startJob(trimmed, job_id, slug);
      dispatchResearchStart(trimmed, job_id, slug);
    } catch (err: any) {
      setStartError(err.message ?? "Failed to start research");
    } finally {
      setSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleSubmit();
  };

  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto p-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-primary shadow-glow-accent">
          <FlaskConical size={20} className="text-white" strokeWidth={1.8} />
        </div>
        <div>
          <h1 className="font-display text-xl font-semibold text-ink">Deep Research</h1>
          <p className="text-xs text-ink-muted">9-agent web research pipeline</p>
        </div>
      </div>

      {/* Input card */}
      <GlassCard variant="elevated" padding="md" animate={false}>
        <label className="mb-2 block text-xs font-medium uppercase tracking-widest text-ink-muted">
          Research Topic
        </label>
        <textarea
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter a topic or question to research…"
          disabled={isRunning || submitting}
          rows={3}
          className="w-full resize-none rounded-xl bg-surface-secondary/50 px-4 py-3 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-accent/40 disabled:opacity-50 transition-all"
        />
        <div className="mt-3 flex items-center justify-between">
          <span className="text-[11px] text-ink-muted">Ctrl+Enter to submit</span>
          <button
            onClick={handleSubmit}
            disabled={!topic.trim() || submitting || isRunning}
            className="flex items-center gap-2 rounded-xl bg-gradient-primary px-5 py-2 text-sm font-semibold text-white shadow-glow-accent transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {(submitting || isRunning) && <Loader2 size={14} className="animate-spin" />}
            {isRunning ? "Researching…" : "Research"}
          </button>
        </div>
        {startError && (
          <div className="mt-3 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
            <AlertCircle size={13} />
            {startError}
          </div>
        )}
      </GlassCard>

      {/* Pipeline panel */}
      <AnimatePresence>
        {activeJob && (
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
          >
            <GlassCard variant="bordered" padding="md" animate={false}>
              {/* Panel header */}
              <div className="mb-4 flex items-center justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">
                    {isRunning  && "Pipeline Running"}
                    {isComplete && "Research Complete"}
                    {isFailed   && "Research Failed"}
                  </p>
                  <p className="mt-0.5 text-[11px] text-ink-muted truncate max-w-[220px]" title={activeJob.topic}>
                    {activeJob.topic}
                  </p>
                </div>
                <div className="flex-shrink-0">
                  {isRunning && (
                    <span className="flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-200">
                      <span className="h-1.5 w-1.5 rounded-full bg-indigo-500 animate-pulse" />
                      Live
                    </span>
                  )}
                  {isComplete && (
                    <span className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      Done
                    </span>
                  )}
                  {isFailed && (
                    <span className="flex items-center gap-1.5 rounded-full bg-red-50 px-2.5 py-1 text-[10px] font-semibold text-red-700 ring-1 ring-inset ring-red-200">
                      <AlertCircle size={10} />
                      Failed
                    </span>
                  )}
                </div>
              </div>

              <PipelineViz />

              {isFailed && activeJob.error && (
                <div className="mt-4 flex items-start gap-2 rounded-xl bg-red-50 p-3 text-xs text-red-700">
                  <AlertCircle size={13} className="mt-0.5 flex-shrink-0" />
                  <span>{activeJob.error}</span>
                </div>
              )}
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Completion card */}
      <AnimatePresence>
        {isComplete && activeJob?.report && (
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            <GlassCard
              variant="glow"
              padding="md"
              animate={false}
              onClick={() => setActiveSubTab("library")}
              className="cursor-pointer group"
            >
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-emerald-100">
                  <BookOpen size={20} className="text-emerald-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-ink">Report Ready</p>
                  <p className="mt-0.5 text-xs text-ink-secondary line-clamp-2">
                    {activeJob.report.report_title || activeJob.report.topic}
                  </p>

                  {/* Stats row */}
                  <div className="mt-2.5 grid grid-cols-2 gap-1.5">
                    <StatChip icon={<Hash size={10} />} value={`${activeJob.report.source_count} sources`} />
                    <StatChip icon={<Sparkles size={10} />} value={`${activeJob.report.word_count?.toLocaleString()} words`} />
                    {activeJob.report.verified_claims !== undefined && (
                      <StatChip icon={<ShieldCheck size={10} />} value={`${activeJob.report.verified_claims} verified`} color="emerald" />
                    )}
                    {(activeJob.report.section_count ?? 0) > 0 && (
                      <StatChip icon={<FileOutput size={10} />} value={`${activeJob.report.section_count} sections`} />
                    )}
                  </div>

                  {/* Confidence bar */}
                  {activeJob.report.avg_confidence > 0 && (
                    <div className="mt-2.5">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[10px] text-ink-muted">Confidence</span>
                        <span className="text-[10px] font-semibold text-emerald-600">
                          {Math.round(activeJob.report.avg_confidence * 100)}%
                        </span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-surface-secondary overflow-hidden">
                        <motion.div
                          className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-400"
                          initial={{ width: 0 }}
                          animate={{ width: `${activeJob.report.avg_confidence * 100}%` }}
                          transition={{ duration: 0.8, delay: 0.2, ease: "easeOut" }}
                        />
                      </div>
                    </div>
                  )}
                </div>
                <span className="text-[11px] font-semibold text-accent opacity-0 group-hover:opacity-100 transition-opacity">
                  View →
                </span>
              </div>
            </GlassCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function StatChip({
  icon,
  value,
  color = "default",
}: {
  icon: React.ReactNode;
  value: string;
  color?: "default" | "emerald";
}) {
  return (
    <span className={cn(
      "flex items-center gap-1 rounded-lg px-2 py-1 text-[10px] font-medium",
      color === "emerald"
        ? "bg-emerald-50 text-emerald-700"
        : "bg-surface-secondary text-ink-muted",
    )}>
      {icon}
      {value}
    </span>
  );
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}
