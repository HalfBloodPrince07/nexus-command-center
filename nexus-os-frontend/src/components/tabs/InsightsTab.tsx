'use client'

import { useEffect, useState, useCallback } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  Sun,
  TrendingUp,
  Clock,
  CheckCircle2,
  X,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Inbox,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  listInsights,
  markInsightRead,
  dismissInsight,
  getTodayBriefing,
  listBriefings,
} from '@/lib/journalApi'
import type { InsightCard, BriefingData } from '@/types/journal'
import { cn } from '@/lib/utils'

/* ------------------------------------------------------------------ */
/*  Subtab definitions                                                 */
/* ------------------------------------------------------------------ */

const SUB_TABS = [
  { id: 'briefing' as const, label: 'Morning Briefing', icon: Sun },
  { id: 'patterns' as const, label: 'Patterns', icon: TrendingUp },
  { id: 'history' as const, label: 'History', icon: Clock },
]

type SubTabId = (typeof SUB_TABS)[number]['id']

/* ------------------------------------------------------------------ */
/*  Shared animation presets                                           */
/* ------------------------------------------------------------------ */

const fadeSlide = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.25, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
}

const stagger = {
  animate: { transition: { staggerChildren: 0.06 } },
}

const itemFade = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
}

/* ------------------------------------------------------------------ */
/*  Helper: severity color                                             */
/* ------------------------------------------------------------------ */

function severityColor(severity: number) {
  if (severity < 0.4) return { bar: 'bg-emerald-500', text: 'text-emerald-400', ring: 'ring-emerald-500/25' }
  if (severity < 0.7) return { bar: 'bg-amber-500', text: 'text-amber-400', ring: 'ring-amber-500/25' }
  return { bar: 'bg-red-500', text: 'text-red-400', ring: 'ring-red-500/25' }
}

function severityDotColor(severity: number) {
  if (severity < 0.4) return 'bg-emerald-500'
  if (severity < 0.7) return 'bg-amber-500'
  return 'bg-red-500'
}

/* ------------------------------------------------------------------ */
/*  Sub-component: MorningBriefing                                     */
/* ------------------------------------------------------------------ */

function MorningBriefing() {
  const [briefing, setBriefing] = useState<BriefingData | null | undefined>(undefined)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getTodayBriefing()
      .then((data) => {
        if (!cancelled) setBriefing(data.briefing ?? null)
      })
      .catch(() => {
        if (!cancelled) setBriefing(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center p-10">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.2, ease: 'linear' }}
          className="h-6 w-6 rounded-full border-2 border-transparent border-t-accent"
        />
      </div>
    )
  }

  if (!briefing) {
    return (
      <motion.div {...fadeSlide} className="flex flex-1 flex-col items-center justify-center gap-4 p-10">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 ring-1 ring-white/10">
          <Inbox size={28} className="text-ink-muted" strokeWidth={1.5} />
        </div>
        <p className="text-sm text-ink-muted">No briefing yet today</p>
        <p className="text-xs text-ink-muted/60">
          Your morning briefing will appear here once generated.
        </p>
      </motion.div>
    )
  }

  return (
    <motion.div {...fadeSlide} className="flex-1 overflow-y-auto p-4 sm:p-6">
      {/* Hero card */}
      <div className="glass-elevated shadow-glass rounded-2xl p-6 sm:p-8">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-primary shadow-glow-accent">
            <Sun size={20} className="text-white" strokeWidth={1.8} />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-ink">Morning Briefing</h2>
            <p className="text-xs text-ink-muted">
              {new Date(briefing.created_at).toLocaleDateString(undefined, {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>
        </div>

        {/* Mood summary */}
        {briefing.mood_summary && (
          <div className="mb-5 rounded-xl bg-white/[0.03] px-4 py-3 ring-1 ring-white/[0.06]">
            <p className="text-xs font-medium uppercase tracking-wider text-ink-muted">Mood</p>
            <p className="mt-1 text-sm text-ink-secondary">{briefing.mood_summary}</p>
          </div>
        )}

        {/* Body markdown */}
        <div className="prose prose-sm prose-invert max-w-none text-ink-secondary prose-headings:text-ink prose-strong:text-ink prose-a:text-accent">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{briefing.body_md}</ReactMarkdown>
        </div>
      </div>
    </motion.div>
  )
}

/* ------------------------------------------------------------------ */
/*  Sub-component: Patterns                                            */
/* ------------------------------------------------------------------ */

function Patterns() {
  const [insights, setInsights] = useState<InsightCard[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listInsights(false, 50)
      setInsights(data.insights)
    } catch {
      /* swallow */
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleMarkRead = async (id: string) => {
    await markInsightRead(id)
    setInsights((prev) => prev.map((i) => (i.id === id ? { ...i, read_at: new Date().toISOString() } : i)))
  }

  const handleDismiss = async (id: string) => {
    await dismissInsight(id)
    setInsights((prev) => prev.filter((i) => i.id !== id))
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center p-10">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.2, ease: 'linear' }}
          className="h-6 w-6 rounded-full border-2 border-transparent border-t-accent"
        />
      </div>
    )
  }

  if (insights.length === 0) {
    return (
      <motion.div {...fadeSlide} className="flex flex-1 flex-col items-center justify-center gap-4 p-10">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 ring-1 ring-white/10">
          <Sparkles size={28} className="text-ink-muted" strokeWidth={1.5} />
        </div>
        <p className="text-sm text-ink-muted">No insights yet</p>
        <p className="text-xs text-ink-muted/60">
          Patterns and insights will appear here as the system learns.
        </p>
      </motion.div>
    )
  }

  return (
    <motion.div
      variants={stagger}
      initial="initial"
      animate="animate"
      className="flex-1 space-y-3 overflow-y-auto p-4 sm:p-6"
    >
      {insights.map((insight) => {
        const sev = severityColor(insight.severity)
        return (
          <motion.div
            key={insight.id}
            variants={itemFade}
            layout
            className="glass-elevated shadow-glass rounded-2xl p-5 transition-all"
          >
            {/* Header row */}
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-ink">{insight.title}</h3>
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ring-1 ring-inset',
                      'bg-white/5',
                      sev.ring,
                      sev.text,
                    )}
                  >
                    {insight.category}
                  </span>
                </div>
                <p className="text-[11px] text-ink-muted">
                  {new Date(insight.created_at).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                </p>
              </div>

              {/* Actions */}
              <div className="flex flex-shrink-0 items-center gap-1.5">
                {!insight.read_at && (
                  <button
                    onClick={() => handleMarkRead(insight.id)}
                    className="rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-white/5 hover:text-emerald-400"
                    aria-label="Mark as read"
                    title="Mark Read"
                  >
                    <CheckCircle2 size={16} strokeWidth={1.8} />
                  </button>
                )}
                <button
                  onClick={() => handleDismiss(insight.id)}
                  className="rounded-lg p-1.5 text-ink-muted transition-colors hover:bg-white/5 hover:text-red-400"
                  aria-label="Dismiss insight"
                  title="Dismiss"
                >
                  <X size={16} strokeWidth={1.8} />
                </button>
              </div>
            </div>

            {/* Severity bar */}
            <div className="mb-3">
              <div className="flex items-center justify-between text-[11px] text-ink-muted">
                <span>Severity</span>
                <span>{Math.round(insight.severity * 100)}%</span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                <motion.div
                  className={cn('h-full rounded-full', sev.bar)}
                  initial={{ width: 0 }}
                  animate={{ width: `${insight.severity * 100}%` }}
                  transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
                />
              </div>
            </div>

            {/* Body */}
            <div className="prose prose-sm prose-invert max-w-none text-ink-secondary prose-headings:text-ink prose-strong:text-ink prose-a:text-accent">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{insight.body_md}</ReactMarkdown>
            </div>
          </motion.div>
        )
      })}
    </motion.div>
  )
}

/* ------------------------------------------------------------------ */
/*  Sub-component: BriefingHistory                                     */
/* ------------------------------------------------------------------ */

function BriefingHistory() {
  const [briefings, setBriefings] = useState<BriefingData[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    listBriefings()
      .then((data) => {
        if (!cancelled) setBriefings(data.briefings)
      })
      .catch(() => {
        /* swallow */
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center p-10">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1.2, ease: 'linear' }}
          className="h-6 w-6 rounded-full border-2 border-transparent border-t-accent"
        />
      </div>
    )
  }

  if (briefings.length === 0) {
    return (
      <motion.div {...fadeSlide} className="flex flex-1 flex-col items-center justify-center gap-4 p-10">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/5 ring-1 ring-white/10">
          <Clock size={28} className="text-ink-muted" strokeWidth={1.5} />
        </div>
        <p className="text-sm text-ink-muted">No briefing history</p>
      </motion.div>
    )
  }

  return (
    <motion.div
      variants={stagger}
      initial="initial"
      animate="animate"
      className="flex-1 space-y-2 overflow-y-auto p-4 sm:p-6"
    >
      {briefings.map((b) => {
        const isExpanded = expandedId === b.id
        const preview = b.body_md.length > 200 ? b.body_md.slice(0, 200) + '...' : b.body_md

        return (
          <motion.div
            key={b.id}
            variants={itemFade}
            layout
            className="glass-elevated shadow-glass rounded-2xl transition-all"
          >
            <button
              onClick={() => setExpandedId(isExpanded ? null : b.id)}
              className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left"
              aria-expanded={isExpanded}
            >
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-ink-muted">
                  {new Date(b.created_at).toLocaleDateString(undefined, {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                  })}
                </p>
                {!isExpanded && (
                  <p className="mt-1 truncate text-sm text-ink-secondary">{preview}</p>
                )}
              </div>
              <span className="flex-shrink-0 text-ink-muted">
                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </span>
            </button>

            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
                  className="overflow-hidden"
                >
                  <div className="border-t border-white/[0.06] px-5 pb-5 pt-4">
                    <div className="prose prose-sm prose-invert max-w-none text-ink-secondary prose-headings:text-ink prose-strong:text-ink prose-a:text-accent">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{b.body_md}</ReactMarkdown>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )
      })}
    </motion.div>
  )
}

/* ------------------------------------------------------------------ */
/*  Main: InsightsTab                                                  */
/* ------------------------------------------------------------------ */

export default function InsightsTab() {
  const [activeSubTab, setActiveSubTab] = useState<SubTabId>('briefing')

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Pill subtab bar */}
      <div className="flex flex-shrink-0 items-center gap-2 px-4 pt-4 pb-2 sm:px-6">
        {SUB_TABS.map(({ id, label }) => {
          const active = activeSubTab === id
          return (
            <button
              key={id}
              onClick={() => setActiveSubTab(id)}
              className={cn(
                'relative rounded-full px-4 py-1.5 text-sm font-medium transition-all duration-200',
                active
                  ? 'bg-gradient-primary text-white shadow-glow-accent'
                  : 'text-ink-secondary hover:text-ink hover:bg-white/5',
              )}
            >
              {label}
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div className="min-h-0 flex-1 flex flex-col overflow-hidden">
        <AnimatePresence mode="wait">
          <motion.div
            key={activeSubTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
            className="flex flex-1 flex-col h-full"
          >
            {activeSubTab === 'briefing' && <MorningBriefing />}
            {activeSubTab === 'patterns' && <Patterns />}
            {activeSubTab === 'history' && <BriefingHistory />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
