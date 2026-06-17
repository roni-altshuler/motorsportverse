"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";

import { fadeUp, staggerContainer } from "@/lib/motion";
import { useReveal } from "@/lib/useReveal";

/** Scroll-reveal wrapper using the shared motion tokens. Reveals on scroll, but
 *  a failsafe guarantees content is never left invisible (see useReveal).
 *  Honors prefers-reduced-motion via the global media query. */
export function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const { ref, shown } = useReveal();
  return (
    <motion.div
      ref={ref}
      className={className}
      variants={fadeUp}
      custom={delay}
      initial="hidden"
      animate={shown ? "visible" : "hidden"}
    >
      {children}
    </motion.div>
  );
}

/** Staggered container — children should use the `fadeUp` variant. */
export function RevealGroup({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const { ref, shown } = useReveal();
  return (
    <motion.div
      ref={ref}
      className={className}
      variants={staggerContainer}
      initial="hidden"
      animate={shown ? "visible" : "hidden"}
    >
      {children}
    </motion.div>
  );
}
