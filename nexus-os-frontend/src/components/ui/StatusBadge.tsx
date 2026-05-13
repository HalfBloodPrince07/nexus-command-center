'use client'

import { cn } from '@/lib/utils'

interface StatusBadgeProps {
  status: 'idle' | 'thinking' | 'streaming' | 'error' | 'online' | 'offline'
  label?: string
  size?: 'sm' | 'md'
  className?: string
}

const StatusBadge = ({ status, label, size = 'md', className }: StatusBadgeProps) => {
  const statusConfig = {
    idle: {
      dot: 'bg-ink-muted',
      pill: 'bg-surface-secondary text-ink-secondary ring-border-subtle',
      pulse: false,
      text: 'Idle',
    },
    thinking: {
      dot: 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]',
      pill: 'bg-amber-50 text-amber-700 ring-amber-200/80',
      pulse: true,
      text: 'Thinking',
    },
    streaming: {
      dot: 'bg-accent shadow-[0_0_8px_rgba(99,102,241,0.5)]',
      pill: 'bg-indigo-50 text-indigo-700 ring-indigo-200/80',
      pulse: true,
      text: 'Streaming',
    },
    error: {
      dot: 'bg-status-error shadow-[0_0_8px_rgba(239,68,68,0.5)]',
      pill: 'bg-red-50 text-red-700 ring-red-200/80',
      pulse: false,
      text: 'Error',
    },
    online: {
      dot: 'bg-status-success shadow-[0_0_8px_rgba(16,185,129,0.5)]',
      pill: 'bg-emerald-50 text-emerald-700 ring-emerald-200/80',
      pulse: true,
      text: 'Online',
    },
    offline: {
      dot: 'bg-ink-muted',
      pill: 'bg-surface-secondary text-ink-secondary ring-border-subtle',
      pulse: false,
      text: 'Offline',
    },
  }

  const config = statusConfig[status]
  const displayLabel = label ?? config.text

  const dotSize = {
    sm: 'h-1.5 w-1.5',
    md: 'h-2 w-2',
  }

  const isStreaming = status === 'streaming'
  const hasLabel = displayLabel !== ''

  return (
    <div
      className={cn(
        'inline-flex items-center gap-2',
        hasLabel && 'rounded-full px-2.5 py-0.5 ring-1 ring-inset',
        hasLabel && config.pill,
        className
      )}
    >
      <span className="relative flex items-center justify-center">
        {config.pulse && (
          <span className={cn('absolute h-full w-full rounded-full animate-ping opacity-40', config.dot)} />
        )}
        <span className={cn('relative rounded-full', dotSize[size], config.dot)} />
      </span>
      {hasLabel && (
        <span
          className={cn(
            'text-xs font-medium',
            isStreaming && 'animate-shimmer bg-gradient-to-r from-indigo-600 via-violet-600 to-indigo-600 bg-[200%_auto] bg-clip-text text-transparent'
          )}
        >
          {displayLabel}
        </span>
      )}
    </div>
  )
}

export default StatusBadge
