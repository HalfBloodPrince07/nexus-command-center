"use client";

import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Brain,
  Clock,
  Database,
  GitBranch,
  X,
  RefreshCw,
  Search,
  Trash2,
  WifiOff,
} from "lucide-react";
import { useMemoryStore, MemoryLayer } from "@/stores/useMemoryStore";
import { useChatStore } from "@/stores/useChatStore";
import { formatRelativeTime } from "@/lib/memoryApi";
import { cn } from "@/lib/utils";

const LAYERS: {
  id: MemoryLayer;
  label: string;
  icon: React.ElementType;
  color: string;
  ring: string;
  bg: string;
  desc: string;
  backend: string;
}[] = [
  {
    id: "episodic",
    label: "Episodic",
    icon: Clock,
    color: "text-violet-400",
    ring: "ring-violet-500/30",
    bg: "bg-violet-500/10",
    desc: "Recent interactions",
    backend: "Redis",
  },
  {
    id: "semantic",
    label: "Semantic",
    icon: Database,
    color: "text-teal-400",
    ring: "ring-teal-500/30",
    bg: "bg-teal-500/10",
    desc: "Facts & knowledge",
    backend: "ChromaDB",
  },
  {
    id: "procedural",
    label: "Procedural",
    icon: GitBranch,
    color: "text-indigo-400",
    ring: "ring-indigo-500/30",
    bg: "bg-indigo-500/10",
    desc: "Behavior patterns",
    backend: "SQLite",
  },
];

const AvailDot = ({ available }: { available: boolean }) => (
  <span className="relative flex h-2 w-2 flex-shrink-0">
    {available && (
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-50" />
    )}
    <span
      className={cn(
        "relative inline-flex h-2 w-2 rounded-full",
        available ? "bg-emerald-400" : "bg-zinc-500/60"
      )}
    />
  </span>
);

type SemanticMemoryDetail = {
  kind: "semantic";
  id: string;
  text: string;
  score?: number;
  metadata: {
    source: string;
    category: string;
    session_id: string;
    stored_at: string;
  };
};

type ProceduralMemoryDetail = {
  kind: "procedural";
  id: string;
  pattern_type: string;
  trigger: string;
  action: string;
  confidence: number;
  use_count: number;
  session_id?: string | null;
  created_at: string;
  updated_at: string;
};

type MemoryDetail = SemanticMemoryDetail | ProceduralMemoryDetail;

const formatTimestampLabel = (value?: string) => {
  if (!value) return "unknown";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return formatRelativeTime(parsed);
};

const DetailDrawer = ({
  item,
  onClose,
}: {
  item: MemoryDetail | null;
  onClose: () => void;
}) => {
  if (!item) return null;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      >
        <button
          type="button"
          aria-label="Close detail drawer"
          className="absolute inset-0 cursor-default bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        />
        <motion.div
          initial={{ x: 24, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 24, opacity: 0 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="absolute right-0 top-0 flex h-full w-full max-w-[440px] flex-col border-l border-border-subtle bg-surface/95 p-5 shadow-2xl"
        >
          <div className="mb-4 flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-ink-muted">
                {item.kind === "semantic" ? "Semantic Fact" : "Procedural Pattern"}
              </p>
              <h3 className="mt-1 text-lg font-semibold text-ink">
                {item.kind === "semantic" ? item.metadata.category : item.pattern_type}
              </h3>
            </div>
            <button
              type="button"
              title="Close"
              onClick={onClose}
              className="rounded-lg p-2 text-ink-muted transition-colors hover:bg-surface-elevated hover:text-ink"
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex-1 space-y-4 overflow-y-auto pr-1">
            {item.kind === "semantic" ? (
              <>
                <div className="rounded-2xl bg-surface-elevated/60 p-4 ring-1 ring-inset ring-border-subtle">
                  <p className="text-sm leading-relaxed text-ink-secondary">{item.text}</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle">
                    <p className="text-[10px] uppercase tracking-wider text-ink-muted">Source</p>
                    <p className="mt-1 break-words text-sm text-ink">{item.metadata.source || "semantic memory"}</p>
                  </div>
                  <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle">
                    <p className="text-[10px] uppercase tracking-wider text-ink-muted">Stored</p>
                    <p className="mt-1 text-sm text-ink">{formatTimestampLabel(item.metadata.stored_at)}</p>
                  </div>
                  <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle">
                    <p className="text-[10px] uppercase tracking-wider text-ink-muted">Session</p>
                    <p className="mt-1 font-mono text-sm text-ink">
                      {item.metadata.session_id ? item.metadata.session_id.slice(0, 12) : "—"}
                    </p>
                  </div>
                  <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle">
                    <p className="text-[10px] uppercase tracking-wider text-ink-muted">Match</p>
                    <p className="mt-1 text-sm text-ink">
                      {typeof item.score === "number" ? `${(item.score * 100).toFixed(0)}%` : "Browse"}
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div className="rounded-2xl bg-surface-elevated/60 p-4 ring-1 ring-inset ring-border-subtle">
                  <p className="text-[10px] uppercase tracking-wider text-ink-muted">Trigger</p>
                  <p className="mt-1 text-sm leading-relaxed text-ink-secondary">{item.trigger}</p>
                </div>
                <div className="rounded-2xl bg-surface-elevated/60 p-4 ring-1 ring-inset ring-border-subtle">
                  <p className="text-[10px] uppercase tracking-wider text-ink-muted">Action</p>
                  <p className="mt-1 text-sm leading-relaxed text-ink-secondary">{item.action}</p>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle">
                    <p className="text-[10px] uppercase tracking-wider text-ink-muted">Confidence</p>
                    <p className="mt-1 text-sm text-ink">{Math.round(item.confidence * 100)}%</p>
                  </div>
                  <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle">
                    <p className="text-[10px] uppercase tracking-wider text-ink-muted">Use Count</p>
                    <p className="mt-1 text-sm text-ink">{item.use_count}</p>
                  </div>
                  <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle">
                    <p className="text-[10px] uppercase tracking-wider text-ink-muted">Created</p>
                    <p className="mt-1 text-sm text-ink">{formatTimestampLabel(item.created_at)}</p>
                  </div>
                  <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle">
                    <p className="text-[10px] uppercase tracking-wider text-ink-muted">Updated</p>
                    <p className="mt-1 text-sm text-ink">{formatTimestampLabel(item.updated_at)}</p>
                  </div>
                  <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle sm:col-span-2">
                    <p className="text-[10px] uppercase tracking-wider text-ink-muted">Session</p>
                    <p className="mt-1 font-mono text-sm text-ink">
                      {item.session_id ? item.session_id.slice(0, 12) : "—"}
                    </p>
                  </div>
                </div>
              </>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

const EpisodicPanel = () => {
  const { episodicItems, isLoadingLayer, loadAllEpisodic, clearEpisodic, stats } =
    useMemoryStore();
  const { conversationId } = useChatStore();
  const available = stats?.episodic.available ?? false;

  const handleClearSession = async () => {
    if (!conversationId) return;
    if (!window.confirm("Clear episodic memory for the current session?")) return;
    await clearEpisodic(conversationId);
    await loadAllEpisodic();
  };

  if (!available) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <WifiOff size={32} className="text-zinc-500" />
        <p className="text-sm font-medium text-ink-secondary">Redis unavailable</p>
        <p className="max-w-[280px] text-xs text-ink-muted">
          Start Redis on localhost:6379 to enable episodic memory.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-ink-muted">
          <AvailDot available={available} />
          <span>All sessions · {stats?.episodic.total ?? 0} events</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => loadAllEpisodic()}
            className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-ink-muted ring-1 ring-inset ring-border-subtle transition-colors hover:text-ink"
          >
            <RefreshCw size={11} className={cn(isLoadingLayer && "animate-spin")} />
            Refresh
          </button>
          {conversationId && episodicItems.length > 0 && (
            <button
              onClick={handleClearSession}
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-red-400 ring-1 ring-inset ring-red-500/20 transition-colors hover:bg-red-500/10"
            >
              <Trash2 size={11} />
              Clear session
            </button>
          )}
        </div>
      </div>

      {isLoadingLayer ? (
        <div className="flex justify-center py-8">
          <RefreshCw size={18} className="animate-spin text-ink-muted" />
        </div>
      ) : episodicItems.length === 0 ? (
        <div className="py-10 text-center text-sm text-ink-muted">
          No episodic events yet. Start chatting to build memory.
        </div>
      ) : (
        <div className="space-y-2">
          {episodicItems.map((item, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle"
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-violet-400">
                  {item.type}
                </span>
                <span className="text-[10px] tabular-nums text-ink-muted">
                  {formatRelativeTime(item.timestamp)}
                </span>
              </div>
              <p className="line-clamp-2 text-xs leading-relaxed text-ink-secondary">
                {item.content}
              </p>
              {item.session_id && (
                <p className="mt-1 truncate font-mono text-[9px] text-ink-muted opacity-50">
                  {item.session_id.slice(0, 8)}...
                </p>
              )}
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
};

const SemanticPanel = ({
  onSelectItem,
}: {
  onSelectItem: (item: SemanticMemoryDetail) => void;
}) => {
  const {
    semanticItems,
    semanticResults,
    isLoadingLayer,
    searchSemantic,
    browseSemantic,
    semanticQuery,
    setSemanticQuery,
    stats,
  } = useMemoryStore();
  const available = stats?.semantic.available ?? false;
  const showingSearch = semanticQuery.trim().length > 0;
  const items = showingSearch ? semanticResults : semanticItems;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (semanticQuery.trim()) searchSemantic(semanticQuery);
  };

  const formatStoredAt = (storedAt?: string) => {
    if (!storedAt) return "recent";
    const parsed = Date.parse(storedAt);
    if (Number.isNaN(parsed)) return storedAt;
    return formatRelativeTime(parsed);
  };

  if (!available) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <WifiOff size={32} className="text-zinc-500" />
        <p className="text-sm font-medium text-ink-secondary">ChromaDB unavailable</p>
        <p className="max-w-[280px] text-xs text-ink-muted">
          Make sure LM Studio is running for embeddings and ChromaDB is initialized.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2 text-xs text-ink-muted">
        <div className="flex items-center gap-2">
          <AvailDot available={available} />
          <span>
            {stats?.semantic.total ?? 0} facts stored
            {showingSearch ? " · vector similarity search" : " · latest stored facts"}
          </span>
        </div>
        <button
          onClick={() => browseSemantic()}
          className="flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] text-ink-muted ring-1 ring-inset ring-border-subtle transition-colors hover:text-ink"
        >
          <RefreshCw size={11} className={cn(isLoadingLayer && "animate-spin")} />
          Browse latest
        </button>
      </div>

      <form onSubmit={handleSearch} className="relative">
        <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          type="text"
          value={semanticQuery}
          onChange={(e) => setSemanticQuery(e.target.value)}
          placeholder="Search semantic memory..."
          className="w-full rounded-xl bg-surface-elevated py-2.5 pl-8 pr-3 text-sm text-ink placeholder:text-ink-muted ring-1 ring-inset ring-border-subtle transition-shadow focus:outline-none focus:ring-accent/40"
        />
      </form>

      {isLoadingLayer ? (
        <div className="flex justify-center py-8">
          <RefreshCw size={18} className="animate-spin text-ink-muted" />
        </div>
      ) : items.length === 0 ? (
        <div className="py-10 text-center text-sm text-ink-muted">
          {showingSearch ? "No matching facts found." : "No semantic facts stored yet."}
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((r, i) => (
            <motion.button
              key={r.id}
              type="button"
              onClick={() => onSelectItem(r as SemanticMemoryDetail)}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.04 }}
              className="w-full rounded-xl bg-surface-elevated/60 p-3 text-left ring-1 ring-inset ring-border-subtle transition-colors hover:bg-surface-elevated"
            >
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <span className="rounded-full bg-teal-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-teal-400">
                  {r.metadata.category}
                </span>
                <span className="text-[10px] tabular-nums text-ink-muted">
                  {showingSearch ? `${(r.score * 100).toFixed(0)}% match` : formatStoredAt(r.metadata.stored_at)}
                </span>
              </div>
              <p className="line-clamp-3 text-xs leading-relaxed text-ink-secondary">{r.text}</p>
              <div className="mt-1 flex items-center justify-between gap-2 text-[10px] text-ink-muted">
                <span className="truncate">{r.metadata.source || "semantic memory"}</span>
                {!showingSearch && r.metadata.session_id && (
                  <span className="truncate opacity-70">{r.metadata.session_id.slice(0, 8)}...</span>
                )}
              </div>
            </motion.button>
          ))}
        </div>
      )}
    </div>
  );
};

const PATTERN_TYPES = ["", "preference", "behavior", "skill"] as const;
type PatternType = (typeof PATTERN_TYPES)[number];

const ProceduralPanel = ({
  onSelectItem,
}: {
  onSelectItem: (item: ProceduralMemoryDetail) => void;
}) => {
  const { proceduralPatterns, isLoadingLayer, loadProcedural, stats } = useMemoryStore();
  const [filterType, setFilterType] = useState<PatternType>("");
  const byType = stats?.procedural.by_type ?? {};

  const handleFilter = (type: PatternType) => {
    setFilterType(type);
    loadProcedural(type || undefined);
  };

  const confidenceColor = (c: number) =>
    c >= 0.8 ? "bg-emerald-400" : c >= 0.5 ? "bg-amber-400" : "bg-red-400";

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {PATTERN_TYPES.map((t) => (
          <button
            key={t}
            onClick={() => handleFilter(t)}
            className={cn(
              "rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ring-inset transition-all",
              filterType === t
                ? "bg-indigo-500/20 text-indigo-300 ring-indigo-500/40"
                : "text-ink-muted ring-border-subtle hover:text-ink"
            )}
          >
            {t === "" ? "All" : t}
            {t !== "" && <span className="ml-1 tabular-nums opacity-60">{byType[t] ?? 0}</span>}
          </button>
        ))}
        <button
          onClick={() => loadProcedural(filterType || undefined)}
          className="ml-auto flex items-center gap-1 text-[11px] text-ink-muted transition-colors hover:text-ink"
        >
          <RefreshCw size={11} className={cn(isLoadingLayer && "animate-spin")} />
          Refresh
        </button>
      </div>

      {isLoadingLayer ? (
        <div className="flex justify-center py-8">
          <RefreshCw size={18} className="animate-spin text-ink-muted" />
        </div>
      ) : proceduralPatterns.length === 0 ? (
        <div className="py-10 text-center text-sm text-ink-muted">
          No procedural patterns yet. They form as NEXUS learns your preferences.
        </div>
      ) : (
        <div className="space-y-2">
          {proceduralPatterns.map((p, i) => (
            <motion.button
              key={p.id}
              type="button"
              onClick={() => onSelectItem(p as ProceduralMemoryDetail)}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              className="w-full rounded-xl bg-surface-elevated/60 p-3 text-left ring-1 ring-inset ring-border-subtle transition-colors hover:bg-surface-elevated"
            >
              <div className="mb-1.5 flex items-center gap-2">
                <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-indigo-400">
                  {p.pattern_type}
                </span>
                <div className="ml-auto flex items-center gap-1.5">
                  <span className="text-[10px] tabular-nums text-ink-muted">x{p.use_count}</span>
                  <div className="h-1.5 w-12 overflow-hidden rounded-full bg-surface-tertiary">
                    <div
                      className={cn("h-full rounded-full w-[var(--progress)]", confidenceColor(p.confidence))}
                      style={{ "--progress": `${Math.round(p.confidence * 100)}%` } as React.CSSProperties}
                    />
                  </div>
                </div>
              </div>
              <p className="text-[11px] font-medium text-ink truncate">{p.trigger}</p>
              <p className="mt-0.5 line-clamp-2 text-[10px] text-ink-muted">{p.action}</p>
            </motion.button>
          ))}
        </div>
      )}
    </div>
  );
};

export default function MemoryTab() {
  const [selectedDetail, setSelectedDetail] = useState<MemoryDetail | null>(null);
  const {
    stats,
    isLoadingStats,
    loadStats,
    selectedLayer,
    setSelectedLayer,
    loadAllEpisodic,
    loadSemantic,
    semanticItems,
    browseSemantic,
    loadProcedural,
    isLoadingLayer,
  } = useMemoryStore();
  const { conversationId } = useChatStore();

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelectedDetail(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setSelectedDetail]);

  useEffect(() => {
    if (selectedLayer === "episodic") {
      loadAllEpisodic();
    } else if (selectedLayer === "semantic") {
      if (semanticItems.length === 0 && !isLoadingLayer) {
        loadSemantic();
      }
    } else if (selectedLayer === "procedural") {
      loadProcedural();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedLayer]);

  const handleSelectLayer = (layer: MemoryLayer) => {
    setSelectedDetail(null);
    setSelectedLayer(layer);
  };

  const getCount = (layer: MemoryLayer) => {
    if (!stats) return 0;
    if (layer === "episodic") return stats.episodic.total;
    if (layer === "semantic") return stats.semantic.total;
    if (layer === "procedural") return stats.procedural.total;
    return "—";
  };

  const isAvailable = (layer: MemoryLayer) => {
    if (!stats) return false;
    if (layer === "episodic") return stats.episodic.available;
    if (layer === "semantic") return stats.semantic.available;
    return true;
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex-none border-b border-border-subtle px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600">
              <Brain size={18} className="text-white" />
            </div>
            <div>
              <h1 className="font-display text-lg font-semibold text-ink">Memory</h1>
              <p className="text-[11px] text-ink-muted">Three-tier cognitive storage</p>
            </div>
          </div>
          <button
            onClick={() => loadStats()}
            disabled={isLoadingStats}
            className="flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs text-ink-muted ring-1 ring-inset ring-border-subtle transition-colors hover:text-ink"
          >
            <RefreshCw size={12} className={cn(isLoadingStats && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex-none border-b border-border-subtle px-6 py-3">
        <div className="grid grid-cols-3 gap-3">
          {LAYERS.map(({ id, label, icon: Icon, color, ring, bg, backend }) => (
            <button
              key={id}
              onClick={() => handleSelectLayer(id)}
              className={cn(
                "rounded-xl p-3 text-left ring-1 ring-inset transition-all",
                selectedLayer === id
                  ? `${bg} ${ring}`
                  : "bg-surface-elevated/40 ring-border-subtle hover:bg-surface-elevated"
              )}
            >
              <div className="mb-1.5 flex items-center justify-between">
                <Icon size={13} className={cn(color)} />
                <AvailDot available={isAvailable(id)} />
              </div>
              <p className={cn("font-display text-xl font-semibold tabular-nums", color)}>
                {isLoadingStats ? "..." : getCount(id)}
              </p>
              <p className="mt-0.5 text-[10px] font-medium text-ink-secondary">{label}</p>
              <p className="text-[9px] text-ink-muted">{backend}</p>
            </button>
          ))}
        </div>
      </div>

      <div className="flex-none flex gap-1 border-b border-border-subtle px-6 pb-0 pt-3">
        {LAYERS.map(({ id, label, icon: Icon, color }) => (
          <button
            key={id}
            onClick={() => handleSelectLayer(id)}
            className={cn(
              "relative flex items-center gap-2 px-1 pb-2.5 text-xs font-medium transition-colors",
              selectedLayer === id ? "text-ink" : "text-ink-muted hover:text-ink-secondary"
            )}
          >
            <Icon size={12} className={cn(selectedLayer === id ? color : "")} />
            {label}
            {selectedLayer === id && (
              <motion.div
                layoutId="memory-tab-indicator"
                className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-gradient-to-r from-violet-500 to-indigo-500"
              />
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={selectedLayer}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            {selectedLayer === "episodic" && <EpisodicPanel />}
            {selectedLayer === "semantic" && (
              <SemanticPanel onSelectItem={(item) => setSelectedDetail(item)} />
            )}
            {selectedLayer === "procedural" && (
              <ProceduralPanel onSelectItem={(item) => setSelectedDetail(item)} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
      <DetailDrawer item={selectedDetail} onClose={() => setSelectedDetail(null)} />
    </div>
  );
}
