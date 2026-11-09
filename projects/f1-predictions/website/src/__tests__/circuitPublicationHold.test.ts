/** The cross-series inventory must distinguish a verified hold from lost data. */
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const script = resolve(process.cwd(), "../../../scripts/check_circuit_geometry.ts");
const tsx = resolve(process.cwd(), "node_modules/tsx/dist/cli.mjs");
let root: string;
const sources = { f1: "season", f2: "f2", f3: "f3", "formula-e": "fe", indycar: "indycar",
  nascar: "nascar", motogp: "motogp", wrc: "wrc", wec: "wec", imsa: "imsa" };
const relative = "projects/motogp-predictions/website/public/data";
function put(path: string, data: unknown) {
  const file = join(root, path);
  mkdirSync(resolve(file, ".."), { recursive: true });
  writeFileSync(file, JSON.stringify(data));
}
function audit() {
  const code = `import { auditCircuitGeometry, hasCompleteVerifiedGeometry } from ${JSON.stringify(script)};
const entry = auditCircuitGeometry(${JSON.stringify(root)}).find(e => e.series === "motogp");
console.log(JSON.stringify({entry, complete: hasCompleteVerifiedGeometry([entry])}));`;
  return JSON.parse(execFileSync(process.execPath, [tsx, "-e", code], { encoding: "utf8", stdio: "pipe" }));
}
function hold(overrides = {}) {
  const snapshot = { preserved: "source fixture" };
  put("projects/motogp-predictions/data/official_2026.json", snapshot);
  put(`${relative}/publication_status.json`, {
    schemaVersion: 1, sport: "MotoGP", season: 2026, status: "held", reasonCode: "snapshot-event-identity",
    message: "Publication withheld", recovery: "Verified inputs required",
    sourceSnapshot: "projects/motogp-predictions/data/official_2026.json",
    snapshotSha256: createHash("sha256").update(JSON.stringify(snapshot)).digest("hex"),
    references: ["https://www.motogp.com/en/calendar/2026"],
    issues: [{ code: "event-identity-mismatch", message: "Mismatched event" }],
    routes: { rounds: [18, 19, 20], riders: ["MAM"] }, ...overrides,
  });
}
beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "circuit-hold-"));
  for (const [series, file] of Object.entries(sources)) {
    if (series !== "motogp") put(`projects/${series}-predictions/website/public/data/${file}.json`, { season: 2026, calendar: [] });
  }
});
afterEach(() => rmSync(root, { recursive: true, force: true }));

it("reports held geometry as unavailable, never verified coverage", () => {
  hold();
  expect(audit()).toMatchObject({ entry: { status: "publication-held", rounds: null, verified: 0 }, complete: false });
});
it("retains the ordinary inventory path when there is no hold", () => {
  put(`${relative}/motogp.json`, { season: 2026, calendar: [] });
  expect(audit()).toMatchObject({ entry: { status: "audited", rounds: 0 }, complete: true });
});
it("still fails on unexplained missing calendar data", () => {
  expect(() => audit()).toThrow();
});
it.each([{ snapshotSha256: "0".repeat(64) }, { sourceSnapshot: "../wrong.json" }, { issues: [] }])(
  "rejects malformed or unbound hold evidence %#", override => {
    hold(override);
    expect(() => audit()).toThrow();
  });
it("does not let a hold conceal still-published numeric artifacts", () => {
  hold();
  put(`${relative}/motogp.json`, { winnerHitRate: 1 });
  expect(() => audit()).toThrow();
});
