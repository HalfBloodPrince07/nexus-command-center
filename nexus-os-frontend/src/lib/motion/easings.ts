/**
 * Easing constants. Default to EASE_OUT_EXPO for enter animations.
 */

export const EASE_OUT_EXPO = [0.22, 1, 0.36, 1] as const
export const EASE_OUT_QUINT = [0.16, 1, 0.30, 1] as const
export const EASE_IN_OUT_QUART = [0.76, 0, 0.24, 1] as const
export const EASE_OUT_BACK = [0.34, 1.56, 0.64, 1] as const
export const EASE_IN_OUT_SINE = [0.37, 0, 0.63, 1] as const

export const EASE = {
  outExpo: EASE_OUT_EXPO,
  outQuint: EASE_OUT_QUINT,
  inOutQuart: EASE_IN_OUT_QUART,
  outBack: EASE_OUT_BACK,
  inOutSine: EASE_IN_OUT_SINE,
} as const
