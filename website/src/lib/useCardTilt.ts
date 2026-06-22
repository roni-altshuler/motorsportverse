"use client";

import {
  useMotionValue,
  useReducedMotion,
  useSpring,
  useTransform,
} from "framer-motion";

const SPRING = { stiffness: 280, damping: 22, mass: 0.6 };
const MAX_TILT = 6; // degrees
const LIFT_PX = 12;
const SCALE_MAX = 1.03;

/**
 * Mouse-tracked 3D card tilt + lift (ported from the personal-site pattern).
 * Returns props to spread onto a framer `motion` element; the element tilts
 * toward the cursor and pops toward the viewer on hover. Also publishes the
 * cursor position as `--mx`/`--my` CSS vars so a highlight-hue spotlight can
 * follow it. Returns `{ reduced: true }` when reduced motion is requested —
 * callers should render a plain element then.
 */
export function useCardTilt() {
  const reduced = useReducedMotion();

  const px = useMotionValue(0);
  const py = useMotionValue(0);
  const lift = useMotionValue(0);

  const sx = useSpring(px, SPRING);
  const sy = useSpring(py, SPRING);
  const slift = useSpring(lift, SPRING);

  const rotateY = useTransform(sx, (v) => v * MAX_TILT);
  const rotateX = useTransform(sy, (v) => -v * MAX_TILT);
  const scale = useTransform(slift, (v) => 1 + v * (SCALE_MAX - 1));
  const z = useTransform(slift, (v) => v * LIFT_PX);

  if (reduced) return { reduced: true as const };

  const onMouseMove = (e: React.MouseEvent<HTMLElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const nx = ((e.clientX - r.left) / r.width) * 2 - 1;
    const ny = ((e.clientY - r.top) / r.height) * 2 - 1;
    px.set(Math.max(-1, Math.min(1, nx)));
    py.set(Math.max(-1, Math.min(1, ny)));
    e.currentTarget.style.setProperty("--mx", `${e.clientX - r.left}px`);
    e.currentTarget.style.setProperty("--my", `${e.clientY - r.top}px`);
  };
  const onMouseEnter = () => lift.set(1);
  const onMouseLeave = () => {
    px.set(0);
    py.set(0);
    lift.set(0);
  };

  return {
    reduced: false as const,
    onMouseMove,
    onMouseEnter,
    onMouseLeave,
    style: {
      rotateX,
      rotateY,
      scale,
      z,
      transformPerspective: 900,
      willChange: "transform",
    },
  };
}
