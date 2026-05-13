'use client'

import { motion, useScroll, useSpring } from 'framer-motion'

/**
 * 2px scroll-progress bar pinned to the top of the viewport.
 * Spring-smoothed so it doesn't tic on every scroll event.
 */
export default function ScrollProgressBar() {
  const { scrollYProgress } = useScroll()
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 140,
    damping: 28,
    restDelta: 0.001,
  })

  return (
    <motion.div
      aria-hidden
      className="pointer-events-none fixed left-0 right-0 top-0 z-[60] h-[2px] origin-left bg-gradient-primary"
      style={{ scaleX }}
    />
  )
}
