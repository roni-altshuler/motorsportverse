/**
 * Motion design tokens.  Single source of truth for framer-motion
 * variants and GSAP timeline parameters.  Mirrors the --dur-* and
 * --ease-* CSS variables in styles/tokens.css so JS and CSS stay
 * in sync.
 */
import type { Transition, Variants } from "framer-motion";

export const DURATIONS = {
  instant: 0.08,
  snap: 0.18,
  base: 0.32,
  glide: 0.52,
  cinema: 0.9,
} as const;

export const EASE = {
  pit: [0.16, 1, 0.3, 1] as [number, number, number, number],
  launch: [0.65, 0, 0.35, 1] as [number, number, number, number],
  drs: [0.22, 1, 0.36, 1] as [number, number, number, number],
} as const;

export const SPRING = {
  pop: { type: "spring", stiffness: 420, damping: 28 } satisfies Transition,
  glide: { type: "spring", stiffness: 180, damping: 22 } satisfies Transition,
  heavy: { type: "spring", stiffness: 90, damping: 18 } satisfies Transition,
} as const;

export const STAGGER = {
  fast: 0.04,
  base: 0.06,
  slow: 0.1,
} as const;

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    transition: { ...SPRING.glide, delay: i * STAGGER.base },
  }),
};

/**
 * Parent wrapper that staggers any direct children carrying `hidden`/`visible`
 * variants (e.g. `fadeUp`). Pair with `initial="hidden" whileInView="visible"`.
 * Empty states keep the parent itself invisible-free so layout never shifts.
 */
export const staggerContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: STAGGER.base } },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: (i: number = 0) => ({
    opacity: 1,
    transition: { duration: DURATIONS.base, delay: i * STAGGER.fast },
  }),
};

export const slideInLeft: Variants = {
  hidden: { opacity: 0, x: -32 },
  visible: { opacity: 1, x: 0, transition: SPRING.glide },
};

export const slideInRight: Variants = {
  hidden: { opacity: 0, x: 32 },
  visible: { opacity: 1, x: 0, transition: SPRING.glide },
};

export const popIn: Variants = {
  hidden: { opacity: 0, scale: 0.92 },
  visible: { opacity: 1, scale: 1, transition: SPRING.pop },
};

export const podiumReveal: Variants = {
  hidden: { opacity: 0, y: 28, scale: 0.96 },
  visible: (i: number = 0) => ({
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { ...SPRING.glide, delay: i * 0.08 },
  }),
};

export const lightsOut = {
  off: { opacity: 0.25, boxShadow: "0 0 0 rgba(255,24,1,0)" },
  on: {
    opacity: 1,
    boxShadow: "0 0 8px rgba(255,24,1,0.85), 0 0 18px rgba(255,24,1,0.55)",
  },
} as const;
