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

    // Remove only the private fiber in compiled source: emitted server markup
    // stays identical, but the renderer replays main against its own contents.
    const replay = probe(mode, "--without-child-boundary");
    expect(replay.serverMarkupSha256).toBe(matching.serverMarkupSha256);
    expect(replay.matchingMarkup).toBe(true);
    expect(replay.errors).toHaveLength(1);
    expect(replay.errors[0].message).toContain(mode === "production" ? "#418" : "Hydration failed");
    expect(replay.errors[0].stack).toContain("replaySuspendedUnitOfWork");
    expect(replay.mainReused).toBe(false);
    expect(replay.contentReused).toBe(false);

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
