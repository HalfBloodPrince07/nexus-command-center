'use client'

import React, { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import { useMagnetic } from '@/hooks/useMagnetic'
import { EASE_OUT_EXPO } from '@/lib/motion'

interface FloatingNavProps {
  onEnter: () => void
}

const NAV_ITEMS = [
  { label: 'Agents', href: '#agents' },
  { label: 'Memory', href: '#memory' },
  { label: 'Research', href: '#research' },
  { label: 'FAQ', href: '#faq' },
]

export default function FloatingNav({ onEnter }: FloatingNavProps) {
  const [hidden, setHidden] = useState(false)
  const lastY = useRef(0)
  const [ctaRef, ctaOffset] = useMagnetic<HTMLButtonElement>(10)

  useEffect(() => {
    const onScroll = () => {
      const y = window.scrollY
      const delta = y - lastY.current
      // Only react past 80px to avoid flicker on small reverses near the top
      if (y < 80) {
        setHidden(false)
      } else if (delta > 6) {
        setHidden(true)
      } else if (delta < -6) {
        setHidden(false)
      }
      lastY.current = y
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <AnimatePresence>
      <motion.nav
        key="nav"
        aria-label="Primary"
        className="fixed left-1/2 top-4 z-50 -translate-x-1/2"
        initial={{ y: -80, opacity: 0 }}
        animate={{
          y: hidden ? -80 : 0,
          opacity: hidden ? 0 : 1,
        }}
        transition={{ duration: 0.45, ease: EASE_OUT_EXPO }}
      >
        <div className="glass-elevated stroke-gradient flex items-center gap-2 rounded-full px-2 py-2 pr-2 sm:gap-6 sm:pl-5">
          {/* Brand */}
          <a href="#top" className="flex items-center gap-2 px-2 sm:px-0">
            <span className="font-display text-base font-bold tracking-tight text-ink">
              NEXUS
            </span>
            <span className="hidden rounded-full border border-border-subtle bg-surface-secondary/60 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-widest text-ink-tertiary sm:inline">
              OS
            </span>
          </a>

          {/* Center nav */}
          <div className="hidden items-center gap-1 md:flex">
            {NAV_ITEMS.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className="rounded-full px-3 py-1.5 text-xs font-medium text-ink-secondary transition-colors duration-200 hover:bg-surface-glass hover:text-ink"
              >
                {item.label}
              </a>
            ))}
          </div>

          {/* CTA — magnetic + glow */}
          <motion.button
            ref={ctaRef}
            onClick={onEnter}
            style={{ transform: `translate3d(${ctaOffset.x}px, ${ctaOffset.y}px, 0)` }}
            className="group relative inline-flex items-center gap-1.5 overflow-hidden rounded-full bg-gradient-primary px-4 py-2 text-xs font-semibold text-white shadow-glow-accent transition-shadow duration-300 hover:shadow-glow-accent-lg"
            data-cursor-hover
          >
            <span className="relative z-10">Launch</span>
            <ArrowRight
              size={13}
              className="relative z-10 transition-transform duration-300 group-hover:translate-x-0.5"
            />
            {/* Sweep highlight on hover */}
            <span className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/30 to-transparent transition-transform duration-700 group-hover:translate-x-full" />
          </motion.button>
        </div>
      </motion.nav>
    </AnimatePresence>
  )
}
