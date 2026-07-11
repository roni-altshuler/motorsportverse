// TypeScript mirror of registry/schema/project.schema.json.
// Keep in sync with the JSON Schema; the build validates the data, this types it.

export type Maturity =
  | "concept"
  | "in-development"
  | "experimental"
  | "production"
  | "archived";

export type Category =
  | "open-wheel"
  | "stock"
  | "endurance"
  | "rally"
  | "motorcycle"
  | "electric"
  | "fantasy";

export interface Maintainer {
  name?: string;
  github?: string;
}

export interface Project {
  slug: string;
  name: string;
  sport: string;
  category: Category;
  maturity: Maturity;
  summary: string;
  description?: string;
  repo?: string;
  website?: string;
  docs?: string;
  datasets?: string[];
  models?: string[];
  tags?: string[];
  icon?: string;
  logo?: string;
  accent?: string;
  uses_core?: string[];
  maintainers?: Maintainer[];
  added?: string;
}

export interface RegistryIndex {
  generated_by: string;
  count: number;
  maturity_counts: Partial<Record<Maturity, number>>;
  projects: Project[];
}
