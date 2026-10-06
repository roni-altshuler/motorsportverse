import { renderToStaticMarkup } from "react-dom/server";
import { within } from "@testing-library/react";
import { RaceDetail } from "@/components/race-detail/RaceDetail";
import { getCircuit, getRound } from "@/lib/f2data";

jest.mock("@/lib/useReducedMotion", () => ({ useReducedMotion: () => true }));
jest.mock("@/lib/SeasonProvider", () => ({
  useSeason: () => ({ basePath: "/data", year: 2026, index: null }),
}));

afterEach(() => { document.body.innerHTML = ""; });

function circuitSection(roundNumber: number, venueKey: string) {
  const round = getRound(roundNumber);
  if (!round) throw new Error(`Missing saved round ${roundNumber}`);
  document.body.innerHTML = renderToStaticMarkup(
    <RaceDetail round={round} probabilities={null} geometry={getCircuit(venueKey)} />,
  );
  const section = within(document.body).getByText("Venue & circuit").closest("details");
  if (!section) throw new Error("Missing circuit disclosure");
  return section;
}

test("retained unreviewed outline cannot claim verification in the race disclosure", () => {
  const section = circuitSection(4, "monaco");
  expect(within(section).getByRole("img", { name: "Circuit layout", hidden: true })).toBeInTheDocument();
  expect(section).toHaveTextContent("Layout review pending");
  expect(section).toHaveTextContent("This existing circuit outline is retained while layout review is pending.");
  expect(section).toHaveTextContent("An interactive circuit explorer requires a reviewed layout and is not available here.");
  expect(section).not.toHaveTextContent(/\bverified\b/i);
});

test("quarantined outline copy describes absence without claiming a retained or verified map", () => {
  const section = circuitSection(7, "silverstone");
  expect(within(section).queryByRole("img", { name: "Circuit layout", hidden: true })).not.toBeInTheDocument();
  expect(section).toHaveTextContent("No circuit outline is available for this event.");
  expect(section).not.toHaveTextContent(/outline is retained|\bverified\b/i);
});
