"use client";

import { Fragment } from "react";
import { motion } from "framer-motion";
import type { PipelineStage } from "@/types/files";

const STAGES: PipelineStage[] = ["uploading", "parsing", "chunking", "embedding", "done"];
const STAGE_LABELS = {
  uploading: "Upload",
  parsing: "Parse",
  chunking: "Chunk",
  embedding: "Embed",
  done: "Done",
  error: "Error",
} as const;

export default function ProcessingPipeline({
  stage,
  originalName,
  uploadPct,
}: {
  stage: PipelineStage;
  originalName: string;
  uploadPct: number;
}) {
  const activeIndex = stage === "error" ? -1 : STAGES.indexOf(stage as (typeof STAGES)[number]);

  return (
    <div className="glass-card space-y-3 rounded-xl p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="max-w-[200px] truncate text-sm text-text-primary">{originalName}</span>
        <StatusBadge stage={stage} />
      </div>

      <div className="flex items-center">
        {STAGES.map((s, i) => {
          const isDone = i < activeIndex || stage === "done";
          const isActive = s === stage;

          return (
            <Fragment key={s}>
              <motion.div
                animate={isActive ? { scale: [1, 1.15, 1] } : {}}
                transition={isActive ? { repeat: Infinity, duration: 1.2 } : undefined}
                className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border text-xs font-bold ${
                  isDone
                    ? "border-accent-success/40 bg-accent-success/20 text-accent-success"
                    : isActive
                      ? "border-accent-primary/50 bg-accent-primary/20 text-accent-primary"
                      : "border-glass-border bg-surface-1 text-text-muted"
                }`}
              >
                {isDone ? "✓" : i + 1}
              </motion.div>
              {i < STAGES.length - 1 && (
                <div className="relative mx-1 h-[2px] flex-1 overflow-hidden bg-surface-2">
                  <motion.div
                    className="absolute inset-y-0 left-0 bg-accent-primary"
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: isDone ? 1 : isActive ? 0.5 : 0 }}
                    transition={{ duration: 0.4 }}
                    style={{ originX: 0 }}
                  />
                </div>
              )}
            </Fragment>
          );
        })}
      </div>

      <div className="flex justify-between px-0">
        {STAGES.map((s) => (
          <span key={s} className="w-8 text-center text-[10px] text-text-muted">
            {STAGE_LABELS[s]}
          </span>
        ))}
      </div>

      {stage === "uploading" && (
        <div className="h-1 overflow-hidden rounded-full bg-surface-2">
          <motion.div
            className="h-full rounded-full bg-accent-primary"
            animate={{ width: `${uploadPct}%` }}
            transition={{ duration: 0.2 }}
          />
        </div>
      )}
    </div>
  );
}

function StatusBadge({ stage }: { stage: PipelineStage }) {
  const map = {
    uploading: ["Uploading", "text-accent-primary bg-accent-primary/10 border-accent-primary/25"],
    parsing: ["Parsing", "text-accent-secondary bg-accent-secondary/10 border-accent-secondary/25"],
    chunking: ["Chunking", "text-accent-secondary bg-accent-secondary/10 border-accent-secondary/25"],
    embedding: ["Embedding", "text-accent-primary bg-accent-primary/10 border-accent-primary/25"],
    done: ["Ready", "text-accent-success bg-accent-success/10 border-accent-success/25"],
    error: ["Error", "text-accent-danger bg-accent-danger/10 border-accent-danger/25"],
  } as const;

  const [label, cls] = map[stage] ?? ["...", ""];
  return <span className={`rounded-md border px-2 py-0.5 text-[10px] font-medium ${cls}`}>{label}</span>;
}
