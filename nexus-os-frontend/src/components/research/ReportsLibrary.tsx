"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, BookOpen, Trash2, Loader2, RefreshCw } from "lucide-react";
import { useResearchStore } from "@/stores/useResearchStore";
import { listReports, getReport, deleteReport } from "@/lib/researchApi";
import GlassCard from "@/components/ui/GlassCard";
import type { ResearchReport } from "@/types/research";

export default function ReportsLibrary() {
  const { reports, setReports, openReport, removeReport } = useResearchStore();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [opening, setOpening] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const data = await listReports();
      setReports(data);
    } catch {
      // silently fail — list stays stale
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchReports(); }, []);

  const filtered = reports.filter((r) =>
    r.topic.toLowerCase().includes(query.toLowerCase()) ||
    (r.tags ?? []).some((t) => t.toLowerCase().includes(query.toLowerCase()))
  );

  const handleOpen = async (slug: string) => {
    setOpening(slug);
    try {
      const { content, metadata } = await getReport(slug);
      openReport(slug, content, metadata);
    } finally {
      setOpening(null);
    }
  };

  const handleDelete = async (e: React.MouseEvent, slug: string) => {
    e.stopPropagation();
    if (!window.confirm("Delete this report?")) return;
    setDeleting(slug);
    try {
      await deleteReport(slug);
      removeReport(slug);
    } finally {
      setDeleting(null);
    }
  };

  const confidenceColor = (avg: number) => {
    if (avg >= 0.75) return "bg-emerald-50 text-emerald-700 ring-emerald-200";
    if (avg >= 0.5) return "bg-amber-50 text-amber-700 ring-amber-200";
    return "bg-red-50 text-red-700 ring-red-200";
  };

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold text-ink">Reports Library</h2>
        <button
          onClick={fetchReports}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-ink-secondary hover:text-ink hover:bg-surface-secondary/60 transition-all disabled:opacity-40"
        >
          <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search reports or tags…"
          className="w-full rounded-xl bg-surface-secondary/50 py-2.5 pl-9 pr-4 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-accent/40"
        />
      </div>

      {/* Empty state */}
      {!loading && filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <BookOpen size={40} className="mb-4 text-ink-muted/40" strokeWidth={1.2} />
          <p className="text-sm font-medium text-ink-secondary">No reports yet</p>
          <p className="mt-1 text-xs text-ink-muted">Start a research job to generate reports.</p>
        </div>
      )}

      {/* Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <AnimatePresence>
          {filtered.map((report, i) => (
            <motion.div
              key={report.slug}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              transition={{ duration: 0.3, delay: i * 0.04 }}
            >
              <GlassCard
                variant="elevated"
                padding="sm"
                animate={false}
                onClick={() => handleOpen(report.slug)}
                className="group relative h-full"
              >
                {/* Delete button */}
                <button
                  onClick={(e) => handleDelete(e, report.slug)}
                  disabled={deleting === report.slug}
                  className="absolute right-3 top-3 hidden rounded-lg p-1.5 text-ink-muted hover:bg-red-50 hover:text-red-600 group-hover:flex transition-all"
                >
                  {deleting === report.slug
                    ? <Loader2 size={13} className="animate-spin" />
                    : <Trash2 size={13} />
                  }
                </button>

                {/* Card content */}
                <div className="flex flex-col gap-2">
                  {/* Topic */}
                  <p className="pr-8 text-sm font-semibold text-ink line-clamp-2 leading-snug">
                    {report.topic}
                  </p>

                  {/* Confidence badge */}
                  <span className={`inline-flex w-fit items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${confidenceColor(report.avg_confidence)}`}>
                    {Math.round(report.avg_confidence * 100)}% confidence
                  </span>

                  {/* Stats */}
                  <div className="flex flex-wrap gap-2 text-[11px] text-ink-muted">
                    <span>{report.source_count} src</span>
                    <span>·</span>
                    <span>{report.word_count?.toLocaleString()} words</span>
                    <span>·</span>
                    <span>{new Date(report.created_at).toLocaleDateString()}</span>
                  </div>

                  {/* Tags */}
                  {report.tags?.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {report.tags.slice(0, 4).map((tag) => (
                        <span key={tag} className="rounded-full bg-accent-muted px-2 py-0.5 text-[10px] text-accent-dark">
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* Opening spinner */}
                {opening === report.slug && (
                  <div className="absolute inset-0 flex items-center justify-center rounded-2xl bg-white/50 backdrop-blur-sm">
                    <Loader2 size={20} className="animate-spin text-accent" />
                  </div>
                )}
              </GlassCard>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
