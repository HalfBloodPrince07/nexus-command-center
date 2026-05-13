'use client'

import { motion, easeOut } from 'framer-motion'
import { cn } from '@/lib/utils'

interface GlassCardProps {
  children: React.ReactNode
  variant?: 'default' | 'elevated' | 'bordered' | 'glow'
  className?: string
  onClick?: () => void
  padding?: 'none' | 'sm' | 'md' | 'lg'
  animate?: boolean
}

const GlassCard = ({
  children,
  variant = 'default',
  className,
  onClick,
  padding = 'md',
  animate = true,
}: GlassCardProps) => {
  const variantClasses = {
    default:
      'glass rounded-2xl shadow-glass',
    elevated:
      'glass-elevated rounded-2xl shadow-glass-lg',
    bordered:
      'glass rounded-2xl ring-1 ring-inset ring-border-accent shadow-glass',
    glow:
      'glass rounded-2xl shadow-glass animate-glow-breathe',
  }

  const paddingClasses = {
    none: 'p-0',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  }

  const motionProps = animate
    ? {
        initial: { opacity: 0, y: 8 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.4, ease: easeOut },
      }
    : {}

  return (
    <motion.div
      {...motionProps}
      className={cn(
        'transition-all duration-300',
        variantClasses[variant],
        paddingClasses[padding],
        onClick && 'cursor-pointer hover:-translate-y-0.5 hover:shadow-glass-lg',
        className
      )}
      onClick={onClick}
    >
      {children}
    </motion.div>
  )
}

export default GlassCard
