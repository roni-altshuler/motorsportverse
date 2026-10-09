/** Original educational energy reservoir. No telemetry or vehicle physics. */
export const ENERGY_FIELDS = {
  capacityKWh: { label: "Usable capacity", unit: "kWh", min: 0.5, max: 20 },
  initialSocPercent: { label: "Starting charge", unit: "%", min: 0, max: 100 },
  deploymentKW: { label: "Deployment output", unit: "kW", min: 0, max: 200 },
  regenerationKW: { label: "Available regeneration", unit: "kW", min: 0, max: 150 },
  efficiencyPercent: { label: "Conversion efficiency", unit: "%", min: 50, max: 100 },
} as const;

export type EnergyField = keyof typeof ENERGY_FIELDS;
export type EnergyAssumptions = Record<EnergyField, number>;
export type EnergyDraft = Record<EnergyField, string>;
export const DEFAULT_ENERGY_ASSUMPTIONS: EnergyAssumptions = {
  capacityKWh: 4,
  initialSocPercent: 70,
  deploymentKW: 60,
  regenerationKW: 50,
  efficiencyPercent: 90,
};
export const ENERGY_CYCLE = {
  deploySeconds: 30,
  coastSeconds: 10,
  regenerateSeconds: 20,
  repeats: 6,
};
export const ENERGY_DURATION_SECONDS =
  (ENERGY_CYCLE.deploySeconds + ENERGY_CYCLE.coastSeconds + ENERGY_CYCLE.regenerateSeconds) *
  ENERGY_CYCLE.repeats;

export function energyDraft(assumptions = DEFAULT_ENERGY_ASSUMPTIONS): EnergyDraft {
  return Object.fromEntries(
    Object.entries(assumptions).map(([key, value]) => [key, String(value)]),
  ) as EnergyDraft;
}

export function validateEnergyAssumptions(assumptions: EnergyAssumptions) {
  const errors: Partial<Record<EnergyField, string>> = {};
  for (const key of Object.keys(ENERGY_FIELDS) as EnergyField[]) {
    const field = ENERGY_FIELDS[key];
    const value = assumptions[key];
    if (!Number.isFinite(value) || value < field.min || value > field.max) {
      errors[key] = `Enter a number from ${field.min} to ${field.max} ${field.unit}.`;
    }
  }
  return errors;
}

export function parseEnergyDraft(draft: EnergyDraft) {
  const assumptions = Object.fromEntries(
    Object.entries(draft).map(([key, value]) => [key, value.trim() === "" ? NaN : Number(value)]),
  ) as EnergyAssumptions;
  const errors = validateEnergyAssumptions(assumptions);
  return { assumptions, errors, valid: Object.keys(errors).length === 0 };
}

export type EnergyFlows = {
  deliveredKWh: number;
  drawnKWh: number;
  availableRegenKWh: number;
  recoveredKWh: number;
  conversionLossKWh: number;
  rejectedRegenKWh: number;
  unmetDeploymentKWh: number;
  deploymentLimitedSeconds: number;
  regenerationLimitedSeconds: number;
};
export type EnergyPoint = { seconds: number; energyKWh: number; socPercent: number };
export type EnergyCycleResult = EnergyFlows & {
  cycle: number;
  endEnergyKWh: number;
  endSocPercent: number;
};
export type EnergyRun = EnergyFlows & {
  initialEnergyKWh: number;
  finalEnergyKWh: number;
  finalSocPercent: number;
  balanceResidualKWh: number;
  points: EnergyPoint[];
  cycles: EnergyCycleResult[];
};
const emptyFlows = (): EnergyFlows => ({
  deliveredKWh: 0,
  drawnKWh: 0,
  availableRegenKWh: 0,
  recoveredKWh: 0,
  conversionLossKWh: 0,
  rejectedRegenKWh: 0,
  unmetDeploymentKWh: 0,
  deploymentLimitedSeconds: 0,
  regenerationLimitedSeconds: 0,
});

export function simulateEnergy(assumptions: EnergyAssumptions): EnergyRun {
  if (Object.keys(validateEnergyAssumptions(assumptions)).length) {
    throw new RangeError(
      "Energy assumptions must be finite and within the educational sandbox bounds.",
    );
  }
  const { capacityKWh, initialSocPercent, deploymentKW, regenerationKW, efficiencyPercent } =
    assumptions;
  const efficiency = efficiencyPercent / 100;
  // Normalize first: C × 100 / 100 can round above C for a fractional
  // capacity (for example 0.73389), creating negative regeneration headroom.
  const initialEnergyKWh = capacityKWh * (initialSocPercent / 100);
  let energyKWh = initialEnergyKWh;
  const totals = emptyFlows();
  const points: EnergyPoint[] = [{ seconds: 0, energyKWh, socPercent: initialSocPercent }];
  const cycles: EnergyCycleResult[] = [];
  const cycleSeconds =
    ENERGY_CYCLE.deploySeconds + ENERGY_CYCLE.coastSeconds + ENERGY_CYCLE.regenerateSeconds;

  for (let cycle = 1; cycle <= ENERGY_CYCLE.repeats; cycle++) {
    const flows = emptyFlows();
    for (let second = 0; second < cycleSeconds; second++) {
      // One-second intervals: kW × seconds / 3600 = kWh. Output demand is
      // measured after conversion; incoming regeneration is before conversion.
      if (second < ENERGY_CYCLE.deploySeconds) {
        const requestedOutput = deploymentKW / 3600;
        const drawn = Math.min(energyKWh, requestedOutput / efficiency);
        const delivered = drawn * efficiency;
        const unmet = Math.max(0, requestedOutput - delivered);
        energyKWh -= drawn;
        flows.drawnKWh += drawn;
        flows.deliveredKWh += delivered;
        flows.conversionLossKWh += drawn - delivered;
        flows.unmetDeploymentKWh += unmet;
        if (unmet > 1e-10) flows.deploymentLimitedSeconds++;
      } else if (second >= ENERGY_CYCLE.deploySeconds + ENERGY_CYCLE.coastSeconds) {
        const incoming = regenerationKW / 3600;
        const recovered = Math.min(capacityKWh - energyKWh, incoming * efficiency);
        const acceptedInput = recovered / efficiency;
        const rejected = Math.max(0, incoming - acceptedInput);
        // Keep the state bound exact even if the floating-point addition
        // rounds up at capacity. The ledger residual retains roundoff.
        energyKWh = Math.min(capacityKWh, energyKWh + recovered);
        flows.availableRegenKWh += incoming;
        flows.recoveredKWh += recovered;
        flows.conversionLossKWh += acceptedInput - recovered;
        flows.rejectedRegenKWh += rejected;
        if (rejected > 1e-10) flows.regenerationLimitedSeconds++;
      }
      points.push({
        seconds: (cycle - 1) * cycleSeconds + second + 1,
        energyKWh,
        socPercent: (energyKWh / capacityKWh) * 100,
      });
    }
    for (const key of Object.keys(totals) as (keyof EnergyFlows)[]) totals[key] += flows[key];
    cycles.push({
      cycle,
      ...flows,
      endEnergyKWh: energyKWh,
      endSocPercent: (energyKWh / capacityKWh) * 100,
    });
  }
  // Unmet demand is not an energy flow. Rejected incoming energy bypasses the
  // reservoir and incurs no modeled conversion loss.
  const balanceResidualKWh =
    initialEnergyKWh +
    totals.availableRegenKWh -
    energyKWh -
    totals.deliveredKWh -
    totals.conversionLossKWh -
    totals.rejectedRegenKWh;
  return {
    ...totals,
    initialEnergyKWh,
    finalEnergyKWh: energyKWh,
    finalSocPercent: (energyKWh / capacityKWh) * 100,
    balanceResidualKWh,
    points,
    cycles,
  };
}
