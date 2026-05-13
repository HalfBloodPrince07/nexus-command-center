'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useJournalStore } from '@/stores/useJournalStore'
import { cn } from '@/lib/utils'
import CalendarHeatmap from 'react-calendar-heatmap'
import {
  PenLine,
  Clock,
  CalendarDays,
  Lightbulb,
  Scale,
  Save,
  Plus,
  ChevronDown,
  Loader2,
  Trash2,
  CheckCircle2,
  AlertCircle,
  BarChart3,
} from 'lucide-react'
import type { JournalEntry, PatternInsight, Decision } from '@/types/journal'

/* -------------------------------------------------------------------------- */
/*  Constants                                                                 */
/* -------------------------------------------------------------------------- */

const SUBTABS = [
  { id: 'new-entry', label: 'New Entry', icon: PenLine },
  { id: 'timeline', label: 'Timeline', icon: Clock },
  { id: 'mood-calendar', label: 'Mood Calendar', icon: CalendarDays },
  { id: 'insights', label: 'Insights', icon: Lightbulb },
  { id: 'decisions', label: 'Decisions', icon: Scale },
] as const

type SubtabId = (typeof SUBTABS)[number]['id']

const DRAFT_KEY = 'nexus-journal-draft'
const AUTOSAVE_MS = 4000
const PAGE_SIZE = 20

const EMOTION_COLORS: Record<string, string> = {
  joy: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  sadness: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  anger: 'bg-red-500/20 text-red-300 border-red-500/30',
  fear: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  surprise: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  disgust: 'bg-green-500/20 text-green-300 border-green-500/30',
  trust: 'bg-teal-500/20 text-teal-300 border-teal-500/30',
  anticipation: 'bg-orange-500/20 text-orange-300 border-orange-500/30',
  love: 'bg-pink-500/20 text-pink-300 border-pink-500/30',
  calm: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  anxiety: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
  hope: 'bg-sky-500/20 text-sky-300 border-sky-500/30',
}

function getEmotionClass(emotion: string): string {
  const key = emotion.toLowerCase()
  return EMOTION_COLORS[key] ?? 'bg-white/10 text-ink-secondary border-white/10'
}

/** Maps a mood score (1-10) to a CSS gradient color stop */
function moodScoreColor(score: number): string {
  if (score <= 2) return '#ef4444'      // red
  if (score <= 4) return '#f59e0b'      // amber
  if (score <= 6) return '#eab308'      // yellow
  if (score <= 8) return '#22c55e'      // green
  return '#10b981'                       // emerald
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatDateShort(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/* -------------------------------------------------------------------------- */
/*  Shared animation variants                                                 */
/* -------------------------------------------------------------------------- */

const fadeSlide = {
  initial: { opacity: 0, y: 12, filter: 'blur(4px)' },
  animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
  exit: { opacity: 0, y: -8, filter: 'blur(4px)' },
}

const staggerContainer = {
  animate: { transition: { staggerChildren: 0.04 } },
}

const staggerItem = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
}

/* -------------------------------------------------------------------------- */
/*  Subtab: New Entry                                                         */
/* -------------------------------------------------------------------------- */

function NewEntryTab() {
  const { createEntry, loading, entries } = useJournalStore()
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [saved, setSaved] = useState(false)
  const [lastSavedEntry, setLastSavedEntry] = useState<JournalEntry | null>(null)
  const lastAutosave = useRef<string>('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Restore draft from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(DRAFT_KEY)
      if (raw) {
        const draft = JSON.parse(raw)
        if (draft.title) setTitle(draft.title)
        if (draft.body) setBody(draft.body)
      }
    } catch {
      // ignore corrupt draft
    }
  }, [])

  // Autosave draft every 4 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      const current = JSON.stringify({ title, body })
      if (current !== lastAutosave.current && (title || body)) {
        localStorage.setItem(DRAFT_KEY, current)
        lastAutosave.current = current
      }
    }, AUTOSAVE_MS)
    return () => clearInterval(interval)
  }, [title, body])

  const handleSave = useCallback(async () => {
    if (!body.trim()) return
    await createEntry(body.trim(), title.trim() || undefined)
    localStorage.removeItem(DRAFT_KEY)
    lastAutosave.current = ''

    // Grab the newly created entry (first in the list after createEntry reloads)
    const latest = useJournalStore.getState().entries[0] ?? null
    setLastSavedEntry(latest)
    setSaved(true)
    setTitle('')
    setBody('')
  }, [body, title, createEntry])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault()
        handleSave()
      }
    },
    [handleSave]
  )

  return (
    <motion.div {...fadeSlide} className="space-y-4">
      {/* Title field */}
      <div>
        <label htmlFor="journal-title" className="block text-xs text-ink-muted mb-1.5 uppercase tracking-wider">
          Title (optional)
        </label>
        <input
          id="journal-title"
          type="text"
          value={title}
          onChange={(e) => { setTitle(e.target.value); setSaved(false) }}
          placeholder="Give this entry a name..."
          className={cn(
            'w-full px-4 py-2.5 rounded-xl text-sm text-ink bg-white/5',
            'border border-white/10 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/30',
            'placeholder:text-ink-muted/50 outline-none transition-all duration-200',
          )}
        />
      </div>

      {/* Body textarea */}
      <div>
        <label htmlFor="journal-body" className="block text-xs text-ink-muted mb-1.5 uppercase tracking-wider">
          What is on your mind?
        </label>
        <textarea
          ref={textareaRef}
          id="journal-body"
          value={body}
          onChange={(e) => { setBody(e.target.value); setSaved(false) }}
          onKeyDown={handleKeyDown}
          placeholder="Write freely. Your thoughts are private and will be analyzed for mood and patterns..."
          rows={10}
          className={cn(
            'w-full px-4 py-3 rounded-xl text-sm text-ink bg-white/5 resize-y min-h-[180px]',
            'border border-white/10 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/30',
            'placeholder:text-ink-muted/50 outline-none transition-all duration-200',
            'leading-relaxed',
          )}
        />
        <p className="text-[11px] text-ink-muted mt-1.5">
          Drafts auto-save every {AUTOSAVE_MS / 1000}s &middot; <kbd className="px-1 py-0.5 rounded bg-white/5 border border-white/10 text-[10px]">Ctrl+Enter</kbd> to save
        </p>
      </div>

      {/* Save button */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={!body.trim() || loading}
          className={cn(
            'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
            'bg-gradient-primary text-white shadow-glass',
            'hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]',
            'disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100',
          )}
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save Entry
        </button>

        {saved && !loading && (
          <motion.span
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            className="text-emerald-400 text-sm flex items-center gap-1.5"
          >
            <CheckCircle2 className="w-4 h-4" />
            Saved
          </motion.span>
        )}
      </div>

      {/* Mood card after save */}
      <AnimatePresence>
        {saved && lastSavedEntry?.mood && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            className="glass p-5 rounded-2xl space-y-3"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Mood Analysis</h3>
              <div className="flex items-center gap-2">
                <div
                  className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold"
                  style={{ backgroundColor: moodScoreColor(lastSavedEntry.mood.score) + '30', color: moodScoreColor(lastSavedEntry.mood.score) }}
                >
                  {lastSavedEntry.mood.score}
                </div>
                <span className="text-xs text-ink-muted">/10</span>
              </div>
            </div>

            {/* Mood bar */}
            <div className="h-2 rounded-full bg-white/5 overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${lastSavedEntry.mood.score * 10}%` }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
                className="h-full rounded-full"
                style={{ background: `linear-gradient(90deg, #ef4444, ${moodScoreColor(lastSavedEntry.mood.score)})` }}
              />
            </div>

            {/* Emotion chips */}
            {lastSavedEntry.mood.emotions.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {lastSavedEntry.mood.emotions.map((em) => (
                  <span
                    key={em}
                    className={cn(
                      'px-2.5 py-1 rounded-full text-xs font-medium border',
                      getEmotionClass(em),
                    )}
                  >
                    {em}
                  </span>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Subtab: Timeline                                                          */
/* -------------------------------------------------------------------------- */

function TimelineTab() {
  const { entries, loadEntries, loading } = useJournalStore()
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(true)
  const loadedRef = useRef(false)

  useEffect(() => {
    if (!loadedRef.current) {
      loadedRef.current = true
      loadEntries(PAGE_SIZE, 0)
    }
  }, [loadEntries])

  // Determine if there might be more entries
  useEffect(() => {
    if (entries.length < offset + PAGE_SIZE) {
      setHasMore(false)
    }
  }, [entries.length, offset])

  const handleLoadMore = useCallback(async () => {
    const next = offset + PAGE_SIZE
    setOffset(next)
    await loadEntries(PAGE_SIZE, next)
    setHasMore(useJournalStore.getState().entries.length >= next + PAGE_SIZE)
  }, [offset, loadEntries])

  if (loading && entries.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-ink-muted" />
      </div>
    )
  }

  if (!loading && entries.length === 0) {
    return (
      <motion.div {...fadeSlide} className="flex flex-col items-center justify-center py-20 text-center">
        <PenLine className="w-10 h-10 text-ink-muted/40 mb-3" />
        <p className="text-ink-secondary text-sm">No journal entries yet.</p>
        <p className="text-ink-muted text-xs mt-1">Write your first entry to get started.</p>
      </motion.div>
    )
  }

  return (
    <motion.div {...fadeSlide} className="space-y-3">
      <motion.div variants={staggerContainer} initial="initial" animate="animate" className="space-y-3">
        {entries.map((entry) => (
          <TimelineCard key={entry.id} entry={entry} />
        ))}
      </motion.div>

      {hasMore && (
        <div className="flex justify-center pt-2">
          <button
            onClick={handleLoadMore}
            disabled={loading}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-xl text-sm text-ink-secondary',
              'border border-white/10 hover:border-white/20 hover:text-ink',
              'transition-all duration-200',
              'disabled:opacity-40',
            )}
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ChevronDown className="w-4 h-4" />}
            Load More
          </button>
        </div>
      )}
    </motion.div>
  )
}

function TimelineCard({ entry }: { entry: JournalEntry }) {
  const [expanded, setExpanded] = useState(false)
  const truncated = entry.body_md.length > 150
  const displayBody = expanded ? entry.body_md : entry.body_md.slice(0, 150) + (truncated ? '...' : '')

  return (
    <motion.div
      variants={staggerItem}
      className={cn(
        'glass p-4 rounded-2xl space-y-2.5 cursor-pointer',
        'hover:border-white/20 transition-colors duration-200',
      )}
      onClick={() => truncated && setExpanded(!expanded)}
    >
      {/* Header: date + title */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {entry.title && (
            <h3 className="text-sm font-semibold text-ink truncate">{entry.title}</h3>
          )}
          <p className="text-xs text-ink-muted">{formatDate(entry.created_at)}</p>
        </div>

        {/* Mood score badge */}
        {entry.mood && (
          <div
            className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold"
            style={{
              backgroundColor: moodScoreColor(entry.mood.score) + '25',
              color: moodScoreColor(entry.mood.score),
            }}
          >
            {entry.mood.score}
          </div>
        )}
      </div>

      {/* Mood color bar */}
      {entry.mood && (
        <div className="h-1 rounded-full bg-white/5 overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${entry.mood.score * 10}%`,
              background: `linear-gradient(90deg, #ef4444, ${moodScoreColor(entry.mood.score)})`,
            }}
          />
        </div>
      )}

      {/* Body */}
      <p className="text-sm text-ink-secondary leading-relaxed whitespace-pre-line">{displayBody}</p>

      {truncated && (
        <button className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors">
          {expanded ? 'Show less' : 'Read more'}
        </button>
      )}

      {/* Emotion chips */}
      {entry.mood && entry.mood.emotions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {entry.mood.emotions.map((em) => (
            <span
              key={em}
              className={cn(
                'px-2 py-0.5 rounded-full text-[11px] font-medium border',
                getEmotionClass(em),
              )}
            >
              {em}
            </span>
          ))}
        </div>
      )}
    </motion.div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Subtab: Mood Calendar                                                     */
/* -------------------------------------------------------------------------- */

function MoodCalendarTab() {
  const { moodCalendar, loadMoodCalendar, loading } = useJournalStore()
  const currentYear = new Date().getFullYear()
  const [year, setYear] = useState(currentYear)
  const loadedYear = useRef<number | null>(null)

  useEffect(() => {
    if (loadedYear.current !== year) {
      loadedYear.current = year
      loadMoodCalendar(year)
    }
  }, [year, loadMoodCalendar])

  // Extract heatmap values from calendar chart payload
  const values: { date: string; count: number }[] = (() => {
    if (!moodCalendar?.series?.[0]?.data) return []
    return moodCalendar.series[0].data.map((point: Record<string, unknown>) => ({
      date: String(point.date ?? point.x ?? ''),
      count: Number(point.score ?? point.y ?? point.value ?? 0),
    }))
  })()

  const startDate = new Date(`${year}-01-01`)
  const endDate = new Date(`${year}-12-31`)

  // Color class based on mood score
  const classForValue = (value: { date?: string; count?: number } | undefined) => {
    if (!value || !value.count) return 'fill-white/[0.04]'
    const s = value.count
    if (s <= 2) return 'fill-red-500/70'
    if (s <= 4) return 'fill-orange-500/60'
    if (s <= 5) return 'fill-yellow-500/50'
    if (s <= 7) return 'fill-emerald-500/50'
    if (s <= 9) return 'fill-emerald-400/70'
    return 'fill-emerald-300/80'
  }

  return (
    <motion.div {...fadeSlide} className="space-y-4">
      {/* Year selector */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setYear((y) => y - 1)}
          className="px-3 py-1.5 rounded-lg text-xs text-ink-secondary border border-white/10 hover:border-white/20 hover:text-ink transition-all"
        >
          {year - 1}
        </button>
        <span className="text-sm font-semibold text-ink tabular-nums">{year}</span>
        <button
          onClick={() => setYear((y) => Math.min(y + 1, currentYear))}
          disabled={year >= currentYear}
          className={cn(
            'px-3 py-1.5 rounded-lg text-xs text-ink-secondary border border-white/10 hover:border-white/20 hover:text-ink transition-all',
            'disabled:opacity-30 disabled:cursor-not-allowed',
          )}
        >
          {year + 1}
        </button>
      </div>

      {/* Heatmap */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-ink-muted" />
        </div>
      ) : (
        <div className="glass p-4 rounded-2xl overflow-x-auto">
          <div className="min-w-[680px]">
            <CalendarHeatmap
              startDate={startDate}
              endDate={endDate}
              values={values}
              classForValue={classForValue}
              showWeekdayLabels
              gutterSize={3}
              titleForValue={(value) =>
                value ? `${value.date}: mood ${value.count}/10` : 'No entry'
              }
            />
          </div>

          {/* Legend */}
          <div className="flex items-center justify-end gap-1.5 mt-3 text-[11px] text-ink-muted">
            <span>Low</span>
            {['fill-red-500/70', 'fill-orange-500/60', 'fill-yellow-500/50', 'fill-emerald-500/50', 'fill-emerald-400/70', 'fill-emerald-300/80'].map(
              (cls, i) => (
                <svg key={i} width="12" height="12" className="rounded-sm">
                  <rect width="12" height="12" rx="2" className={cls} />
                </svg>
              )
            )}
            <span>High</span>
          </div>
        </div>
      )}
    </motion.div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Subtab: Insights                                                          */
/* -------------------------------------------------------------------------- */

function InsightsTab() {
  const { insights, loadInsights, loading } = useJournalStore()
  const loadedRef = useRef(false)

  useEffect(() => {
    if (!loadedRef.current) {
      loadedRef.current = true
      loadInsights()
    }
  }, [loadInsights])

  if (loading && insights.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-ink-muted" />
      </div>
    )
  }

  if (!loading && insights.length === 0) {
    return (
      <motion.div {...fadeSlide} className="flex flex-col items-center justify-center py-20 text-center">
        <Lightbulb className="w-10 h-10 text-ink-muted/40 mb-3" />
        <p className="text-ink-secondary text-sm">No insights yet.</p>
        <p className="text-ink-muted text-xs mt-1">Keep journaling and patterns will emerge.</p>
      </motion.div>
    )
  }

  return (
    <motion.div {...fadeSlide}>
      <motion.div variants={staggerContainer} initial="initial" animate="animate" className="grid gap-3 sm:grid-cols-2">
        {insights.map((insight, idx) => (
          <InsightCard key={idx} insight={insight} />
        ))}
      </motion.div>
    </motion.div>
  )
}

function InsightCard({ insight }: { insight: PatternInsight }) {
  const pct = Math.round(insight.confidence * 100)

  return (
    <motion.div
      variants={staggerItem}
      className="glass p-4 rounded-2xl space-y-3 hover:border-white/20 transition-colors duration-200"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink leading-snug">{insight.title}</h3>
        <span className="flex-shrink-0 text-xs text-ink-muted tabular-nums">{pct}%</span>
      </div>

      <p className="text-xs text-ink-secondary leading-relaxed">{insight.description}</p>

      {/* Confidence bar */}
      <div className="space-y-1">
        <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-700"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="flex items-center justify-between text-[11px] text-ink-muted">
          <span>Confidence</span>
          <span className="flex items-center gap-1">
            <BarChart3 className="w-3 h-3" />
            {insight.evidence_count} evidence
          </span>
        </div>
      </div>
    </motion.div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Subtab: Decisions                                                         */
/* -------------------------------------------------------------------------- */

function DecisionsTab() {
  const { decisions, loadDecisions, startDecision, loading } = useJournalStore()
  const [showForm, setShowForm] = useState(false)
  const [question, setQuestion] = useState('')
  const loadedRef = useRef(false)

  useEffect(() => {
    if (!loadedRef.current) {
      loadedRef.current = true
      loadDecisions()
    }
  }, [loadDecisions])

  const handleSubmit = useCallback(async () => {
    if (!question.trim()) return
    await startDecision(question.trim())
    setQuestion('')
    setShowForm(false)
  }, [question, startDecision])

  return (
    <motion.div {...fadeSlide} className="space-y-4">
      {/* New decision button / form */}
      <AnimatePresence mode="wait">
        {!showForm ? (
          <motion.button
            key="btn"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowForm(true)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium',
              'bg-gradient-primary text-white shadow-glass',
              'hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]',
              'transition-all duration-200',
            )}
          >
            <Plus className="w-4 h-4" />
            New Decision
          </motion.button>
        ) : (
          <motion.div
            key="form"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="glass p-4 rounded-2xl space-y-3"
          >
            <label htmlFor="decision-q" className="block text-xs text-ink-muted uppercase tracking-wider">
              What decision do you need help with?
            </label>
            <textarea
              id="decision-q"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Describe the decision or dilemma you are facing..."
              rows={4}
              className={cn(
                'w-full px-4 py-3 rounded-xl text-sm text-ink bg-white/5 resize-y min-h-[100px]',
                'border border-white/10 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/30',
                'placeholder:text-ink-muted/50 outline-none transition-all duration-200 leading-relaxed',
              )}
            />
            <div className="flex items-center gap-2">
              <button
                onClick={handleSubmit}
                disabled={!question.trim() || loading}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium',
                  'bg-gradient-primary text-white shadow-glass',
                  'hover:shadow-lg active:scale-[0.98]',
                  'disabled:opacity-40 disabled:cursor-not-allowed',
                  'transition-all duration-200',
                )}
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Scale className="w-4 h-4" />}
                Analyze
              </button>
              <button
                onClick={() => { setShowForm(false); setQuestion('') }}
                className="px-4 py-2 rounded-xl text-sm text-ink-secondary hover:text-ink transition-colors"
              >
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Decisions list */}
      {loading && decisions.length === 0 ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-ink-muted" />
        </div>
      ) : decisions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Scale className="w-10 h-10 text-ink-muted/40 mb-3" />
          <p className="text-ink-secondary text-sm">No decisions yet.</p>
          <p className="text-ink-muted text-xs mt-1">Use the button above to analyze a decision.</p>
        </div>
      ) : (
        <motion.div variants={staggerContainer} initial="initial" animate="animate" className="space-y-3">
          {decisions.map((decision) => (
            <DecisionCard key={decision.id} decision={decision} />
          ))}
        </motion.div>
      )}
    </motion.div>
  )
}

const STATUS_CONFIG: Record<Decision['status'], { label: string; color: string; icon: typeof CheckCircle2 }> = {
  pending: { label: 'Pending', color: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30', icon: Clock },
  analyzing: { label: 'Analyzing', color: 'bg-blue-500/20 text-blue-300 border-blue-500/30', icon: Loader2 },
  complete: { label: 'Complete', color: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30', icon: CheckCircle2 },
  recorded_outcome: { label: 'Outcome Recorded', color: 'bg-violet-500/20 text-violet-300 border-violet-500/30', icon: BarChart3 },
}

function DecisionCard({ decision }: { decision: Decision }) {
  const cfg = STATUS_CONFIG[decision.status]
  const Icon = cfg.icon

  return (
    <motion.div
      variants={staggerItem}
      className="glass p-4 rounded-2xl space-y-3 hover:border-white/20 transition-colors duration-200"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-ink font-medium leading-snug flex-1">{decision.question}</p>
        <span
          className={cn(
            'flex-shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border',
            cfg.color,
          )}
        >
          <Icon className={cn('w-3 h-3', decision.status === 'analyzing' && 'animate-spin')} />
          {cfg.label}
        </span>
      </div>

      <p className="text-xs text-ink-muted">{formatDate(decision.created_at)}</p>

      {/* Show analysis for completed decisions */}
      {(decision.status === 'complete' || decision.status === 'recorded_outcome') && decision.analysis && (
        <div className="space-y-2 pt-1 border-t border-white/5">
          <p className="text-xs text-ink-secondary leading-relaxed">
            <span className="font-semibold text-ink">Recommendation:</span> {decision.analysis.recommendation}
          </p>

          {/* Confidence */}
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1 rounded-full bg-white/5 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
                style={{ width: `${Math.round(decision.analysis.confidence * 100)}%` }}
              />
            </div>
            <span className="text-[11px] text-ink-muted tabular-nums">
              {Math.round(decision.analysis.confidence * 100)}%
            </span>
          </div>

          {decision.analysis.caveats && (
            <p className="text-[11px] text-ink-muted flex items-start gap-1.5">
              <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0 text-amber-400" />
              {decision.analysis.caveats}
            </p>
          )}
        </div>
      )}

      {/* Outcome */}
      {decision.status === 'recorded_outcome' && decision.outcome && (
        <div className="pt-1 border-t border-white/5">
          <p className="text-xs text-ink-secondary">
            <span className="font-semibold text-ink">Outcome:</span> {decision.outcome}
          </p>
        </div>
      )}
    </motion.div>
  )
}

/* -------------------------------------------------------------------------- */
/*  Main: JournalTab                                                          */
/* -------------------------------------------------------------------------- */

export default function JournalTab() {
  const [activeTab, setActiveTab] = useState<SubtabId>('new-entry')

  return (
    <div className="h-full flex flex-col">
      {/* Pill navigation */}
      <div className="flex-shrink-0 px-1 pb-4">
        <nav
          className="flex items-center gap-1.5 overflow-x-auto scrollbar-none py-1"
          role="tablist"
          aria-label="Journal sections"
        >
          {SUBTABS.map(({ id, label, icon: Icon }) => {
            const isActive = activeTab === id
            return (
              <button
                key={id}
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(id)}
                className={cn(
                  'flex items-center gap-1.5 px-3.5 py-2 rounded-full text-sm font-medium whitespace-nowrap',
                  'transition-all duration-200 flex-shrink-0',
                  isActive
                    ? 'bg-gradient-primary text-white shadow-glass'
                    : 'text-ink-secondary hover:text-ink',
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Content area */}
      <div className="flex-1 min-h-0 overflow-y-auto scrollbar-thin px-1 pb-4">
        <AnimatePresence mode="wait">
          {activeTab === 'new-entry' && (
            <motion.div key="new-entry" {...fadeSlide} transition={{ duration: 0.2 }}>
              <NewEntryTab />
            </motion.div>
          )}
          {activeTab === 'timeline' && (
            <motion.div key="timeline" {...fadeSlide} transition={{ duration: 0.2 }}>
              <TimelineTab />
            </motion.div>
          )}
          {activeTab === 'mood-calendar' && (
            <motion.div key="mood-calendar" {...fadeSlide} transition={{ duration: 0.2 }}>
              <MoodCalendarTab />
            </motion.div>
          )}
          {activeTab === 'insights' && (
            <motion.div key="insights" {...fadeSlide} transition={{ duration: 0.2 }}>
              <InsightsTab />
            </motion.div>
          )}
          {activeTab === 'decisions' && (
            <motion.div key="decisions" {...fadeSlide} transition={{ duration: 0.2 }}>
              <DecisionsTab />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
