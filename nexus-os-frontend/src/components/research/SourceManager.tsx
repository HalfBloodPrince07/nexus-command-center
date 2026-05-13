"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ExternalLink, RefreshCw, AlertCircle } from "lucide-react";
import { useResearchStore } from "@/stores/useResearchStore";
import { listAllSources } from "@/lib/researchApi";
import { cn } from "@/lib/utils";
import type { ResearchSource } from "@/types/research";

const PAGE_SIZE = 20;

const statusConfig: Record<string, { label: string; classes: string }> = {
  success:    { label: "OK",       classes: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  paywall:    { label: "Paywall",  classes: "bg-amber-50 text-amber-700 ring-amber-200" },
  timeout:    { label: "Timeout",  classes: "bg-orange-50 text-orange-700 ring-orange-200" },
  error:      { label: "Error",    classes: "bg-red-50 text-red-700 ring-red-200" },
  http_error: { label: "HTTP Err", classes: "bg-red-50 text-red-700 ring-red-200" },
};

export default function SourceManager() {
  const { sources, setSources } = useResearchStore();
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [filterStatus, setFilterStatus] = useState<string>("all");

  const fetchSources = async () => {
    setLoading(true);
    try {
      const data = await listAllSources();
      setSources(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchSources(); }, []);

  const filtered = filterStatus === "all"
    ? sources
    : sources.filter((s) => s.extraction_status === filterStatus);

  const pages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  const qualityBar = (score: number) => {
    const pct = Math.round(score * 100);
    const color = score >= 0.7 ? "bg-emerald-400" : score >= 0.4 ? "bg-amber-400" : "bg-red-400";
    return (
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-secondary">
          <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-[11px] text-ink-muted">{pct}</span>
      </div>
    );
  };

  return (
    <div className="flex h-full flex-col gap-4 overflow-hidden p-6">
      {/* Header */}
      <div className="flex flex-shrink-0 items-center justify-between">
        <h2 className="font-display text-lg font-semibold text-ink">
          Sources
          {sources.length > 0 && (
            <span className="ml-2 text-sm font-normal text-ink-muted">({sources.length})</span>
          )}
        </h2>
        <button
          onClick={fetchSources}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-ink-secondary hover:text-ink hover:bg-surface-secondary/60 transition-all disabled:opacity-40"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Filter bar */}
      <div className="flex flex-shrink-0 flex-wrap gap-2">
        {["all", "success", "paywall", "timeout", "error", "http_error"].map((s) => (
          <button
            key={s}
            onClick={() => { setFilterStatus(s); setPage(0); }}
            className={cn(
              "rounded-full px-3 py-1 text-[11px] font-medium ring-1 ring-inset transition-all",
              filterStatus === s
                ? "bg-accent text-white ring-accent"
                : "bg-surface-secondary text-ink-secondary ring-border-subtle hover:text-ink"
            )}
          >
            {s === "all" ? "All" : statusConfig[s]?.label ?? s}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="min-h-0 flex-1 overflow-auto rounded-2xl glass">
        {paged.length === 0 && !loading ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <AlertCircle size={36} className="mb-4 text-ink-muted/40" strokeWidth={1.2} />
            <p className="text-sm text-ink-secondary">No sources found</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-left text-[11px] uppercase tracking-wider text-ink-muted">
                <th className="px-4 py-3 font-medium">Domain</th>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Quality</th>
                <th className="px-4 py-3 font-medium">Chars</th>
                <th className="px-4 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium" />
              </tr>
            </thead>
            <tbody>
              {paged.map((src, i) => {
                const sc = statusConfig[src.extraction_status] ?? { label: src.extraction_status, classes: "bg-surface-secondary text-ink-muted ring-border-subtle" };
                return (
                  <motion.tr
                    key={src.url_hash}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.02 }}
                    className="border-b border-border-subtle/50 hover:bg-surface-secondary/30 transition-colors"
                  >
                    <td className="px-4 py-2.5 text-xs font-medium text-ink-secondary whitespace-nowrap">
                      {src.domain}
                    </td>
                    <td className="max-w-[240px] px-4 py-2.5 text-xs text-ink">
                      <span className="line-clamp-1">{src.title || "—"}</span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset", sc.classes)}>
                        {sc.label}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">{qualityBar(src.quality_score)}</td>
                    <td className="px-4 py-2.5 text-xs text-ink-muted">
                      {src.char_count?.toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-ink-muted whitespace-nowrap">
                      {new Date(src.scraped_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-2.5">
                      <a
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="flex items-center gap-1 text-xs text-accent hover:underline"
                      >
                        <ExternalLink size={11} />
                        Open
                      </a>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex flex-shrink-0 items-center justify-between text-xs text-ink-muted">
          <span>
            {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, filtered.length)} of {filtered.length}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="rounded-lg px-3 py-1.5 hover:bg-surface-secondary/60 disabled:opacity-30"
            >
              Prev
            </button>
            <button
              onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
              disabled={page >= pages - 1}
              className="rounded-lg px-3 py-1.5 hover:bg-surface-secondary/60 disabled:opacity-30"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
