import { render, screen, within } from "@testing-library/react";
import PredictionFreshnessPanel from "@/components/race-detail/PredictionFreshnessPanel";
import KeyFactorsPanel from "@/components/race-detail/KeyFactorsPanel";
import {
  artifactTimestamp,
  compareArtifactTimes,
  qualifyingAssumption,
  weatherAssumption,
  type FreshnessInput,
  type ProbabilityMetadata,
} from "@/lib/predictionFreshness";
import publishedRanking from "../../public/data/rounds/round_16.json";
import publishedProbability from "../../public/data/probabilities/round_16.json";
import type { ClassificationEntry } from "@/types";

const missing: FreshnessInput = { round: 16 };
const meta: ProbabilityMetadata = { round: 16, season: 2026, generatedAt: "2026-09-27T01:06:55Z" };
// Scenario fixtures must not inherit dates, sources or factors from mutable exports.
const ranking: FreshnessInput = {
  round: 16,
  generatedAt: "2026-06-27T17:06:41Z",
  qualifyingDataAvailable: false,
  gridProvenance: "estimated",
  dataFreshness: { qualifyingSource: "model estimate", weatherSource: "static" },
  weatherData: { rainProbability: 0.2, temperatureC: 30, source: "static" },
};
const probability = meta;
const knownRanking: FreshnessInput = {
  ...ranking,
  generatedAt: "2026-09-26T09:00:59Z",
  qualifyingDataAvailable: true,
  gridProvenance: "real-quali-verified",
  dataFreshness: { qualifyingSource: "FastF1", weatherSource: "api" },
  weatherData: { rainProbability: 0, temperatureC: 26.5, source: "api" },
};
const classification: ClassificationEntry[] = [
  {
    position: 1,
    driver: "QA1",
    driverFullName: "Test Driver",
    team: "Test Team",
    teamColor: "#ffffff",
    predictedTime: 3600,
    gap: "Leader",
    points: 25,
  },
];

test("independent dated artifacts retain estimated inputs and an unknown cutoff", () => {
  render(<PredictionFreshnessPanel data={ranking} probabilities={probability} season={2026} />);
  const panel = screen.getByRole("region", { name: "Freshness & Sources" });
  expect(within(panel).getByText("27 Jun 2026, 17:06:41 UTC")).toHaveAttribute(
    "datetime",
    "2026-06-27T17:06:41.000Z",
  );
  expect(within(panel).getByText("27 Sept 2026, 01:06:55 UTC")).toHaveAttribute(
    "datetime",
    "2026-09-27T01:06:55.000Z",
  );
  expect(within(panel).getByRole("status")).toHaveTextContent("Different export times");
  expect(within(panel).getByText(/ranking export is older/)).toHaveTextContent(
    "does not establish refreshed rankings or inputs",
  );
  expect(within(panel).getByText("Estimated qualifying")).toBeVisible();
  expect(within(panel).getByText("Static weather estimate")).toBeVisible();
  expect(within(panel).getByText("Not published")).toBeVisible();
});

test("recorded verified qualifying and API weather do not invent an input cutoff", () => {
  render(<PredictionFreshnessPanel data={knownRanking} probabilities={null} season={2026} />);
  expect(screen.getByText("Verified grid recorded")).toBeVisible();
  expect(screen.getByText("API weather recorded")).toBeVisible();
  expect(screen.getByText("Not published")).toBeVisible();
  expect(screen.getByText(/could not be loaded/)).toBeVisible();
});

test("missing metadata never falls back to model or static sources", () => {
  render(
    <PredictionFreshnessPanel
      data={missing}
      probabilities={{ ...meta, generatedAt: "" }}
      season={2026}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Incomplete time metadata");
  expect(screen.getAllByText("Not published")).toHaveLength(3);
  expect(screen.getByText("Qualifying input unverified")).toBeVisible();
  expect(screen.getByText("Weather input unverified")).toBeVisible();
  expect(screen.queryByText(/static estimate|model pipeline/i)).not.toBeInTheDocument();
});

test("loading a probability file is distinct from unavailable or unpublished metadata", () => {
  const { rerender } = render(
    <PredictionFreshnessPanel
      data={ranking}
      probabilities={null}
      probabilityLoading
      season={2026}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Reading probability metadata");
  expect(screen.getByText("Reading metadata…")).toBeVisible();
  expect(screen.queryByText("Unavailable")).not.toBeInTheDocument();
  rerender(<PredictionFreshnessPanel data={ranking} probabilities={null} season={2026} />);
  expect(screen.getByText("Unavailable")).toBeVisible();
});

test.each([{ round: 15 }, { season: 2025 }])(
  "conflicting probability identity does not borrow its date: %j",
  (override) => {
    render(
      <PredictionFreshnessPanel
        data={ranking}
        probabilities={{ ...meta, ...override }}
        season={2026}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Probability identity conflict");
    expect(screen.getByText(/different round or season/)).toBeVisible();
    expect(screen.queryByText("27 Sept 2026, 01:06:55 UTC")).not.toBeInTheDocument();
    expect(screen.queryByText(/ranking export is older/)).not.toBeInTheDocument();
  },
);

test("invalid time is visibly untrusted and is not ordered against a valid time", () => {
  render(
    <PredictionFreshnessPanel
      data={{ ...ranking, generatedAt: "2026-02-30T09:00:00Z" }}
      probabilities={meta}
      season={2026}
    />,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Timestamp needs review");
  expect(screen.getByText("Invalid timestamp")).toBeVisible();
  expect(screen.queryByText(/export is older/)).not.toBeInTheDocument();
});

test.each([
  "not a date",
  "2026-09-27",
  "2026-09-27T01:06:55",
  "2026-02-30T01:06:55Z",
  "2026-13-01T01:06:55Z",
  "2026-09-27T24:00:00Z",
  17,
])("rejects ambiguous or invalid timestamps: %s", (value) => {
  expect(artifactTimestamp(value).state).toBe("invalid");
});

test.each([undefined, null, "", "   "])("missing time stays missing: %s", (value) => {
  expect(artifactTimestamp(value).state).toBe("missing");
});

test("offset timestamps compare as instants; matching times still do not prove a cutoff", () => {
  const a = artifactTimestamp("2026-09-27T03:06:55+02:00");
  const b = artifactTimestamp(meta.generatedAt);
  expect(compareArtifactTimes(a, b).label).toBe("Matching export times");
  render(
    <PredictionFreshnessPanel
      data={{ ...ranking, generatedAt: "2026-09-27T03:06:55+02:00" }}
      probabilities={meta}
      season={2026}
    />,
  );
  expect(screen.getByText(/do not establish when forecast inputs were frozen/)).toBeVisible();
});

test("an older probability artifact receives the reverse warning", () => {
  expect(
    compareArtifactTimes(
      artifactTimestamp(meta.generatedAt),
      artifactTimestamp(ranking.generatedAt),
    ).note,
  ).toMatch(/probability export is older/);
});

test("contradictory input metadata is surfaced rather than silently selected", () => {
  const contradictory = {
    ...ranking,
    qualifyingDataAvailable: true,
    dataFreshness: { qualifyingSource: "model estimate", weatherSource: "api" },
  };
  expect(qualifyingAssumption(contradictory).label).toBe("Conflicting qualifying metadata");
  expect(weatherAssumption(contradictory).label).toBe("Conflicting weather metadata");
  expect(
    qualifyingAssumption({
      ...missing,
      qualifyingDataAvailable: false,
      gridProvenance: "real-quali-verified",
    }).warning,
  ).toBe(true);
});

test("cached weather records uncertainty about input age", () => {
  expect(
    weatherAssumption({ ...missing, dataFreshness: { weatherSource: "cached" } }).detail,
  ).toMatch(/age is not published/);
});

test("absent factor data describes this export without promising a future run; graded hiding remains", () => {
  const { rerender } = render(<KeyFactorsPanel classification={classification} />);
  expect(screen.getByText("Factor data unavailable")).toBeVisible();
  expect(screen.getByText(/not included in this ranking export/)).toBeVisible();
  expect(screen.queryByText(/next model run|publish with|awaiting/i)).not.toBeInTheDocument();
  rerender(<KeyFactorsPanel classification={classification} graded />);
  expect(screen.queryByText("Factor data unavailable")).not.toBeInTheDocument();
});

test("recorded factors remain visible, including on graded exports", () => {
  render(
    <KeyFactorsPanel
      classification={classification.map((entry) => ({
        ...entry,
        keyFactors: [{ factor: "Qualifying pace", weight: 1, direction: "advantage" }],
      }))}
      graded
    />,
  );
  expect(screen.getByText("Qualifying pace")).toBeVisible();
  expect(screen.queryByText("Factor data unavailable")).not.toBeInTheDocument();
});

test("published artifacts display their own timestamps without fixing export dates", () => {
  render(
    <PredictionFreshnessPanel
      data={publishedRanking}
      probabilities={publishedProbability}
      season={2026}
    />,
  );
  const panel = screen.getByRole("region", { name: "Freshness & Sources" });
  expect(Array.from(panel.querySelectorAll("time"), (time) => time.dateTime)).toEqual([
    new Date(publishedRanking.generatedAt).toISOString(),
    new Date(publishedProbability.generatedAt).toISOString(),
  ]);
  expect(within(panel).getByText("Not published")).toBeVisible();
  expect(
    within(panel).getByText(/Export times do not establish when forecast inputs were frozen/),
  ).toBeVisible();
});
