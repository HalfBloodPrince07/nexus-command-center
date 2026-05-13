'use client'

import GlassCard from './GlassCard'
import React from 'react'
import { motion } from 'framer-motion'

interface ComingSoonProps {
  tabName: string
  icon: React.ReactNode
  description?: string
}

const ComingSoon = ({ tabName, icon, description }: ComingSoonProps) => {
  return (
    <div className="relative flex h-full w-full items-center justify-center p-8">
      {/* Dot grid */}
      <div
        className="pointer-events-none absolute inset-0 z-0 opacity-40"
        style={{
          backgroundImage: 'radial-gradient(circle, rgba(99, 102, 241, 0.08) 1px, transparent 1px)',
          backgroundSize: '32px 32px',
          maskImage: 'radial-gradient(ellipse at center, black 30%, transparent 70%)',
        }}
      />

      <GlassCard
        variant="elevated"
        padding="lg"
        className="relative z-10 flex w-full max-w-md flex-col items-center text-center"
      >
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
          className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-subtle shadow-inner-shine"
        >
          <div className="text-accent">
            {React.cloneElement(icon as React.ReactElement, {
              size: 40,
              strokeWidth: 1.5,
            })}
          </div>
        </motion.div>

        <h2 className="font-display text-3xl font-semibold tracking-tight text-ink">
          {tabName}
        </h2>
        <p className="mt-2 text-sm text-ink-secondary">Coming in a future phase</p>
        {description && (
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-ink-muted">{description}</p>
        )}

        <div className="mt-6 inline-flex items-center gap-2 rounded-full bg-accent-muted px-4 py-1.5 text-xs font-semibold text-accent-dark ring-1 ring-inset ring-border-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
          Planned
        </div>
      </GlassCard>
    </div>
  )
}

export default ComingSoon
