"use client";
import { AnimatePresence, motion } from "framer-motion";
import { useAppStore } from "@/stores/useAppStore";
import { AgentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const AgentActivityPanel = () => {
  const { activeAgents, activeAgentId } = useAppStore();

  const grouped = {
    supervisor: activeAgents.find((a) => a.tier === 1) ?? null,
    lead: activeAgents.find((a) => a.tier === 2) ?? null,
    specialists: activeAgents.filter((a) => a.tier === 3),
  };

  const busyCount = activeAgents.filter(
    (a) => a.status === "thinking" || a.status === "streaming"
  ).length;

  return (
    <div className="h-full w-[280px] border-l border-border-subtle glass-subtle p-4 flex flex-col">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-display text-sm font-semibold tracking-tight text-ink">Agents</h3>
        <span className="inline-flex items-center rounded-full bg-accent-muted px-2.5 py-0.5 text-[11px] font-semibold text-accent-dark ring-1 ring-inset ring-border-accent">
          {activeAgents.length}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4">
        {/* Hierarchy diagram */}
        <div className="rounded-2xl border border-glass-border bg-surface-1/70 p-4">
          <div className="flex flex-col items-center gap-3">
            {grouped.supervisor && (
              <AgentNode agent={grouped.supervisor} activeAgentId={activeAgentId} />
            )}
            <div className="h-4 w-px bg-glass-border" />
            {grouped.lead && (
              <AgentNode agent={grouped.lead} activeAgentId={activeAgentId} />
            )}
            {grouped.specialists.length > 0 && (
              <>
                <div className="h-4 w-px bg-glass-border" />
                <div className="flex w-full items-start justify-center gap-3">
                  {grouped.specialists.map((agent) => (
                    <div key={agent.id} className="flex flex-1 flex-col items-center">
                      <div className="h-px w-full bg-glass-border" />
                      <AgentNode agent={agent} activeAgentId={activeAgentId} compact />
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Agent cards */}
        <div className="space-y-2">
          {activeAgents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} activeAgentId={activeAgentId} />
          ))}
        </div>
      </div>

      {/* Activity indicator bar */}
      {busyCount > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 4 }}
          className="mt-3 rounded-xl bg-accent-primary/10 border border-accent-primary/20 px-3 py-2 text-[11px] text-accent-primary font-medium flex items-center gap-2"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-accent-primary animate-pulse" />
          {busyCount} agent{busyCount > 1 ? "s" : ""} working…
        </motion.div>
      )}
    </div>
  );
};

/** Status dot config */
const STATUS_CONFIG: Record<
  AgentStatus["status"],
  { dot: string; label: string; glow: string }
> = {
  thinking: {
    dot: "bg-violet-400 animate-pulse",
    label: "thinking…",
    glow: "shadow-[0_0_8px_rgba(167,139,250,0.6)]",
  },
  streaming: {
    dot: "bg-emerald-400 animate-pulse",
    label: "streaming",
    glow: "shadow-[0_0_8px_rgba(52,211,153,0.6)]",
  },
  idle: {
    dot: "bg-text-muted/50",
    label: "idle",
    glow: "",
  },
  error: {
    dot: "bg-red-400",
    label: "error",
    glow: "",
  },
};

function AgentNode({
  agent,
  activeAgentId,
  compact = false,
}: {
  agent: AgentStatus;
  activeAgentId: string;
  compact?: boolean;
}) {
  const isActive =
    activeAgentId === agent.id ||
    activeAgentId === agent.name ||
    activeAgentId.toLowerCase() === agent.name.toLowerCase();

  const isBusy = agent.status === "thinking" || agent.status === "streaming";
  const cfg = STATUS_CONFIG[agent.status] ?? STATUS_CONFIG.idle;

  return (
    <motion.div
      layout
      className={cn(
        "relative rounded-2xl border px-3 py-2 text-center shadow-sm transition-colors",
        compact ? "min-w-[72px]" : "min-w-[120px]",
        isActive || isBusy
          ? "border-accent-primary/50 bg-accent-primary/10 text-accent-primary"
          : "border-glass-border bg-surface-1 text-text-primary"
      )}
    >
      <AnimatePresence>
        {(isActive || isBusy) && (
          <motion.div
            layoutId={`activeAgent-${agent.id}`}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="pointer-events-none absolute inset-0 rounded-2xl border border-accent-primary/50 bg-accent-primary/20 shadow-[0_0_24px_rgba(99,102,241,0.15)]"
          />
        )}
      </AnimatePresence>
      <div className="relative z-10">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">
          {agent.name}
        </div>
        {isBusy && (
          <div className={cn("mt-0.5 text-[9px] font-medium", agent.status === "thinking" ? "text-violet-400" : "text-emerald-400")}>
            {cfg.label}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function AgentCard({
  agent,
  activeAgentId,
}: {
  agent: AgentStatus;
  activeAgentId: string;
}) {
  const isActive =
    activeAgentId === agent.id ||
    activeAgentId === agent.name ||
    activeAgentId.toLowerCase() === agent.name.toLowerCase();

  const isBusy = agent.status === "thinking" || agent.status === "streaming";
  const cfg = STATUS_CONFIG[agent.status] ?? STATUS_CONFIG.idle;

  return (
    <motion.div
      layout
      className={cn(
        "rounded-2xl border p-3 shadow-sm transition-colors",
        isActive || isBusy
          ? "border-accent-primary/25 bg-accent-primary/10"
          : "border-glass-border bg-surface-1/60"
      )}
    >
      <div className="flex items-start gap-3">
        {/* Avatar */}
        <div
          className={cn(
            "flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl text-sm font-semibold relative",
            isActive || isBusy
              ? cn("bg-accent-primary/20 text-accent-primary", isBusy && cfg.glow)
              : "bg-surface-2 text-text-primary"
          )}
        >
          {agent.name.charAt(0)}
          {isBusy && (
            <span className={cn("absolute -top-1 -right-1 h-3 w-3 rounded-full border-2 border-surface-1", cfg.dot)} />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h4 className="truncate text-sm font-semibold text-text-primary">{agent.name}</h4>
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] font-semibold text-text-muted">
              T{agent.tier}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-text-muted truncate">{agent.description}</p>

          {/* Status row */}
          <div className="mt-2 flex items-center gap-2">
            <span className={cn("h-2 w-2 rounded-full flex-shrink-0", cfg.dot)} />
            <span
              className={cn(
                "text-[11px] font-medium",
                agent.status === "thinking" && "text-violet-400",
                agent.status === "streaming" && "text-emerald-400",
                agent.status === "idle" && "text-text-muted",
                agent.status === "error" && "text-red-400"
              )}
            >
              {cfg.label}
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

export default AgentActivityPanel;
