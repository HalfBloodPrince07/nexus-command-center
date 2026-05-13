/**
 * Duration scale.
 * Micro 200ms · Component 400–600ms · Hero 800–1200ms · never > 1.4s for UI.
 */

export const DUR = {
  micro: 0.2,
  fast: 0.35,
  base: 0.5,
  slow: 0.7,
  hero: 1.0,
  heroSlow: 1.2,
  cap: 1.4,
} as const

export const STAGGER = {
  tight: 0.04,
  base: 0.06,
  loose: 0.08,
} as const
