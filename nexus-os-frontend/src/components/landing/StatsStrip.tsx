'use client'

import React, { useEffect, useState } from 'react'
import { motion, useInView } from 'framer-motion'
import { Bot, Layers, Lock, Clock, HardDrive, Network } from 'lucide-react'

interface Stat {
  value: number
  suffix?: string
  prefix?: string
  label: string
  icon: React.ElementType
}

const STATS: Stat[] = [
  { value: 5, suffix: '', prefix: '', label: 'Active Agents', icon: Bot },
  { value: 3, suffix: '', prefix: '', label: 'Memory Layers', icon: Layers },
  { value: 100, suffix: '%', prefix: '', label: 'Local & Private', icon: Lock },
  { value: 2, suffix: 's', prefix: '<', label: 'Avg Response', icon: Clock },
  { value: 50, suffix: 'MB', prefix: '', label: 'Max Upload', icon: HardDrive },
  { value: 19, suffix: '+', prefix: '', label: 'Agent Ecosystem', icon: Network },
]

function CountUp({ value, trigger }: { value: number; trigger: boolean }) {
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (!trigger) return
    const duration = 1200
    const start = Date.now()
    const tick = () => {
      const t = Math.min((Date.now() - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      setDisplay(Math.round(eased * value))
      if (t < 1) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, [trigger, value])

  return <>{display}</>
}

export default function StatsStrip() {
  const ref = React.useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-100px' })

  return (
    <section className="py-16">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="glass-elevated rounded-2xl p-5 sm:p-6"
        >
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {STATS.map((stat, i) => {
              const Icon = stat.icon
              return (
                <motion.div
                  key={stat.label}
                  initial={{ opacity: 0, y: 12 }}
                  animate={inView ? { opacity: 1, y: 0 } : {}}
                  transition={{ duration: 0.5, delay: i * 0.06, ease: [0.16, 1, 0.3, 1] }}
                  className="flex flex-col items-center text-center"
                >
                  <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-lg bg-accent-muted">
                    <Icon size={16} className="text-accent" strokeWidth={2}
                  />
                  </div>
                  <p className="font-display text-xl font-bold tabular-nums text-ink sm:text-2xl">
                    <CountUp value={stat.value} trigger={inView} />
                    {stat.suffix}
                  </p>
                  <p className="mt-0.5 text-[10px] uppercase tracking-wider text-ink-muted">{stat.label}</p>
                </motion.div>
              )
            })}
          </div>
        </motion.div>
      </div>
    </section>
  )
}
