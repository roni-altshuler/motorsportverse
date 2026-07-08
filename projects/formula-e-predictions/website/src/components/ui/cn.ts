/**
 * cn — the standard shadcn className utility.
 *
 * Combines clsx (conditional classNames) with tailwind-merge (collapses
 * conflicting Tailwind classes — last write wins).  Use everywhere we
 * compose classNames in this directory.
 */
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
