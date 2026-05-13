'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Bell } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { listInsights } from '@/lib/journalApi'
import { useAppStore } from '@/stores/useAppStore'
import type { InsightCard } from '@/types/journal'
import { cn } from '@/lib/utils'

/* ------------------------------------------------------------------ */
/*  Helper: severity dot color                                         */
/* ------------------------------------------------------------------ */

function severityDotColor(severity: number) {
  if (severity < 0.4) return 'bg-emerald-500'
  if (severity < 0.7) return 'bg-amber-500'
  return 'bg-red-500'
}

/* ------------------------------------------------------------------ */
/*  NotificationBell                                                   */
/* ------------------------------------------------------------------ */

const POLL_INTERVAL = 60_000 // 60 seconds

export function NotificationBell() {
  const setActiveTab = useAppStore((s) => s.setActiveTab)

  const [open, setOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [recentInsights, setRecentInsights] = useState<InsightCard[]>([])
  const dropdownRef = useRef<HTMLDivElement>(null)
  const bellRef = useRef<HTMLButtonElement>(null)

  /* ---- Fetch unread insights ---- */
  const fetchUnread = useCallback(async () => {
    try {
      const data = await listInsights(true, 100)
      setUnreadCount(data.insights.length)
      setRecentInsights(data.insights.slice(0, 5))
    } catch {
      /* network error — keep stale count */
    }
  }, [])

  useEffect(() => {
    fetchUnread()
    const interval = setInterval(fetchUnread, POLL_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchUnread])

  /* ---- Close on outside click ---- */
  useEffect(() => {
    if (!open) return

    function handleClick(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        bellRef.current &&
        !bellRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  /* ---- Close on Escape key ---- */
  useEffect(() => {
    if (!open) return

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open])

  /* ---- Handle "See all" ---- */
  const handleSeeAll = () => {
    setOpen(false)
    setActiveTab('insights')
  }

  return (
    <div className="relative">
      {/* Bell button */}
      <button
        ref={bellRef}
        onClick={() => setOpen((prev) => !prev)}
        className={cn(
          'relative rounded-full p-2 text-ink-muted transition-all',
          'hover:bg-black/[0.04] dark:hover:bg-white/[0.06] hover:text-ink',
          open && 'bg-white/[0.06] text-ink',
        )}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
        aria-expanded={open}
        aria-haspopup="true"
      >
        <Bell size={18} strokeWidth={1.8} />

        {/* Badge */}
        {unreadCount > 0 && (
          <motion.span
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white shadow-sm"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </motion.span>
        )}
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            ref={dropdownRef}
            initial={{ opacity: 0, y: 4, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.95 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            className="absolute bottom-full left-1/2 z-50 mb-2 w-72 -translate-x-1/2 glass-elevated rounded-2xl shadow-glass-lg ring-1 ring-white/10"
            role="menu"
          >
            {/* Header */}
            <div className="border-b border-white/[0.06] px-4 py-3">
              <p className="text-xs font-semibold text-ink">
                Notifications
                {unreadCount > 0 && (
                  <span className="ml-1.5 rounded-full bg-red-500/15 px-1.5 py-0.5 text-[10px] font-bold text-red-400">
                    {unreadCount}
                  </span>
                )}
              </p>
            </div>

            {/* Items */}
            <div className="max-h-64 overflow-y-auto py-1">
              {recentInsights.length === 0 ? (
                <div className="px-4 py-6 text-center">
                  <p className="text-xs text-ink-muted">No unread notifications</p>
                </div>
              ) : (
                recentInsights.map((insight) => (
                  <div
                    key={insight.id}
                    className="flex items-start gap-3 px-4 py-2.5 transition-colors hover:bg-white/[0.03]"
                    role="menuitem"
                  >
                    <span
                      className={cn(
                        'mt-1.5 h-2 w-2 flex-shrink-0 rounded-full',
                        severityDotColor(insight.severity),
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-ink">{insight.title}</p>
                      <p className="text-[11px] text-ink-muted">
                        {new Date(insight.created_at).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Footer */}
            <div className="border-t border-white/[0.06] px-4 py-2.5">
              <button
                onClick={handleSeeAll}
                className="w-full rounded-lg py-1.5 text-center text-xs font-medium text-accent transition-colors hover:bg-white/[0.04]"
              >
                See all insights
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default NotificationBell
