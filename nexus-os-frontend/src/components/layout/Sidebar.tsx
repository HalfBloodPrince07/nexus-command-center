'use client'

import {
  BookOpen, Brain, ChevronLeft, ChevronRight, FlaskConical, FolderOpen,
  History, LayoutDashboard, MessageSquare, Settings, Zap,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAppStore } from '@/stores/useAppStore'
import { TABS } from '@/lib/constants'
import { cn } from '@/lib/utils'
import React from 'react'
import { NotificationBell } from '@/components/layout/NotificationBell'

const Tooltip = ({ children, text }: { children: React.ReactNode; text: string }) => (
  <div className="group relative flex items-center">
    {children}
    <div className="pointer-events-none absolute left-full z-50 ml-3 hidden -translate-x-1 whitespace-nowrap rounded-xl glass-elevated px-3 py-1.5 text-xs font-medium text-ink opacity-0 shadow-glass-lg transition-all group-hover:block group-hover:translate-x-0 group-hover:opacity-100">
      {text}
    </div>
  </div>
)

const iconMap: { [key: string]: React.ElementType } = {
  chat: MessageSquare,
  dashboard: LayoutDashboard,
  research: FlaskConical,
  journal: BookOpen,
  files: FolderOpen,
  memory: Brain,
  history: History,
  insights: Zap,
  settings: Settings,
}

const Sidebar = () => {
  const { sidebarCollapsed, toggleSidebar, activeTab, setActiveTab, systemOnline } = useAppStore()
  const isExpanded = !sidebarCollapsed

  return (
    <motion.aside
      initial={false}
      animate={{ width: isExpanded ? 240 : 72 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      className="relative z-20 flex h-full flex-shrink-0 flex-col glass py-5 shadow-glass"
    >
      {/* Logo */}
      <div className="relative mb-8 flex h-12 items-center justify-center">
        <AnimatePresence mode="wait">
          {isExpanded ? (
            <motion.div
              key="logo"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
              transition={{ duration: 0.25 }}
              className="absolute flex items-center gap-2.5"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-primary shadow-glow-accent">
                <span className="font-display text-sm font-bold text-white">N</span>
              </div>
              <span className="font-display text-[15px] font-semibold tracking-tight text-gradient">
                NEXUS OS
              </span>
            </motion.div>
          ) : (
            <motion.div
              key="monogram"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              transition={{ duration: 0.25 }}
              className="absolute flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-primary font-display font-bold text-white shadow-glow-accent"
            >
              N
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Navigation */}
      <nav className="flex-grow space-y-1 px-3">
        {TABS.map(tab => {
          const Icon = iconMap[tab.id]
          const isActive = activeTab === tab.id

          const button = (
            <button
              key={tab.id}
              onClick={() => tab.available && setActiveTab(tab.id)}
              className={cn(
                'group relative flex w-full items-center rounded-xl p-2.5 text-left text-sm font-medium transition-all duration-200',
                !tab.available && 'cursor-not-allowed opacity-35',
                tab.available && !isActive && 'text-ink-secondary hover:bg-black/[0.03] dark:hover:bg-white/[0.05] hover:text-ink',
                isActive && 'text-white'
              )}
            >
              {isActive && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute inset-0 rounded-xl bg-gradient-primary shadow-glow-accent"
                  transition={{ type: 'spring', stiffness: 400, damping: 35 }}
                />
              )}
              <Icon
                className={cn(
                  'relative z-10 h-[18px] w-[18px] flex-shrink-0 transition-colors',
                  isActive ? 'text-white' : 'text-ink-muted group-hover:text-ink'
                )}
                strokeWidth={1.8}
              />
              <AnimatePresence>
                {isExpanded && (
                  <motion.span
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -8 }}
                    transition={{ duration: 0.2, delay: 0.08 }}
                    className="relative z-10 ml-3 whitespace-nowrap"
                  >
                    {tab.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </button>
          )

          return isExpanded || !tab.available ? button : (
            <Tooltip key={tab.id} text={tab.label}>{button}</Tooltip>
          )
        })}

        {isExpanded && (
          <div className="pt-5 pl-3 text-[11px] font-medium uppercase tracking-widest text-ink-muted">
            1 Agent Active
          </div>
        )}
      </nav>

      {/* Footer */}
      <div className="mt-auto flex flex-col items-center justify-center gap-3 px-3">
        {/* Notifications */}
        <NotificationBell />

        {/* Status */}
        <div className={cn(
          'flex items-center gap-2 rounded-full px-3 py-1.5 ring-1 ring-inset transition-all',
          systemOnline
            ? 'bg-emerald-50/90 dark:bg-emerald-500/10 ring-emerald-200/80 dark:ring-emerald-500/25'
            : 'bg-red-50/90 dark:bg-red-500/10 ring-red-200/80 dark:ring-red-500/25'
        )}>
          <span className="relative flex h-1.5 w-1.5">
            {systemOnline && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-50" />
            )}
            <span className={cn('relative inline-flex h-1.5 w-1.5 rounded-full', systemOnline ? 'bg-emerald-500' : 'bg-red-500')} />
          </span>
          <AnimatePresence>
            {isExpanded && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.2 }}
                className={cn('overflow-hidden whitespace-nowrap text-[11px] font-medium', systemOnline ? 'text-emerald-700 dark:text-emerald-400' : 'text-red-700 dark:text-red-400')}
              >
                {systemOnline ? 'Online' : 'Offline'}
              </motion.span>
            )}
          </AnimatePresence>
        </div>

        {/* Toggle */}
        <button
          onClick={toggleSidebar}
          className="rounded-full p-2 text-ink-muted transition-all hover:bg-black/[0.04] dark:hover:bg-white/[0.06] hover:text-ink"
          aria-label={isExpanded ? 'Collapse sidebar' : 'Expand sidebar'}
        >
          {isExpanded ? <ChevronLeft size={18} /> : <ChevronRight size={18} />}
        </button>
      </div>
    </motion.aside>
  )
}

export default Sidebar
