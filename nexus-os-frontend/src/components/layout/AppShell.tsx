'use client'
import React from 'react'
import { cn } from '@/lib/utils'
import { useAppStore } from '@/stores/useAppStore'
import { ParticleFieldDynamic } from '../three/ParticleField'
import Sidebar from './Sidebar'
import DashboardPanel from './DashboardPanel'
import CommandCenter from '../CommandCenter'

const AppShell = () => {
  const { dashboardPanelOpen } = useAppStore()

  return (
    <div className="fixed inset-0 overflow-hidden bg-surface-primary transition-colors duration-300">
      {/* Background mesh gradient + ambient glows */}
      <div className="pointer-events-none absolute inset-0 z-0">
        <div className="absolute inset-0 bg-gradient-mesh" />
        <div className="absolute -top-[200px] -left-[200px] h-[600px] w-[600px] rounded-full bg-indigo-400/[0.06] dark:bg-indigo-400/[0.14] blur-[140px]" />
        <div className="absolute -bottom-[200px] -right-[200px] h-[500px] w-[500px] rounded-full bg-violet-400/[0.05] dark:bg-violet-400/[0.12] blur-[120px]" />
        <div className="absolute top-1/3 left-1/2 h-[400px] w-[400px] -translate-x-1/2 rounded-full bg-teal-300/[0.03] dark:bg-teal-300/[0.08] blur-[100px]" />
      </div>

      {/* Particle field */}
      <ParticleFieldDynamic />

      {/* Noise overlay */}
      <div className="bg-noise pointer-events-none absolute inset-0 z-[1]" />

      <div className="relative z-10 flex h-full w-full">
        <Sidebar />
        <main className={cn(
          'flex-1 overflow-hidden flex transition-[padding-right] duration-300 ease-out',
          dashboardPanelOpen ? 'pr-[320px]' : 'pr-0',
        )}>
          <CommandCenter />
        </main>
        <DashboardPanel />
      </div>
    </div>
  )
}

export default AppShell
