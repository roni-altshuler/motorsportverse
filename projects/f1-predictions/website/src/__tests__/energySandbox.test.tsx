import { fireEvent, render, screen, within } from "@testing-library/react";
import EnergySandbox from "@/components/engineering/EnergySandbox";
import {
  DEFAULT_ENERGY_ASSUMPTIONS,
  ENERGY_DURATION_SECONDS,
  ENERGY_FIELDS,
  energyDraft,
  parseEnergyDraft,
  simulateEnergy,
  type EnergyAssumptions,
  type EnergyField,
} from "@/lib/energySandbox";

const simulate = (override: Partial<EnergyAssumptions> = {}) =>
  simulateEnergy({ ...DEFAULT_ENERGY_ASSUMPTIONS, ...override });

test("default example agrees with independent power × time energy accounting", () => {
  const run = simulate();
  // Six 30 s deployments at 60 kW = 3 kWh delivered. Six 20 s inputs
  // at 50 kW = 5/3 kWh incoming. At 90% efficiency the store draws 10/3
  // and recovers 1.5; 2.8 + 1.5 - 10/3 = 29/30 kWh remains.
  expect(run.initialEnergyKWh).toBeCloseTo(2.8, 12);
  expect(run.deliveredKWh).toBeCloseTo(3, 12);
  expect(run.drawnKWh).toBeCloseTo(10 / 3, 12);
  expect(run.availableRegenKWh).toBeCloseTo(5 / 3, 12);
  expect(run.recoveredKWh).toBeCloseTo(1.5, 12);
  expect(run.conversionLossKWh).toBeCloseTo(0.5, 12);
  expect(run.finalEnergyKWh).toBeCloseTo(29 / 30, 12);
  expect(run.finalSocPercent).toBeCloseTo((29 / 30 / 4) * 100, 10);
  expect(run.unmetDeploymentKWh).toBeCloseTo(0, 12);
  expect(run.rejectedRegenKWh).toBeCloseTo(0, 12);
  expect(run.deploymentLimitedSeconds).toBe(0);
  expect(run.regenerationLimitedSeconds).toBe(0);
  expect(run.points).toHaveLength(ENERGY_DURATION_SECONDS + 1);
  expect(run.cycles).toHaveLength(6);
});

test("one complete cycle includes a loss-free coast, then regeneration", () => {
  const run = simulate();
  expect(run.points[30].energyKWh).toBeCloseTo(2.8 - 5 / 9, 12);
  expect(run.points[40].energyKWh).toBe(run.points[30].energyKWh);
  expect(run.points[60].energyKWh).toBeCloseTo(2.8 - 5 / 9 + 0.25, 12);
  expect(run.cycles[0].deliveredKWh).toBeCloseTo(0.5, 12);
  expect(run.cycles[0].recoveredKWh).toBeCloseTo(0.25, 12);
});

test("zero power preserves stored energy, regardless of conversion efficiency", () => {
  const run = simulate({ deploymentKW: 0, regenerationKW: 0, efficiencyPercent: 50 });
  expect(run.finalEnergyKWh).toBe(run.initialEnergyKWh);
  expect(run.points.every((point) => point.energyKWh === run.initialEnergyKWh)).toBe(true);
  expect(run.conversionLossKWh).toBe(0);
  expect(run.deploymentLimitedSeconds + run.regenerationLimitedSeconds).toBe(0);
});

test("empty storage cannot deliver energy and unmet demand is not a loss", () => {
  const run = simulate({ initialSocPercent: 0, deploymentKW: 200, regenerationKW: 0 });
  expect(run.finalEnergyKWh).toBe(0);
  expect(run.deliveredKWh).toBe(0);
  expect(run.drawnKWh).toBe(0);
  expect(run.conversionLossKWh).toBe(0);
  expect(run.unmetDeploymentKWh).toBeCloseTo(10, 12);
  expect(run.deploymentLimitedSeconds).toBe(180);
  expect(run.balanceResidualKWh).toBe(0);
});

test("full storage rejects incoming energy without fictitious conversion losses", () => {
  const run = simulate({ initialSocPercent: 100, deploymentKW: 0, regenerationKW: 150 });
  expect(run.finalEnergyKWh).toBe(4);
  expect(run.recoveredKWh).toBe(0);
  expect(run.rejectedRegenKWh).toBeCloseTo(5, 12);
  expect(run.availableRegenKWh).toBeCloseTo(5, 12);
  expect(run.conversionLossKWh).toBe(0);
  expect(run.regenerationLimitedSeconds).toBe(120);
});

test("fractional capacities at full charge never start above capacity or recover negative energy", () => {
  for (const capacityKWh of [0.73389, 0.7462, 1.731, 4.123]) {
    const run = simulate({
      capacityKWh,
      initialSocPercent: 100,
      deploymentKW: 0,
      regenerationKW: 150,
    });
    expect(run.initialEnergyKWh).toBe(capacityKWh);
    expect(
      run.points.every((point) => point.energyKWh === capacityKWh && point.socPercent === 100),
    ).toBe(true);
    expect(run.recoveredKWh).toBe(0);
    expect(run.conversionLossKWh).toBe(0);
    expect(run.rejectedRegenKWh).toBeCloseTo(5, 12);
  }
});

test("100% efficiency closes a lossless round trip with equal cycle energy", () => {
  const run = simulate({ deploymentKW: 40, regenerationKW: 60, efficiencyPercent: 100 });
  expect(run.finalEnergyKWh).toBeCloseTo(run.initialEnergyKWh, 12);
  expect(run.deliveredKWh).toBeCloseTo(2, 12);
  expect(run.recoveredKWh).toBeCloseTo(2, 12);
  expect(run.conversionLossKWh).toBe(0);
});

test("regeneration after an empty start can supply a later deployment", () => {
  const run = simulate({ initialSocPercent: 0, efficiencyPercent: 50 });
  expect(run.cycles[0].deliveredKWh).toBe(0);
  expect(run.cycles[0].recoveredKWh).toBeCloseTo(5 / 36, 12);
  expect(run.cycles[1].deliveredKWh).toBeCloseTo(5 / 72, 12);
  expect(run.deploymentLimitedSeconds).toBeGreaterThan(0);
});

test("capacity, nonnegative flows and two independent conservation identities hold across 720 scenarios", () => {
  for (const capacityKWh of [0.5, 0.73389, 1.731, 4, 20])
    for (const initialSocPercent of [0, 37.5, 100])
      for (const deploymentKW of [0, 0.3, 60, 200])
        for (const regenerationKW of [0, 0.7, 50, 150])
          for (const efficiencyPercent of [50, 90, 100]) {
            const run = simulate({
              capacityKWh,
              initialSocPercent,
              deploymentKW,
              regenerationKW,
              efficiencyPercent,
            });
            expect(
              run.points.every(
                (point) => Number.isFinite(point.energyKWh) && Number.isFinite(point.socPercent),
              ),
            ).toBe(true);
            expect(Math.min(...run.points.map((point) => point.energyKWh))).toBeGreaterThanOrEqual(
              0,
            );
            expect(Math.max(...run.points.map((point) => point.energyKWh))).toBeLessThanOrEqual(
              capacityKWh,
            );
            expect(Math.min(...run.points.map((point) => point.socPercent))).toBeGreaterThanOrEqual(
              0,
            );
            expect(Math.max(...run.points.map((point) => point.socPercent))).toBeLessThanOrEqual(
              100,
            );
            for (const field of [
              "deliveredKWh",
              "drawnKWh",
              "availableRegenKWh",
              "recoveredKWh",
              "conversionLossKWh",
              "rejectedRegenKWh",
              "unmetDeploymentKWh",
            ] as const) {
              expect(Number.isFinite(run[field])).toBe(true);
              expect(run[field]).toBeGreaterThanOrEqual(0);
            }
            expect(run.initialEnergyKWh + run.recoveredKWh).toBeCloseTo(
              run.finalEnergyKWh + run.drawnKWh,
              10,
            );
            expect(run.initialEnergyKWh + run.availableRegenKWh).toBeCloseTo(
              run.finalEnergyKWh + run.deliveredKWh + run.conversionLossKWh + run.rejectedRegenKWh,
              10,
            );
            expect(run.deliveredKWh + run.unmetDeploymentKWh).toBeCloseTo(
              (deploymentKW * 180) / 3600,
              10,
            );
            expect(run.recoveredKWh / (efficiencyPercent / 100) + run.rejectedRegenKWh).toBeCloseTo(
              (regenerationKW * 120) / 3600,
              10,
            );
            expect(Math.abs(run.balanceResidualKWh)).toBeLessThan(1e-10);
          }
});

test.each(Object.keys(ENERGY_FIELDS) as EnergyField[])(
  "rejects invalid %s rather than silently clamping",
  (key) => {
    const field = ENERGY_FIELDS[key];
    for (const value of [NaN, Infinity, -Infinity, field.min - 0.1, field.max + 0.1]) {
      expect(() => simulate({ [key]: value })).toThrow(RangeError);
    }
    const blank = parseEnergyDraft({ ...energyDraft(), [key]: " " });
    expect(blank.valid).toBe(false);
    expect(blank.errors[key]).toContain("Enter a number");
  },
);

test("decimal assumptions remain valid and no input object is mutated", () => {
  const assumptions = Object.freeze({
    ...DEFAULT_ENERGY_ASSUMPTIONS,
    capacityKWh: 4.123,
    efficiencyPercent: 91.25,
  });
  expect(parseEnergyDraft(energyDraft(assumptions)).valid).toBe(true);
  expect(simulateEnergy(assumptions).finalEnergyKWh).toBeGreaterThan(0);
  expect(assumptions.capacityKWh).toBe(4.123);
});

test("controls update the actual result; invalid inputs hide it and reset restores it", () => {
  render(<EnergySandbox />);
  const region = screen.getByRole("region", { name: "Energy management sandbox." });
  expect(
    within(region).getByRole("img", { name: /Synthetic charge over 360 seconds/ }),
  ).toBeVisible();
  expect(within(region).getByRole("status")).toHaveTextContent("Final charge 24.2 percent");
  const deployment = screen.getByRole("spinbutton", { name: "Deployment output (kW)" });
  fireEvent.change(deployment, { target: { value: "200" } });
  expect(screen.getByText("Power curtailed at a limit")).toBeVisible();
  expect(screen.getByText(/Empty reservoir:/)).toBeVisible();
  fireEvent.change(deployment, { target: { value: "201" } });
  expect(deployment).toHaveAttribute("aria-invalid", "true");
  expect(screen.queryByTestId("energy-results")).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Results paused");
  expect(screen.getByText("Enter a number from 0 to 200 kW.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: /^Reset$/ }));
  expect(deployment).toHaveValue(60);
  expect(screen.getByRole("status")).toHaveTextContent("Final charge 24.2 percent");
});

test("empty input does not become zero; accessible details and learning links retain their limits", () => {
  render(<EnergySandbox />);
  const capacity = screen.getByRole("spinbutton", { name: "Usable capacity (kWh)" });
  fireEvent.change(capacity, { target: { value: "" } });
  expect(capacity).toHaveAttribute("aria-invalid", "true");
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
  fireEvent.change(capacity, { target: { value: "4" } });
  expect(screen.getByRole("table")).toHaveAccessibleName(/Each 60-second cycle/);
  expect(screen.getByText(/No voltage, current, temperature/)).toBeVisible();
  expect(screen.getByText(/energy proxy is educational/)).toHaveTextContent(
    "no measured telemetry",
  );
  for (const name of ["MATLAB Onramp", "Simulink Onramp", "Simscape Battery Onramp"]) {
    const link = screen.getByRole("link", { name: new RegExp(name) });
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("https://matlabacademy.mathworks.com/details/"),
    );
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  }
});
