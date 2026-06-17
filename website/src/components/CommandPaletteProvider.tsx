// Server component: builds the command-palette index from the registry at
// build time and hands it to the client palette. Mounted once in the layout.

import { CommandPalette, type PaletteItem } from "@/components/CommandPalette";
import { getProjects } from "@/lib/registry";

export function CommandPaletteProvider() {
  const projects = getProjects();

  const items: PaletteItem[] = [
    { id: "home", label: "Home", group: "Pages", href: "/", keywords: "landing start" },
    { id: "projects", label: "All projects", group: "Pages", href: "/projects", keywords: "catalog directory grid" },
    { id: "docs", label: "Documentation", group: "Pages", href: "/docs", keywords: "guide api reference" },
    { id: "contribute", label: "Contribute", group: "Pages", href: "/contribute", keywords: "add sport build" },
    ...projects.map<PaletteItem>((p) => ({
      id: `proj-${p.slug}`,
      label: p.name,
      hint: p.sport,
      group: "Projects",
      href: `/projects/${p.slug}`,
      keywords: `${p.sport} ${p.category} ${(p.tags ?? []).join(" ")}`,
    })),
    {
      id: "gh",
      label: "GitHub organization",
      hint: "external",
      group: "Links",
      href: "https://github.com/motorsportverse",
      external: true,
      keywords: "source code repo",
    },
  ];

  return <CommandPalette items={items} />;
}
