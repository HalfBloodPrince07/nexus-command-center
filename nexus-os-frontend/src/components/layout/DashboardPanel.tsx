'use client'
import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ChevronRight, ChevronLeft, Settings, Brain, Activity,
  Thermometer, MonitorDot, Clock, Database, GitBranch, ChevronRight as ChevronRightIcon,
} from 'lucide-react'
import { useAppStore } from '@/stores/useAppStore'
import { useMemoryStore } from '@/stores/useMemoryStore'
import GlassCard from '../ui/GlassCard'
import { cn } from '@/lib/utils'
import { ResourceAvatarOrbDynamic } from '../three/ResourceAvatarOrb'

// ─── MetricBar color config ───────────────────────────────────────────────────
const BAR_PALETTE: Record<string, { g1: string; g2: string; glow: string }> = {
  indigo: { g1: '#818cf8', g2: '#4f46e5', glow: 'rgba(99,102,241,0.55)'  },
  violet: { g1: '#c4b5fd', g2: '#7c3aed', glow: 'rgba(139,92,246,0.55)' },
  teal:   { g1: '#5eead4', g2: '#0f766e', glow: 'rgba(20,184,166,0.55)'  },
  pink:   { g1: '#f9a8d4', g2: '#be185d', glow: 'rgba(236,72,153,0.55)'  },
}

function getBarStyle(pct: number, color: string): React.CSSProperties {
  if (pct >= 80) return {
    background: 'linear-gradient(90deg, #f87171 0%, #dc2626 100%)',
    boxShadow: '0 0 14px rgba(239,68,68,0.7), 0 0 4px rgba(239,68,68,0.4)',
    transition: 'background 0.5s ease, box-shadow 0.5s ease',
  }
  if (pct >= 50) return {
    background: 'linear-gradient(90deg, #fcd34d 0%, #d97706 100%)',
    boxShadow: '0 0 10px rgba(245,158,11,0.6)',
    transition: 'background 0.5s ease, box-shadow 0.5s ease',
  }
  const p = BAR_PALETTE[color] ?? BAR_PALETTE.indigo
  return {
    background: `linear-gradient(90deg, ${p.g1} 0%, ${p.g2} 100%)`,
    boxShadow: `0 0 8px ${p.glow}`,
    transition: 'background 0.5s ease, box-shadow 0.5s ease',
  }
}

// ─── MetricBar ────────────────────────────────────────────────────────────────
const MetricBar = ({
  label, value, suffix = '%', color = 'indigo', detail,
}: {
  label: string
  value: number | null
  suffix?: string
  color?: 'indigo' | 'violet' | 'teal' | 'pink'
  detail?: string
}) => {
  const pct    = Math.min(value ?? 0, 100)
  const isNull = value === null
  const isHigh = pct >= 80
  const isMid  = pct >= 50 && pct < 80

  // shimmer speed: fast when critical, moderate when warning, slow when idle
  const shimmerDuration = isHigh ? 1.1 : isMid ? 1.8 : 3.2
  const shimmerDelay    = isHigh ? 0.1 : isMid ? 0.4 : 1.0

  return (
    <div className="space-y-1.5">
      {/* label + value */}
      <div className="flex justify-between text-[11px] font-medium">
        <span className="text-ink-secondary">{label}</span>
        <div className="flex items-center gap-1.5">
          {detail && <span className="text-ink-muted">{detail}</span>}
          <motion.span
            key={Math.round(pct)}           // re-animate on value change
            initial={{ scale: 0.85, opacity: 0.6 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.25 }}
            className={cn(
              'tabular-nums font-semibold',
              isNull ? 'text-ink-muted font-normal' :
              isHigh ? 'text-red-400'   :
              isMid  ? 'text-amber-400' :
              'text-ink',
            )}
          >
            {isNull ? '--' : `${Math.round(pct)}${suffix}`}
          </motion.span>
        </div>
      </div>

      {/* track */}
      <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-surface-tertiary/80 ring-1 ring-inset ring-white/5">

        {/* subtle threshold guides burned into the track */}
        <div className="pointer-events-none absolute inset-y-0 left-[50%] w-px bg-white/[0.07] z-10" />
        <div className="pointer-events-none absolute inset-y-0 left-[80%] w-px bg-white/[0.10] z-10" />

        {/* fill — width animated, color via CSS transition on inline style */}
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          initial={{ width: '0%' }}
          animate={{ width: isNull ? '0%' : `${pct}%` }}
          transition={{ duration: 0.75, ease: [0.16, 1, 0.3, 1] }}
          style={isNull ? {} : getBarStyle(pct, color)}
        />

        {/* always-running shimmer sweep — speed reflects urgency */}
        {!isNull && (
          <motion.div
            className="pointer-events-none absolute inset-y-0 w-10 bg-gradient-to-r from-transparent via-white/[0.22] to-transparent"
            animate={{ x: ['-40px', '340px'] }}
            transition={{
              duration: shimmerDuration,
              repeat: Infinity,
              ease: 'linear',
              repeatDelay: shimmerDelay,
            }}
          />
        )}
      </div>
    </div>
  )
}

// ─── TempDisplay ──────────────────────────────────────────────────────────────
const TempDisplay = ({ temp, label }: { temp: number | null; label: string }) => {
  const getColor = (t: number) =>
    t < 50 ? 'text-teal-500' : t < 70 ? 'text-amber-500' : 'text-red-500'

  const getBg = (t: number) =>
    t < 50 ? 'bg-teal-50 dark:bg-teal-500/10 ring-teal-200/80 dark:ring-teal-500/25' :
    t < 70 ? 'bg-amber-50 dark:bg-amber-500/10 ring-amber-200/80 dark:ring-amber-500/25' :
             'bg-red-50 dark:bg-red-500/10 ring-red-200/80 dark:ring-red-500/25'

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2 text-[11px] text-ink-secondary">
        <Thermometer size={13} className="text-ink-muted" />
        <span>{label}</span>
      </div>
      {temp !== null ? (
        <motion.span
          key={Math.round(temp)}
          initial={{ scale: 0.85, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={cn(
            'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums ring-1 ring-inset',
            getBg(temp), getColor(temp),
          )}
        >
          {Math.round(temp)}&deg;C
        </motion.span>
      ) : (
        <span className="text-[11px] text-ink-muted">--</span>
      )}
    </div>
  )
}

// ─── DashboardPanel ───────────────────────────────────────────────────────────
const DashboardPanel = () => {
  const { dashboardPanelOpen, toggleDashboardPanel, activeAgents, systemMetrics, systemOnline, setActiveTab } = useAppStore()
  const {
    convStats,
    loadConvStats,
    stats,
    loadStats,
    setSelectedLayer,
    loadAllEpisodic,
    browseSemantic,
    loadProcedural,
  } = useMemoryStore()

  React.useEffect(() => {
    loadConvStats()
    loadStats()
    const id = setInterval(() => {
      loadConvStats()
      loadStats()
    }, 30000)
    return () => clearInterval(id)
  }, [loadConvStats, loadStats])

  const todayCount = convStats?.today_messages ?? null
  const avgMs = convStats?.avg_response_ms ?? null
  const avgLabel = avgMs !== null ? `${(avgMs / 1000).toFixed(1)}s` : '--'

  // 7-bar activity chart: use real weekly data when available.
  const activityBars = React.useMemo(() => {
    const weekly = convStats?.weekly_messages
    if (weekly && weekly.length === 7) {
      const max = Math.max(...weekly, 1)
      return weekly.map(v => Math.round((v / max) * 100))
    }
    // Fallback before first poll completes
    return [0, 0, 0, 0, 0, 0, 0]
  }, [convStats?.weekly_messages])

  const cpu      = systemMetrics?.cpu_percent    ?? null
  const ram      = systemMetrics?.ram_percent    ?? null
  const ramDetail= systemMetrics ? `${systemMetrics.ram_used_gb}/${systemMetrics.ram_total_gb} GB` : undefined
  const gpu      = systemMetrics?.gpu_percent    ?? null
  const gpuTemp  = systemMetrics?.gpu_temp_c     ?? null
  const gpuVram  = systemMetrics?.gpu_vram_percent ?? null
  const gpuName  = systemMetrics?.gpu_name       ?? null

  const hasGpu = gpuName !== null

  return (
    <>
      {/* collapse toggle — lives outside the sliding panel so it's always reachable */}
      <motion.button
        onClick={toggleDashboardPanel}
        style={{ y: '-50%' }}
        initial={false}
        animate={{ x: dashboardPanelOpen ? -320 : 0 }}
        transition={{ type: 'spring', stiffness: 400, damping: 40 }}
        className="fixed right-0 top-1/2 z-20 flex h-8 w-5 items-center justify-center rounded-l-lg glass-elevated text-ink-muted shadow-glass hover:text-ink"
        aria-label={dashboardPanelOpen ? 'Close panel' : 'Open panel'}
      >
        {dashboardPanelOpen ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </motion.button>

    <motion.div
      initial={{ x: 320 }}
      animate={{ x: dashboardPanelOpen ? 0 : 320 }}
      transition={{ type: 'spring', stiffness: 400, damping: 40 }}
      className="fixed right-0 top-0 z-10 h-full w-[320px] overflow-y-auto glass p-5 shadow-glass"
    >
      {/* header */}
      <div className="mb-5 flex items-center justify-between">
        <h2 className="font-display text-lg font-semibold tracking-tight text-ink">Dashboard</h2>
        <div className="flex items-center gap-3">
          <div className={cn(
            'flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ring-inset',
            systemOnline
              ? 'bg-emerald-50/90 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 ring-emerald-200/80 dark:ring-emerald-500/25'
              : 'bg-red-50/90 dark:bg-red-500/10 text-red-700 dark:text-red-400 ring-red-200/80 dark:ring-red-500/25',
          )}>
            <span className="relative flex h-1.5 w-1.5">
              {systemOnline && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-60" />
              )}
              <span className={cn('relative inline-flex h-1.5 w-1.5 rounded-full', systemOnline ? 'bg-emerald-500' : 'bg-red-500')} />
            </span>
            {systemOnline ? 'Live' : 'Offline'}
          </div>
          <button className="text-ink-muted transition-colors hover:text-ink">
            <Settings size={16} />
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {/* ─── System Health ─────────────────────────────────── */}
        <GlassCard padding="sm">
          <div className="mb-4 flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-gradient-primary">
              <Activity size={13} className="text-white" />
            </div>
            <h3 className="text-sm font-semibold text-ink">System Health</h3>
          </div>

          {/* ── 3D Resource Avatars ───────────────────────────── */}
          <div className={cn(
            'mb-5 grid items-end gap-1',
            hasGpu ? 'grid-cols-4' : 'grid-cols-2 justify-items-center',
          )}>
            <ResourceAvatarOrbDynamic value={cpu}     resourceKey="cpu"  size={58} />
            <ResourceAvatarOrbDynamic value={ram}     resourceKey="ram"  size={58} />
            {hasGpu && (
              <>
                <ResourceAvatarOrbDynamic value={gpu}     resourceKey="gpu"  size={58} />
                <ResourceAvatarOrbDynamic value={gpuVram} resourceKey="vram" size={58} />
              </>
            )}
          </div>

          {/* divider */}
          <div className="mb-3.5 h-px bg-border-subtle" />

          {/* ── Metric Bars ───────────────────────────────────── */}
          <div className="space-y-3.5">
            <MetricBar label="CPU" value={cpu} color="indigo" />
            <MetricBar label="RAM" value={ram} color="violet" detail={ramDetail} />

            <AnimatePresence>
              {hasGpu && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="space-y-3.5 overflow-hidden"
                >
                  <div className="flex items-center gap-2 pt-1.5 border-t border-border-subtle">
                    <MonitorDot size={13} className="text-ink-muted" />
                    <span className="truncate text-[11px] font-medium text-ink-secondary">{gpuName}</span>
                  </div>
                  <MetricBar label="GPU"  value={gpu}     color="teal" />
                  <MetricBar label="VRAM" value={gpuVram} color="pink" />
                  <TempDisplay temp={gpuTemp} label="GPU Temp" />
                </motion.div>
              )}
            </AnimatePresence>

            {/* LM Studio */}
            <div className="flex items-center justify-between pt-2 border-t border-border-subtle text-xs">
              <span className="text-ink-secondary">LM Studio</span>
              <span className={cn(
                'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset',
                systemOnline
                  ? 'bg-emerald-50/90 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 ring-emerald-200/80 dark:ring-emerald-500/25'
                  : 'bg-red-50/90 dark:bg-red-500/10 text-red-700 dark:text-red-400 ring-red-200/80 dark:ring-red-500/25',
              )}>
                <span className={cn('h-1 w-1 rounded-full', systemOnline ? 'bg-emerald-500' : 'bg-red-500')} />
                {systemOnline ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
        </GlassCard>

        {/* ─── Active Agents ─────────────────────────────────── */}
        <GlassCard padding="sm">
          <h3 className="mb-1 text-sm font-semibold text-ink">Active Agents</h3>
          <p className="mb-4 text-[11px] text-ink-muted">Phase 1 · 1/19 agents active</p>
          <div className="grid grid-cols-2 gap-2.5">
            <div className="rounded-xl bg-gradient-subtle p-3 ring-1 ring-inset ring-border-subtle">
              <p className="text-sm font-semibold text-ink">Supervisor</p>
              <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent">Tier 1</p>
              <p className="mt-2 text-[11px] text-ink-secondary">
                {activeAgents[0]?.status ?? 'idle'}
              </p>
            </div>
            {[0, 1, 2].map(i => (
              <div key={i} className="rounded-xl border-2 border-dashed border-border-subtle bg-white/20" />
            ))}
          </div>
        </GlassCard>

        {/* ─── Conversation Stats ─────────────────────────────── */}
        <GlassCard padding="sm">
          <h3 className="mb-3 text-sm font-semibold text-ink">Conversation Stats</h3>
          <div className="mb-3 grid grid-cols-2 gap-2 text-center">
            <div className="rounded-xl bg-surface-elevated p-3 ring-1 ring-inset ring-border-subtle">
              <motion.p
                key={String(todayCount)}
                initial={{ scale: 0.85, opacity: 0.6 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.25 }}
                className="font-display text-2xl font-semibold text-ink tabular-nums"
              >
                {todayCount ?? '--'}
              </motion.p>
              <p className="text-[10px] uppercase tracking-wider text-ink-muted">Today</p>
            </div>
            <div className="rounded-xl bg-surface-elevated p-3 ring-1 ring-inset ring-border-subtle">
              <motion.p
                key={avgLabel}
                initial={{ scale: 0.85, opacity: 0.6 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.25 }}
                className="font-display text-2xl font-semibold text-ink tabular-nums"
              >
                {avgLabel}
              </motion.p>
              <p className="text-[10px] uppercase tracking-wider text-ink-muted">Avg. Time</p>
            </div>
          </div>
          {/* Mini 7-bar activity chart */}
          <div className="rounded-xl bg-surface-elevated/60 p-3 ring-1 ring-inset ring-border-subtle">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[10px] uppercase tracking-wider text-ink-muted">Activity</span>
              <span className="text-[10px] text-ink-muted">Last 7 days</span>
            </div>
            <div className="flex h-[60px] items-end gap-1">
              {activityBars.map((h, i) => (
                <motion.div
                  key={i}
                  className="flex-1 rounded-sm"
                  initial={{ height: 0 }}
                  animate={{ height: `${Math.max(h, 4)}%` }}
                  transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: i * 0.04 }}
                  style={{
                    background: h > 0
                      ? 'linear-gradient(180deg, #818cf8 0%, #4f46e5 100%)'
                      : 'rgba(255,255,255,0.06)',
                    boxShadow: h > 60 ? '0 0 8px rgba(99,102,241,0.5)' : undefined,
                  }}
                />
              ))}
            </div>
          </div>
        </GlassCard>

        {/* ─── Memory ─────────────────────────────────────────── */}
        <GlassCard padding="sm">
          <div className="mb-3 flex items-center gap-2">
            <Brain size={14} className="text-violet-500" />
            <h3 className="text-sm font-semibold text-ink">Memory</h3>
          </div>
          <div className="space-y-2">
            {[
              {
                label: 'Episodic',
                count: stats?.episodic.total ?? 0,
                available: stats?.episodic.available ?? false,
                dotClass: 'bg-violet-500',
                description: 'Redis · recent events',
                icon: Clock,
              },
              {
                label: 'Semantic',
                count: stats?.semantic.total ?? 0,
                available: stats?.semantic.available ?? false,
                dotClass: 'bg-teal-500',
                description: 'ChromaDB · facts',
                icon: Database,
              },
              {
                label: 'Procedural',
                count: stats?.procedural.total ?? 0,
                available: true,
                dotClass: 'bg-indigo-500',
                description: 'SQLite · patterns',
                icon: GitBranch,
              },
            ].map(({ label, count, available, dotClass, description, icon: Icon }) => (
              <button
                key={label}
                type="button"
                onClick={() => {
                  if (label === 'Episodic') {
                    setSelectedLayer('episodic')
                    loadAllEpisodic()
                  } else if (label === 'Semantic') {
                    setSelectedLayer('semantic')
                    browseSemantic()
                  } else {
                    setSelectedLayer('procedural')
                    loadProcedural()
                  }
                  setActiveTab('memory')
                }}
                className="flex w-full items-center justify-between gap-2 rounded-lg px-1 py-1 text-left transition-colors hover:bg-surface-elevated/50"
              >
                <div className="flex min-w-0 items-center gap-2">
                  <span className="relative flex h-2 w-2 flex-shrink-0">
                    {available && (
                      <span className={cn('absolute inline-flex h-full w-full animate-ping rounded-full opacity-50', dotClass)} />
                    )}
                    <span className={cn('relative inline-flex h-2 w-2 rounded-full', available ? dotClass : 'bg-zinc-400/60')} />
                  </span>
                  <Icon size={12} className="flex-shrink-0 text-ink-muted" />
                  <div className="min-w-0">
                    <p className="truncate text-xs font-medium text-ink">{label}</p>
                    <p className="truncate text-[10px] text-ink-muted">{description}</p>
                  </div>
                </div>
                <span className={cn(
                  'flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold tabular-nums ring-1 ring-inset',
                  available
                    ? 'bg-accent-muted text-accent-dark ring-border-accent'
                    : 'bg-surface-tertiary/60 text-ink-muted ring-border-subtle',
                )}>
                  {count}
                </span>
              </button>
            ))}
          </div>
          <button
            onClick={() => setActiveTab('memory')}
            className="mt-3 flex w-full items-center justify-between rounded-xl bg-surface-elevated px-3 py-2 text-xs font-medium text-ink-secondary ring-1 ring-inset ring-border-subtle transition-all hover:bg-accent-muted hover:text-accent-dark hover:ring-border-accent"
          >
            <span>Browse Memory</span>
            <ChevronRightIcon size={14} />
          </button>
        </GlassCard>
      </div>
    </motion.div>
    </>
  )
}

export default DashboardPanel
