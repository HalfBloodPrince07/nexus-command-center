"use client";

import { motion } from "framer-motion";
import { ArrowLeft, Download, ExternalLink } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { useResearchStore } from "@/stores/useResearchStore";
import "highlight.js/styles/github.css";

export default function ReportViewer() {
  const { viewingReport, closeReport } = useResearchStore();

  if (!viewingReport) return null;

  const { content, metadata } = viewingReport;

  const handleExport = () => {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${metadata.slug}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const confidenceColor = (v: number) => {
    if (v >= 0.75) return "bg-emerald-50 text-emerald-700 ring-emerald-200";
    if (v >= 0.5) return "bg-amber-50 text-amber-700 ring-amber-200";
    return "bg-red-50 text-red-700 ring-red-200";
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 12 }}
      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
      className="flex h-full flex-col overflow-hidden"
    >
      {/* Toolbar */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-border-subtle px-6 py-3">
        <button
          onClick={closeReport}
          className="flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm text-ink-secondary hover:bg-surface-secondary/60 hover:text-ink transition-all"
        >
          <ArrowLeft size={16} />
          Back to Library
        </button>
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset ${confidenceColor(metadata.avg_confidence)}`}>
            {Math.round(metadata.avg_confidence * 100)}% conf
          </span>
          <span className="text-[11px] text-ink-muted">{metadata.source_count} sources</span>
          <span className="text-[11px] text-ink-muted">·</span>
          <span className="text-[11px] text-ink-muted">{metadata.word_count?.toLocaleString()} words</span>
          <button
            onClick={handleExport}
            className="ml-2 flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs font-medium text-ink-secondary hover:bg-surface-secondary/60 hover:text-ink transition-all"
          >
            <Download size={13} />
            Export .md
          </button>
        </div>
      </div>

      {/* Tags */}
      {metadata.tags?.length > 0 && (
        <div className="flex flex-shrink-0 flex-wrap gap-1.5 px-6 py-2 border-b border-border-subtle/50">
          {metadata.tags.map((tag) => (
            <span key={tag} className="rounded-full bg-accent-muted px-2.5 py-0.5 text-[11px] font-medium text-accent-dark">
              {tag}
            </span>
          ))}
          <span className="ml-auto text-[11px] text-ink-muted">
            {new Date(metadata.created_at).toLocaleString()}
          </span>
        </div>
      )}

      {/* Markdown content */}
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-3xl">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={{
              h1: ({ children }) => (
                <h1 className="mb-4 mt-8 font-display text-2xl font-semibold text-ink first:mt-0">{children}</h1>
              ),
              h2: ({ children }) => (
                <h2 className="mb-3 mt-6 font-display text-xl font-semibold text-ink">{children}</h2>
              ),
              h3: ({ children }) => (
                <h3 className="mb-2 mt-4 font-display text-base font-semibold text-ink">{children}</h3>
              ),
              p: ({ children }) => (
                <p className="mb-4 text-sm leading-relaxed text-ink">{children}</p>
              ),
              ul: ({ children }) => (
                <ul className="mb-4 list-disc space-y-1 pl-5 text-sm text-ink">{children}</ul>
              ),
              ol: ({ children }) => (
                <ol className="mb-4 list-decimal space-y-1 pl-5 text-sm text-ink">{children}</ol>
              ),
              li: ({ children }) => (
                <li className="text-sm text-ink">{children}</li>
              ),
              blockquote: ({ children }) => (
                <blockquote className="my-4 border-l-4 border-accent/40 pl-4 text-sm italic text-ink-secondary">
                  {children}
                </blockquote>
              ),
              code: ({ inline, className, children }: any) =>
                inline ? (
                  <code className="rounded bg-surface-secondary px-1.5 py-0.5 font-mono text-xs text-accent-dark">
                    {children}
                  </code>
                ) : (
                  <code className={className}>{children}</code>
                ),
              pre: ({ children }) => (
                <pre className="my-4 overflow-x-auto rounded-xl bg-surface-secondary p-4 text-xs">
                  {children}
                </pre>
              ),
              a: ({ href, children }) => (
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-0.5 text-accent hover:underline"
                >
                  {children}
                  <ExternalLink size={10} className="inline" />
                </a>
              ),
              table: ({ children }) => (
                <div className="my-4 overflow-x-auto rounded-xl glass">
                  <table className="w-full text-sm">{children}</table>
                </div>
              ),
              thead: ({ children }) => (
                <thead className="border-b border-border-subtle text-[11px] uppercase tracking-wider text-ink-muted">
                  {children}
                </thead>
              ),
              th: ({ children }) => (
                <th className="px-4 py-2 text-left font-medium">{children}</th>
              ),
              td: ({ children }) => (
                <td className="border-b border-border-subtle/40 px-4 py-2 text-ink">{children}</td>
              ),
              hr: () => <hr className="my-6 border-border-subtle" />,
            }}
          >
            {content}
          </ReactMarkdown>
        </div>
      </div>
    </motion.div>
  );
}
