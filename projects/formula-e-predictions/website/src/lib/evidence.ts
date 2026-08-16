// Build-time loader for the shared evidence artifact.
//
// `public/data/evidence.json` is written by scripts/build_evidence.py, which
// calls motorsport_core.evidence — one implementation of the model-vs-baseline
// comparison for the whole ecosystem. Nothing here recomputes a metric: a page
// that derives its own number is a second model nobody benchmarked, and two
// sites deriving it separately will eventually disagree in public.
//
// Returning `undefined` when the file is absent is deliberate. EvidencePanel
// renders the "no benchmark yet, treat these as unverified" state in that case,
// which is the honest thing to show — a missing benchmark is information, not a
// reason to render nothing.
//
// Synced to every site — edit the canonical copy under
// projects/f1-predictions/website/src/lib/.
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

import type { EvidenceBlock } from "@/components/ui/EvidencePanel";

export function getEvidence(): EvidenceBlock | undefined {
  const path = join(process.cwd(), "public", "data", "evidence.json");
  if (!existsSync(path)) return undefined;
  try {
    return JSON.parse(readFileSync(path, "utf-8")) as EvidenceBlock;
  } catch {
    return undefined;
  }
}
