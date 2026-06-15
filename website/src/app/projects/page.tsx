import type { Metadata } from "next";

import { ProjectExplorer } from "@/components/ProjectExplorer";
import { getProjects } from "@/lib/registry";

export const metadata: Metadata = {
  title: "Projects — MotorsportVerse",
  description: "The MotorsportVerse project catalog, filterable by maturity and category.",
};

export default function ProjectsPage() {
  const projects = getProjects();
  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <h1 className="text-3xl font-bold tracking-tight text-[var(--ink)]">Project directory</h1>
      <p className="mt-3 max-w-2xl text-[var(--ink-muted)]">
        Every motorsport in the ecosystem, from production projects to registered
        concepts. Filter by lifecycle stage or category.
      </p>
      <div className="mt-10">
        <ProjectExplorer projects={projects} />
      </div>
    </div>
  );
}
