import type { Maturity } from "@/types/registry";

const LABELS: Record<Maturity, string> = {
  concept: "Concept",
  "in-development": "In Development",
  experimental: "Experimental",
  production: "Production",
  archived: "Archived",
};

const COLORS: Record<Maturity, string> = {
  concept: "var(--maturity-concept)",
  "in-development": "var(--maturity-in-development)",
  experimental: "var(--maturity-experimental)",
  production: "var(--maturity-production)",
  archived: "var(--maturity-archived)",
};

export function MaturityBadge({ maturity }: { maturity: Maturity }) {
  const color = COLORS[maturity];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
      style={{
        color,
        backgroundColor: "color-mix(in srgb, " + color + " 14%, transparent)",
        border: "1px solid color-mix(in srgb, " + color + " 35%, transparent)",
      }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: color }}
      />
      {LABELS[maturity]}
    </span>
  );
}
