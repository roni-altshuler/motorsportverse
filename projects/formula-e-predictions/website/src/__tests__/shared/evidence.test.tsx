/**
 * The evidence-discipline contract.
 *
 * These tests assert the rules in docs/EVIDENCE.md that are enforced in the UI
 * rather than in Python: a losing comparison is printed, a closed calibration
 * gate is visible, a backtest is labelled, and an unavailable benchmark says so
 * instead of rendering nothing.
 *
 * Synced to every series site — edit the canonical copy under
 * projects/f1-predictions/website/src/__tests__/shared/.
 */
import { render, screen } from "@testing-library/react";

import { BaselineLadder } from "@/components/ui/BaselineLadder";
import { EmptyState } from "@/components/ui/EmptyState";
import { EvidencePanel, type EvidenceBlock } from "@/components/ui/EvidencePanel";
import { StatusBanner } from "@/components/ui/StatusBanner";

function comparison(overrides: Partial<EvidenceBlock["headline"]> = {}) {
  return {
    metric: "mean_position_error",
    baseline: "lastRace",
    baselineLabel: "Last race order",
    raceType: "race",
    lowerIsBetter: true,
    nRounds: 9,
    modelMean: 5.1,
    baselineMean: 7.4,
    improvement: 2.3,
    ciLow: 1.1,
    ciHigh: 3.4,
    verdict: "better",
    note: "the model beats last race order over 9 paired rounds",
    ...overrides,
  } as NonNullable<EvidenceBlock["headline"]>;
}

function block(overrides: Partial<EvidenceBlock> = {}): EvidenceBlock {
  const headline = comparison();
  return {
    available: true,
    season: 2026,
    generatedAt: "2026-07-08T06:28:26Z",
    roundsScored: 9,
    basis: "forward evaluation — each round was forecast before it ran",
    headline,
    comparisons: [headline],
    caveats: ["Metrics are only comparable within this series."],
    ...overrides,
  };
}

describe("EvidencePanel", () => {
  it("renders on every forecast page, even with no benchmark", () => {
    render(<EvidencePanel evidence={undefined} />);
    expect(screen.getByTestId("evidence-panel")).toBeInTheDocument();
    expect(screen.getByText(/treat every probability on this page as unverified/i))
      .toBeInTheDocument();
  });

  it("surfaces the reason a benchmark is missing", () => {
    render(
      <EvidencePanel
        evidence={{ available: false, reason: "no round has been scored yet this season" }}
      />,
    );
    expect(screen.getByText(/no round has been scored yet this season/i)).toBeInTheDocument();
  });

  it("leads with the gap to a baseline, not with a bare accuracy", () => {
    render(<EvidencePanel evidence={block()} />);
    // The verdict appears in the headline sentence AND in the table row, which
    // is deliberate — the sentence is what a skimming reader takes away.
    expect(screen.getAllByText(/beats the baseline/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/last race order/i).length).toBeGreaterThan(0);
  });

  it("PRINTS a losing comparison rather than hiding it", () => {
    const losing = comparison({
      verdict: "worse",
      improvement: -1.8,
      modelMean: 8.9,
      baselineMean: 7.1,
      note: "the model does NOT beat last race order",
    });
    render(<EvidencePanel evidence={block({ headline: losing, comparisons: [losing] })} />);
    expect(screen.getAllByText(/does NOT beat the baseline/i).length).toBeGreaterThan(0);
  });

  it("shows the sign on a negative gain", () => {
    const losing = comparison({ verdict: "worse", improvement: -1.8 });
    render(<EvidencePanel evidence={block({ headline: losing, comparisons: [losing] })} />);
    expect(screen.getByText("-1.80")).toBeInTheDocument();
  });

  it("does not claim a difference when the interval straddles zero", () => {
    const flat = comparison({
      verdict: "inconclusive",
      improvement: 0.1,
      ciLow: -0.6,
      ciHigh: 0.8,
    });
    render(<EvidencePanel evidence={block({ headline: flat, comparisons: [flat] })} />);
    expect(screen.getAllByText(/no difference demonstrated/i).length).toBeGreaterThan(0);
  });

  it("states that historical and live records are never merged", () => {
    render(<EvidencePanel evidence={block()} />);
    expect(screen.getByText(/never merged/i)).toBeInTheDocument();
  });

  it("says in words which side of zero the interval falls", () => {
    render(<EvidencePanel evidence={block()} />);
    expect(screen.getByText(/whole interval is above zero/i)).toBeInTheDocument();
  });

  it("spells out a measured shortfall rather than leaving it to be read off a CI", () => {
    const losing = comparison({
      verdict: "worse",
      improvement: -0.78,
      ciLow: -1.29,
      ciHigh: -0.22,
    });
    render(<EvidencePanel evidence={block({ headline: losing, comparisons: [losing] })} />);
    expect(screen.getByText(/BELOW zero, so the shortfall is measured, not noise/i))
      .toBeInTheDocument();
  });

  it("omits the bootstrap sentence when there is no interval", () => {
    const noCi = comparison({ ciLow: null, ciHigh: null, verdict: "insufficient" });
    render(<EvidencePanel evidence={block({ headline: noCi, comparisons: [noCi] })} />);
    expect(screen.queryByText(/Paired bootstrap/i)).not.toBeInTheDocument();
  });

  it("prints every caveat, including on a win", () => {
    render(<EvidencePanel evidence={block()} />);
    expect(screen.getByText(/only comparable within this series/i)).toBeInTheDocument();
  });

  it("renders an absent mean as the em dash, never as zero", () => {
    const partial = comparison({ modelMean: null, baselineMean: null, improvement: null });
    render(<EvidencePanel evidence={block({ headline: partial, comparisons: [partial] })} />);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});

describe("BaselineLadder", () => {
  const rows = [
    { label: "This model", value: 5.1, n: 9, isModel: true },
    { label: "Last race order", value: 7.4, n: 9 },
    { label: "Grid order", value: 6.2, n: 9 },
  ];

  it("keeps every baseline visible — they are never deleted", () => {
    render(<BaselineLadder rows={rows} />);
    expect(screen.getByText("Last race order")).toBeInTheDocument();
    expect(screen.getByText("Grid order")).toBeInTheDocument();
  });

  it("ranks by the metric, so a beaten model appears below its baseline", () => {
    const beaten = [
      { label: "This model", value: 9.2, n: 9, isModel: true },
      { label: "Grid order", value: 6.2, n: 9 },
    ];
    render(<BaselineLadder rows={beaten} />);
    expect(screen.getByText(/ranks 2 of 2/i)).toBeInTheDocument();
    expect(screen.getByText(/does not serve/i)).toBeInTheDocument();
  });

  it("says nothing scolding when the model leads", () => {
    render(<BaselineLadder rows={rows} />);
    expect(screen.queryByText(/does not serve/i)).not.toBeInTheDocument();
  });

  it("shows an unmeasured baseline as unmeasured instead of dropping it", () => {
    render(<BaselineLadder rows={[...rows, { label: "Championship order", value: null }]} />);
    expect(screen.getByText(/championship order — not yet measured/i)).toBeInTheDocument();
  });

  it("prints every value as text beside its bar", () => {
    render(<BaselineLadder rows={rows} />);
    expect(screen.getByText("5.10")).toBeInTheDocument();
    expect(screen.getByText("7.40")).toBeInTheDocument();
  });

  it("respects higher-is-better metrics", () => {
    render(
      <BaselineLadder
        metricLabel="Top-5 NDCG"
        lowerIsBetter={false}
        rows={[
          { label: "This model", value: 0.69, isModel: true },
          { label: "Last race order", value: 0.51 },
        ]}
      />,
    );
    expect(screen.queryByText(/does not serve/i)).not.toBeInTheDocument();
  });
});

describe("StatusBanner", () => {
  it("labels a backtest a backtest, in words", () => {
    render(<StatusBanner kind="backtest">Replayed after the fact.</StatusBanner>);
    expect(screen.getByText("Backtest")).toBeInTheDocument();
    expect(screen.getByTestId("status-banner")).toHaveAttribute("data-kind", "backtest");
  });

  it("makes a closed calibration gate visible", () => {
    render(<StatusBanner kind="uncalibrated">Raw model output.</StatusBanner>);
    expect(screen.getByText("Uncalibrated")).toBeInTheDocument();
  });

  it("labels a simulated league as simulated", () => {
    render(<StatusBanner kind="fantasy">Fan-made and entirely fictional.</StatusBanner>);
    expect(screen.getByText("Simulated")).toBeInTheDocument();
  });

  it("is not dismissible — there is no close control", () => {
    render(<StatusBanner kind="backtest">Replayed.</StatusBanner>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("EmptyState", () => {
  it("renders absence as a fact rather than as a blank", () => {
    render(
      <EmptyState
        title="No rounds scored yet"
        description="The season has not started."
        hint="The first forecast appears after round 1."
      />,
    );
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
    expect(screen.getByText("No rounds scored yet")).toBeInTheDocument();
    expect(screen.getByText(/first forecast appears/i)).toBeInTheDocument();
  });

  it("announces itself to assistive tech", () => {
    render(<EmptyState title="Nothing here" />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
