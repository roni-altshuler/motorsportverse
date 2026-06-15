// Node mirror of build_registry.py — keeps the website build self-contained
// (no Python needed at `npm run build`). Validates required fields + enums and
// writes registry/index.json + website/public/data/registry.json.

import { readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const PROJECTS_DIR = join(ROOT, "registry", "projects");
const SCHEMA_PATH = join(ROOT, "registry", "schema", "project.schema.json");
const INDEX_PATH = join(ROOT, "registry", "index.json");
const WEBSITE_COPY = join(ROOT, "website", "public", "data", "registry.json");

const MATURITY_ORDER = ["production", "experimental", "in-development", "concept", "archived"];

const schema = JSON.parse(readFileSync(SCHEMA_PATH, "utf-8"));
const files = readdirSync(PROJECTS_DIR).filter((f) => f.endsWith(".json")).sort();

const errors = [];
const entries = [];
const seen = new Set();

for (const file of files) {
  const entry = JSON.parse(readFileSync(join(PROJECTS_DIR, file), "utf-8"));
  for (const field of schema.required || []) {
    if (!(field in entry)) errors.push(`${file}: missing required '${field}'`);
  }
  for (const [key, spec] of Object.entries(schema.properties || {})) {
    if (key in entry && spec.enum && !spec.enum.includes(entry[key])) {
      errors.push(`${file}: '${key}'=${JSON.stringify(entry[key])} not in ${JSON.stringify(spec.enum)}`);
    }
  }
  const stem = file.replace(/\.json$/, "");
  if (entry.slug !== stem) errors.push(`${file}: slug '${entry.slug}' != stem '${stem}'`);
  if (seen.has(entry.slug)) errors.push(`${file}: duplicate slug '${entry.slug}'`);
  seen.add(entry.slug);
  entries.push(entry);
}

if (errors.length) {
  console.error("Registry validation FAILED:");
  errors.forEach((e) => console.error("  - " + e));
  process.exit(1);
}

const rank = Object.fromEntries(MATURITY_ORDER.map((m, i) => [m, i]));
entries.sort((a, b) => (rank[a.maturity] ?? 99) - (rank[b.maturity] ?? 99) || a.name.localeCompare(b.name));

const counts = {};
for (const e of entries) counts[e.maturity] = (counts[e.maturity] || 0) + 1;

const index = {
  // Same value as build_registry.py so output is byte-identical regardless of
  // which generator ran last.
  generated_by: "motorsportverse registry build",
  count: entries.length,
  maturity_counts: counts,
  projects: entries,
};

const out = JSON.stringify(index, null, 2) + "\n";
writeFileSync(INDEX_PATH, out);
mkdirSync(dirname(WEBSITE_COPY), { recursive: true });
writeFileSync(WEBSITE_COPY, out);

console.log(`OK: ${entries.length} projects validated. maturity: ${JSON.stringify(counts)}`);
