// Build-time loader for the project catalog.
//
// The catalog source of truth is registry/index.json (produced by
// scripts/build_registry.py and copied to public/data/registry.json). These are
// server components in a static export, so we read the file at build time with
// fs — no runtime fetch.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { Project, RegistryIndex } from "@/types/registry";

let cache: RegistryIndex | null = null;

function load(): RegistryIndex {
  if (cache) return cache;
  // public/data/registry.json is written by the prebuild step.
  const path = join(process.cwd(), "public", "data", "registry.json");
  cache = JSON.parse(readFileSync(path, "utf-8")) as RegistryIndex;
  return cache;
}

export function getRegistry(): RegistryIndex {
  return load();
}

export function getProjects(): Project[] {
  return load().projects;
}

export function getProject(slug: string): Project | undefined {
  return load().projects.find((p) => p.slug === slug);
}

export function getMaturityCounts() {
  return load().maturity_counts;
}
