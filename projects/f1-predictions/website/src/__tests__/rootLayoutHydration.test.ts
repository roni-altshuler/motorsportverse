import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

interface Probe {
  matchingMarkup: boolean;
  serverMarkupSha256: string;
  pendingLog: string[];
  errors: { message: string; stack: string }[];
  mainReused: boolean;
  contentReused: boolean;
}

type RendererMode = "production" | "development";

function probe(mode: RendererMode, ...args: string[]): Probe {
  // A fresh child keeps Next's bundled React and mocked scheduler isolated
  // from the package React used by the ordinary component tests.
  const result = spawnSync(
    process.execPath,
    [resolve("../../../scripts/qa/root_layout_hydration.cjs"), ...args],
    { cwd: process.cwd(), env: { ...process.env, NODE_ENV: mode }, encoding: "utf8" },
  );
  if (result.status !== 0) throw new Error(result.stderr || `Probe exited ${result.status}`);
  return JSON.parse(result.stdout) as Probe;
}

describe.each(["production", "development"] as const)("root route hydration (%s)", (mode) => {
  it("retains matching nodes through a pending route, and detects real mismatches", () => {
    const matching = probe(mode);
    expect(matching.matchingMarkup).toBe(true);
    expect(matching.pendingLog).toEqual(["read:pending"]);
    expect(matching.errors).toEqual([]);
    expect(matching.mainReused).toBe(true);
    expect(matching.contentReused).toBe(true);

    // Next 16.3.8's bundled renderer also retains matching nodes without the
    // private child boundary. Keep this controlled variant explicit instead
    // of requiring the old renderer's replay failure to remain present.
    const replay = probe(mode, "--without-child-boundary");
    expect(replay.serverMarkupSha256).toBe(matching.serverMarkupSha256);
    expect(replay.matchingMarkup).toBe(true);
    expect(replay.pendingLog).toEqual(["read:pending"]);
    expect(replay.errors).toEqual([]);
    expect(replay.mainReused).toBe(true);
    expect(replay.contentReused).toBe(true);

    // Alter the server fixture before parsing; the repair must not hide a
    // genuine mismatch or introduce hydration-warning suppression.
    const different = probe(mode, "--different-server-text");
    expect(different.matchingMarkup).toBe(false);
    expect(different.errors).toHaveLength(1);
    expect(different.errors[0].message).toContain(
      mode === "production" ? "#418" : "Hydration failed",
    );
    expect(different.mainReused).toBe(true);
    expect(different.contentReused).toBe(false);
  }, 15000);
});
