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
    <div className="shell section">
      <p className="eyebrow">The grid</p>
      <h1 className="display mt-3 text-5xl">Project directory</h1>
      <p className="lead mt-4 max-w-2xl">
        Every motorsport in the ecosystem, from production projects to registered concepts. Filter
        by lifecycle stage or category.
      </p>
      <div className="mt-12">
        <ProjectExplorer projects={projects} />
      </div>
    </div>
  );
}
