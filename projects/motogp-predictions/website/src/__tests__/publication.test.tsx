import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import PublicationHoldNotice from "@/components/PublicationHoldNotice";
import { getPublicationHold, type PublicationHold } from "@/lib/publication";

const hold: PublicationHold = {
  schemaVersion: 1, sport: "MotoGP", status: "held", reasonCode: "snapshot-event-identity", season: 2026,
  message: "MotoGP forecasts and season figures are withheld while event identities are verified.",
  recovery: "Verified inputs and supported coverage are required.",
  sourceSnapshot: "data/official_2026.json", snapshotSha256: "a".repeat(64),
  references: ["https://www.motogp.com/en/calendar/2026"],
  issues: [{ code: "event-identity-mismatch", round: 18, message: "Round 18 is paired with a different scheduled event.",
    scheduled: { venue: "Phillip Island", date: "2026-10-25" },
    recorded: { venue: "Sepang", date: "2026-11-01" }, matchingScheduledRounds: [19] }],
  routes: { rounds: [18, 19, 20], riders: ["MAM"] },
};

it("shows the exact mismatch without scoring a withheld publication", () => {
  render(<PublicationHoldNotice hold={hold} />);
  expect(screen.getByRole("heading", { name: "Publication temporarily withheld" })).toBeInTheDocument();
  expect(screen.getByText(/Scheduled: Phillip Island/)).toHaveTextContent("Stored result: Sepang");
  expect(screen.getByText(/scheduled round 19/)).toBeInTheDocument();
  expect(screen.queryByText(/Not yet scored|0%|Winner match/)).not.toBeInTheDocument();
  expect(screen.getByText(/existing forecasts have not been relabeled/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Official MotoGP calendar" })).toHaveAttribute("href", hold.references[0]);
});

it("describes unsupported coverage without inventing an event mismatch", () => {
  render(<PublicationHoldNotice hold={{ ...hold, issues: [{ code: "unsupported-completed-round-gap", message: "Completed IDs contain a gap." }] }} />);
  expect(screen.getByText(/available event coverage cannot yet be published safely/)).toBeInTheDocument();
  expect(screen.queryByText(/Results were paired/)).not.toBeInTheDocument();
});

let dir: string;
beforeEach(() => { dir = mkdtempSync(join(tmpdir(), "motogp-publication-")); });
afterEach(() => rmSync(dir, { recursive: true, force: true }));

it("loads a valid hold and distinguishes genuine absence", () => {
  expect(getPublicationHold(dir)).toBeNull();
  writeFileSync(join(dir, "publication_status.json"), JSON.stringify(hold));
  expect(getPublicationHold(dir)).toEqual(hold);
});

it.each([{}, { ...hold, status: "published" }, { ...hold, snapshotSha256: "bad" },
  { ...hold, issues: [] }, { ...hold, routes: null }, { ...hold, references: ["https://"] },
  { ...hold, references: ["https:// bad host"] }, { ...hold, references: ["javascript:alert(1)"] },
  { ...hold, references: ["https://example.com/"] }])("fails closed on malformed metadata %#", invalid => {
  writeFileSync(join(dir, "publication_status.json"), JSON.stringify(invalid));
  expect(() => getPublicationHold(dir)).toThrow();
});

it("blocks stale numerical loaders even when old files remain", () => {
  const cwd = jest.spyOn(process, "cwd").mockReturnValue(dir);
  const data = join(dir, "public/data");
  mkdirSync(join(data, "rounds"), { recursive: true });
  writeFileSync(join(data, "motogp.json"), JSON.stringify({ season: 2026, winnerHitRate: 1 }));
  writeFileSync(join(data, "rounds/round_18.json"), JSON.stringify({ round: 18, winnerHitRate: 1 }));
  try {
    jest.isolateModules(() => {
      const loader = jest.requireActual<typeof import("@/lib/motogpData")>("@/lib/motogpData");
      expect(loader.getMotogpData()).toMatchObject({ winnerHitRate: 1 }); // warm cache
      expect(loader.getRound(18)).toMatchObject({ round: 18 });
      writeFileSync(join(data, "publication_status.json"), JSON.stringify(hold));
      expect(loader.allRoundNumbers()).toEqual([18, 19, 20]);
      expect(loader.getRound(18)).toBeNull();
      expect(() => loader.getMotogpData()).toThrow(/withheld/);
    });
  } finally {
    cwd.mockRestore();
  }
});
