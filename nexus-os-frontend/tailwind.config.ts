import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: 'class',
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface: {
          primary: "var(--bg-primary)",
          secondary: "var(--bg-secondary)",
          tertiary: "var(--bg-tertiary)",
          elevated: "var(--bg-elevated)",
          glass: "var(--surface-glass)",
          "glass-elevated": "var(--surface-glass-elevated)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          light: "var(--accent-light)",
          dark: "var(--accent-dark)",
          deeper: "var(--accent-deeper)",
          muted: "var(--accent-muted)",
          glow: "var(--accent-glow)",
        },
        "accent-2": {
          DEFAULT: "var(--accent-secondary)",
          light: "var(--accent-secondary-light)",
          muted: "var(--accent-secondary-muted)",
        },
        ink: {
          DEFAULT: "var(--text-primary)",
          secondary: "var(--text-secondary)",
          tertiary: "var(--text-tertiary)",
          muted: "var(--text-muted)",
          inverted: "var(--text-inverted)",
        },
        border: {
          subtle: "var(--border-subtle)",
          medium: "var(--border-medium)",
          glow: "var(--border-glow)",
          accent: "var(--border-accent)",
        },
        status: {
          success: "var(--success)",
          warning: "var(--warning)",
          error: "var(--error)",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "-apple-system", "sans-serif"],
        display: ["var(--font-space-grotesk)", "var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "SF Mono", "Monaco", "monospace"],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },
      boxShadow: {
        "glass-sm": "0 2px 8px rgba(15, 12, 36, 0.04)",
        glass: "0 8px 32px rgba(15, 12, 36, 0.06)",
        "glass-lg": "0 20px 60px rgba(15, 12, 36, 0.08)",
        "glass-xl": "0 32px 80px rgba(15, 12, 36, 0.10)",
        "glow-accent":    "0 0 36px rgba(124, 92, 255, 0.28)",
        "glow-accent-lg": "0 0 72px rgba(124, 92, 255, 0.40)",
        "glow-accent-xl": "0 0 120px rgba(124, 92, 255, 0.55)",
        "inner-shine":    "inset 0 1px 0 0 rgba(255, 255, 255, 0.6)",
        "soft-up":        "0 -4px 24px rgba(15, 12, 36, 0.04)",
        ring: "0 0 0 1px var(--border-subtle)",
      },
      backgroundImage: {
        "gradient-primary": "var(--gradient-primary)",
        "gradient-subtle":  "var(--gradient-subtle)",
        "gradient-radial":  "radial-gradient(ellipse at center, var(--tw-gradient-stops))",
        "gradient-mesh":    "var(--gradient-mesh)",
        "gradient-conic":   "conic-gradient(from var(--conic-from, 0deg) at var(--conic-pos, 50% 50%), var(--tw-gradient-stops))",
      },
      borderRadius: {
        "4xl": "2rem",
        "5xl": "2.5rem",
      },
      animation: {
        float: "float 6s cubic-bezier(0.37, 0, 0.63, 1) infinite",
        "float-delayed": "float-delayed 8s cubic-bezier(0.37, 0, 0.63, 1) infinite",
        "glow-breathe": "glow-breathe 4s cubic-bezier(0.37, 0, 0.63, 1) infinite",
        "gradient-shift": "gradient-shift 6s ease infinite",
        shimmer: "shimmer 3s linear infinite",
        aurora: "aurora 20s linear infinite",
      },
      transitionTimingFunction: {
        "out-expo":   "cubic-bezier(0.22, 1, 0.36, 1)",
        "out-quint":  "cubic-bezier(0.16, 1, 0.30, 1)",
        "in-out-quart": "cubic-bezier(0.76, 0, 0.24, 1)",
        "out-back":   "cubic-bezier(0.34, 1.56, 0.64, 1)",
        "in-out-sine": "cubic-bezier(0.37, 0, 0.63, 1)",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-12px)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
