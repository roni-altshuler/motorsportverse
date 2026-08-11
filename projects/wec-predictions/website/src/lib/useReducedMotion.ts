"use client";

import { useReducedMotion as fmUseReducedMotion } from "framer-motion";

/**
 * Coerced wrapper around framer-motion's useReducedMotion hook so
 * consumers don't need to handle the boolean | null tri-state.
 */
export function useReducedMotion(): boolean {
  return fmUseReducedMotion() ?? false;
}
