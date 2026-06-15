"use client";

import { useMemo, useState } from "react";

import { ProjectCard } from "@/components/ProjectCard";
import type { Maturity, Project } from "@/types/registry";

const MATURITIES: (Maturity | "all")[] = [
  "all",
  "production",
  "in-development",
  "experimental",
  "concept",
  "archived",
];

const MATURITY_LABEL: Record<string, string> = {
  all: "All",
  production: "Production",
  "in-development": "In Development",
  experimental: "Experimental",
  concept: "Concept",
  archived: "Archived",
};

export function ProjectExplorer({ projects }: { projects: Project[] }) {
  const [maturity, setMaturity] = useState<Maturity | "all">("all");
  const [category, setCategory] = useState<string>("all");

  const categories = useMemo(
    () => ["all", ...Array.from(new Set(projects.map((p) => p.category))).sort()],
    [projects],
  );

  const filtered = projects.filter(
    (p) =>
      (maturity === "all" || p.maturity === maturity) &&
      (category === "all" || p.category === category),
  );

  return (
    <div>
      <div className="mb-6 flex flex-col gap-3">
        <div className="flex flex-wrap gap-2">
          {MATURITIES.map((m) => (
            <FilterChip
              key={m}
              active={maturity === m}
              onClick={() => setMaturity(m)}
              label={MATURITY_LABEL[m]}
            />
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map((c) => (
            <FilterChip
              key={c}
              active={category === c}
              onClick={() => setCategory(c)}
              label={c === "all" ? "All categories" : c}
            />
          ))}
        </div>
      </div>

      <p className="mb-4 text-sm text-[var(--ink-dim)]">
        {filtered.length} of {projects.length} projects
      </p>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((p) => (
          <ProjectCard key={p.slug} project={p} />
        ))}
      </div>
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border px-3 py-1.5 text-xs font-medium capitalize transition-colors"
      style={{
        color: active ? "var(--accent-ink)" : "var(--ink-muted)",
        backgroundColor: active ? "var(--accent)" : "transparent",
        borderColor: active ? "var(--accent)" : "var(--hairline)",
      }}
    >
      {label}
    </button>
  );
}
