'use client'

import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import dynamic from 'next/dynamic'

const LandingPage = dynamic(() => import('@/components/landing/LandingPage'), { ssr: false })
const AppShell = dynamic(() => import('@/components/layout/AppShell'), { ssr: false })

export default function Home() {
  const [entered, setEntered] = useState(false)

  return (
    <AnimatePresence mode="wait">
      {!entered ? (
        <motion.div
          key="landing"
          exit={{ opacity: 0, scale: 0.98 }}
          transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          <LandingPage onEnter={() => setEntered(true)} />
        </motion.div>
      ) : (
        <motion.div
          key="app"
          initial={{ opacity: 0, scale: 1.02 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-0"
        >
          <AppShell />
        </motion.div>
      )}
    </AnimatePresence>
  )
}
