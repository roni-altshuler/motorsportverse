"use client";

import { useId, useState } from "react";
import {
  ENERGY_CYCLE,
  ENERGY_DURATION_SECONDS,
  ENERGY_FIELDS,
  energyDraft,
  parseEnergyDraft,
  simulateEnergy,
  type EnergyField,
  type EnergyRun,
} from "@/lib/energySandbox";

const number = (value: number, decimals = 3) => value.toFixed(decimals);
const action =
  "button-label min-h-11 border border-hairline-strong px-4 py-3 text-ink hover:bg-surface-elevated";
const help: Record<EnergyField, string> = {
  capacityKWh: "The energy reservoir's upper limit.",
  initialSocPercent: "Stored energy as a share of capacity.",
  deploymentKW: "Requested output after conversion losses.",
  regenerationKW: "Fictional incoming power before conversion.",
  efficiencyPercent: "Same fixed efficiency in both directions.",
};

function ChargeTrace({ run, mobile }: { run: EnergyRun; mobile: boolean }) {
  const width = mobile ? 360 : 710;
  const right = width - 24;
  const x = (seconds: number) => 48 + (seconds / ENERGY_DURATION_SECONDS) * (right - 48);
  const y = (soc: number) => 24 + ((100 - soc) / 100) * 180;
  const path = run.points
    .map(
      (point, i) =>
        `${i ? "L" : "M"}${x(point.seconds).toFixed(2)},${y(point.socPercent).toFixed(2)}`,
    )
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${width} 258`}
      aria-hidden="true"
      focusable="false"
      className={mobile ? "block w-full sm:hidden" : "hidden w-full sm:block"}
    >
      {[0, 25, 50, 75, 100].map((soc) => (
        <g key={soc}>
          <line
            x1="48"
            x2={right}
            y1={y(soc)}
            y2={y(soc)}
            stroke="var(--hairline-strong)"
            strokeDasharray={soc === 0 || soc === 100 ? undefined : "3 5"}
          />
          <text
            x="38"
            y={y(soc) + 4}
            textAnchor="end"
            fill="var(--muted)"
            fontSize="12"
            fontFamily="var(--font-mono)"
          >
            {soc}
          </text>
        </g>
      ))}
      {Array.from({ length: ENERGY_CYCLE.repeats }, (_, i) => {
        const start = i * 60;
        return (
          <g key={i}>
            <rect x={x(start)} y="212" width={x(30) - x(0)} height="4" fill="var(--ink)" />
            <rect x={x(start + 30)} y="212" width={x(10) - x(0)} height="4" fill="var(--muted)" />
            <rect x={x(start + 40)} y="212" width={x(20) - x(0)} height="4" fill="var(--success)" />
          </g>
        );
      })}
      <path
        d={path}
        fill="none"
        stroke="var(--ink)"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={x(ENERGY_DURATION_SECONDS)} cy={y(run.finalSocPercent)} r="4" fill="var(--ink)" />
      {(mobile ? [0, 120, 240, 360] : [0, 60, 120, 180, 240, 300, 360]).map((seconds) => (
        <text
          key={seconds}
          x={x(seconds)}
          y="236"
          textAnchor="middle"
          fill="var(--muted)"
          fontSize="12"
          fontFamily="var(--font-mono)"
        >
          {seconds}
        </text>
      ))}
      <text
        x={right}
        y="255"
        textAnchor="end"
        fill="var(--muted)"
        fontSize="12"
        fontFamily="var(--font-mono)"
      >
        Time · s
      </text>
    </svg>
  );
}

function ChargeChart({ run, id }: { run: EnergyRun; id: string }) {
  return (
    <figure aria-labelledby={`${id}-chart-caption`}>
      <figcaption
        id={`${id}-chart-caption`}
        className="mb-4 flex flex-wrap items-center justify-between gap-2"
      >
        <span className="title-sm">Charge through the cycle</span>
        <span className="font-mono text-xs text-muted">Energy-based SoC · %</span>
      </figcaption>
      <div
        role="img"
        aria-label={`Synthetic charge over ${ENERGY_DURATION_SECONDS} seconds`}
        aria-describedby={`${id}-chart-desc`}
      >
        <p id={`${id}-chart-desc`} className="sr-only">
          Charge starts at {number(run.points[0].socPercent, 1)} percent and ends at{" "}
          {number(run.finalSocPercent, 1)} percent. Six identical deploy, coast and regenerate
          cycles. Exact cycle values are in the table below.
        </p>
        <ChargeTrace run={run} mobile={false} />
        <ChargeTrace run={run} mobile />
      </div>
      <ul
        className="mt-3 flex flex-wrap gap-x-5 gap-y-2 font-mono text-xs text-muted"
        aria-label="Cycle phases"
      >
        {[
          ["Deploy", "30 s", "var(--ink)"],
          ["Coast", "10 s", "var(--muted)"],
          ["Regenerate", "20 s", "var(--success)"],
        ].map(([label, duration, color]) => (
          <li key={label} className="flex items-center gap-2">
            <span
              className="inline-block h-1 w-4"
              style={{ backgroundColor: color }}
              aria-hidden="true"
            />
            {label} · {duration}
          </li>
        ))}
      </ul>
    </figure>
  );
}

function EnergyResults({ run, id }: { run: EnergyRun; id: string }) {
  const limited = run.deploymentLimitedSeconds > 0 || run.regenerationLimitedSeconds > 0;
  const ledger = [
    ["Starting stored energy", run.initialEnergyKWh],
    ["Available regeneration input", run.availableRegenKWh],
    ["Final stored energy", run.finalEnergyKWh],
    ["Delivered deployment", run.deliveredKWh],
    ["Conversion losses", run.conversionLossKWh],
    ["Rejected regeneration input", run.rejectedRegenKWh],
  ] as const;
  return (
    <div className="min-w-0" data-testid="energy-results">
      <div
        className="mb-6 border-l-2 pl-4"
        style={{ borderColor: limited ? "var(--warning)" : "var(--success)" }}
      >
        <p className="title-sm" style={{ color: limited ? "var(--warning)" : "var(--success)" }}>
          {limited ? "Power curtailed at a limit" : "Requested power supplied"}
        </p>
        <p className="body-sm mt-2">
          {limited
            ? "Capacity limits reduce energy transfer. The trace stays between empty and full."
            : "These assumptions keep charge within capacity without curtailing energy transfer."}
        </p>
        {run.deploymentLimitedSeconds > 0 && (
          <p className="body-sm mt-2">
            Empty reservoir: {number(run.unmetDeploymentKWh)} kWh of requested deployment could not
            be supplied.
          </p>
        )}
        {run.regenerationLimitedSeconds > 0 && (
          <p className="body-sm mt-2">
            Full reservoir: {number(run.rejectedRegenKWh)} kWh of incoming regeneration was
            rejected.
          </p>
        )}
      </div>
      <dl className="mb-8 grid grid-cols-1 divide-y divide-hairline border-y border-hairline sm:grid-cols-3 sm:divide-x sm:divide-y-0">
        {[
          [
            "Final charge",
            `${number(run.finalSocPercent, 1)} %`,
            `${number(run.finalEnergyKWh)} kWh stored`,
          ],
          ["Deployment delivered", `${number(run.deliveredKWh)} kWh`, "Output after conversion"],
          ["Energy recovered", `${number(run.recoveredKWh)} kWh`, "Added to the reservoir"],
        ].map(([label, value, detail]) => (
          <div key={label} className="py-5 sm:px-4 sm:first:pl-0 sm:last:pr-0">
            <dt className="eyebrow">{label}</dt>
            <dd className="mt-2 font-mono text-2xl text-ink" data-metric={label}>
              {value}
            </dd>
            <dd className="body-sm mt-1 text-muted">{detail}</dd>
          </div>
        ))}
      </dl>
      <ChargeChart run={run} id={id} />
      <details className="mt-7 border-y border-hairline py-4">
        <summary className="button-label min-h-11 cursor-pointer py-3 text-ink">
          Energy ledger & cycle values
        </summary>
        <p className="body-sm mt-4">
          Starting energy + available regeneration = final energy + delivered deployment +
          conversion losses + rejected regeneration. Unmet demand is a shortfall, not an energy
          flow.
        </p>
        <dl className="mt-4 grid grid-cols-1 gap-x-8 sm:grid-cols-2">
          {ledger.map(([label, value]) => (
            <div
              className="flex flex-wrap justify-between gap-2 border-b border-hairline py-3"
              key={label}
            >
              <dt className="body-sm">{label}</dt>
              <dd className="font-mono text-sm text-ink">{number(value)} kWh</dd>
            </div>
          ))}
        </dl>
        <p className="body-sm mt-4">
          Balance residual:{" "}
          <span className="font-mono text-ink">
            {Math.abs(run.balanceResidualKWh).toExponential(1)} kWh
          </span>
          . Calculated before rounding the displayed values.
        </p>
        <div
          className="mt-6 overflow-x-auto"
          tabIndex={0}
          role="region"
          aria-label="Cycle values, horizontally scrollable"
        >
          <table className="w-full min-w-[520px] text-left text-sm">
            <caption className="mb-3 text-left text-muted">
              Each 60-second cycle · all energy values in kWh
            </caption>
            <thead className="font-mono text-xs text-muted">
              <tr>
                {["Cycle / time", "Charge", "Delivered", "Recovered", "Unmet", "Rejected"].map(
                  (label) => (
                    <th
                      key={label}
                      scope="col"
                      className="border-b border-hairline px-2 py-3 font-normal"
                    >
                      {label}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody className="font-mono text-xs text-ink">
              {run.cycles.map((cycle) => (
                <tr key={cycle.cycle}>
                  <th scope="row" className="border-b border-hairline px-2 py-3 font-normal">
                    {cycle.cycle} / {cycle.cycle * 60} s
                  </th>
                  <td className="border-b border-hairline px-2 py-3">
                    {number(cycle.endSocPercent, 1)} %
                  </td>
                  {[
                    cycle.deliveredKWh,
                    cycle.recoveredKWh,
                    cycle.unmetDeploymentKWh,
                    cycle.rejectedRegenKWh,
                  ].map((value, i) => (
                    <td key={i} className="border-b border-hairline px-2 py-3">
                      {number(value)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

export default function EnergySandbox() {
  const id = useId();
  const [draft, setDraft] = useState(energyDraft);
  const parsed = parseEnergyDraft(draft);
  const run = parsed.valid ? simulateEnergy(parsed.assumptions) : null;
  return (
    <section
      id="energy-sandbox"
      aria-labelledby={`${id}-heading`}
      className="mx-auto max-w-7xl scroll-mt-28 px-4 pb-20 sm:px-8"
    >
      <header className="border-t border-hairline pb-9 pt-12">
        <p className="eyebrow mb-3">Energy lab · Synthetic / Educational</p>
        <h2 id={`${id}-heading`} className="display-lg">
          Energy management sandbox.
        </h2>
        <p className="body-lg mt-5 max-w-3xl">
          Spend energy, recover some, and see what remains. Adjust five assumptions through a
          fictional six-minute cycle; results recalculate locally.
        </p>
        <p className="body-sm mt-4 max-w-3xl text-muted">
          Charge (SoC) here means stored energy ÷ usable capacity. This energy proxy is educational:
          it uses no measured telemetry and does not predict a race or represent an
          engineering-grade F1 battery.
        </p>
      </header>
      <div className="grid items-start gap-10 lg:grid-cols-[minmax(250px,320px)_minmax(0,1fr)] lg:gap-12">
        <form
          onSubmit={(event) => event.preventDefault()}
          className="border border-hairline bg-surface-soft p-5 sm:p-6"
          aria-labelledby={`${id}-assumptions`}
          noValidate
        >
          <div className="mb-6 flex items-center justify-between gap-3">
            <h3 id={`${id}-assumptions`} className="title-md">
              Your assumptions
            </h3>
            <button type="button" className={action} onClick={() => setDraft(energyDraft())}>
              Reset
            </button>
          </div>
          <div className="space-y-5">
            {(Object.keys(ENERGY_FIELDS) as EnergyField[]).map((key) => {
              const field = ENERGY_FIELDS[key];
              const error = parsed.errors[key];
              return (
                <div key={key}>
                  <label htmlFor={`${id}-${key}`} className="mb-2 block font-mono text-xs text-ink">
                    {field.label} <span className="text-muted">({field.unit})</span>
                  </label>
                  <input
                    id={`${id}-${key}`}
                    type="number"
                    inputMode="decimal"
                    min={field.min}
                    max={field.max}
                    step="any"
                    value={draft[key]}
                    onChange={(event) =>
                      setDraft((current) => ({ ...current, [key]: event.target.value }))
                    }
                    aria-invalid={!!error}
                    aria-describedby={`${id}-${key}-help${error ? ` ${id}-${key}-error` : ""}`}
                    className="min-h-11 w-full border border-hairline-strong bg-canvas px-3 py-2 font-mono text-lg text-ink aria-invalid:border-[color:var(--warning)]"
                  />
                  <p id={`${id}-${key}-help`} className="body-sm mt-2 text-muted">
                    {help[key]} Range: {field.min}–{field.max} {field.unit}.
                  </p>
                  {error && (
                    <p
                      id={`${id}-${key}-error`}
                      className="body-sm mt-2 text-[color:var(--warning)]"
                    >
                      {error}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
          <p className="body-sm mt-6 border-t border-hairline pt-4 text-muted">
            30 s deploy → 10 s coast → 20 s regenerate. Repeat six times. No energy is used during
            coasting.
          </p>
        </form>
        <div className="min-w-0">
          <p
            role="status"
            aria-live="polite"
            aria-atomic="true"
            className="body-sm mb-5 text-muted"
          >
            {run
              ? `Synthetic results updated. Final charge ${number(run.finalSocPercent, 1)} percent.`
              : "Results paused. Correct the highlighted assumptions to recalculate; previous results are hidden."}
          </p>
          {run ? (
            <EnergyResults run={run} id={id} />
          ) : (
            <div className="border border-hairline p-8">
              <h3 className="title-md">Check your assumptions</h3>
              <p className="body-md mt-3">
                Each value needs a finite number within its stated range. Reset returns to the
                starting example.
              </p>
            </div>
          )}
        </div>
      </div>
      <div className="mt-12 grid gap-8 border-t border-hairline pt-8 lg:grid-cols-[minmax(250px,320px)_minmax(0,1fr)] lg:gap-12">
        <div>
          <h3 className="title-md">Model boundaries</h3>
          <p className="body-sm mt-4 text-muted">
            Fixed capacity and conversion efficiency. Empty storage curtails deployment; full
            storage rejects regeneration. Conversion losses are accounted for as energy only.
          </p>
          <p className="body-sm mt-3 text-muted">
            No voltage, current, temperature, cooling, degradation, speed, circuit or regulatory
            model. The input ranges are sandbox limits, not vehicle specifications.
          </p>
        </div>
        <div>
          <h3 className="title-md">Keep learning</h3>
          <p className="body-sm mt-3 text-muted">
            Official MathWorks browser courses. Onramps are free and require a MathWorks account;
            these links open the provider, with no course content embedded here.
          </p>
          <ul className="mt-5 grid gap-3 sm:grid-cols-3">
            {[
              [
                "MATLAB Onramp",
                "Approx. 2 h",
                "https://matlabacademy.mathworks.com/details/matlab-onramp/gettingstarted",
              ],
              [
                "Simulink Onramp",
                "Approx. 2 h",
                "https://matlabacademy.mathworks.com/details/simulink-onramp/simulink",
              ],
              [
                "Simscape Battery Onramp",
                "Approx. 1 h",
                "https://matlabacademy.mathworks.com/details/simscape-battery-onramp/orsb",
              ],
            ].map(([label, duration, href]) => (
              <li key={href}>
                <a
                  href={href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex h-full min-h-24 flex-col justify-between gap-3 border border-hairline p-4 text-ink hover:border-hairline-strong"
                >
                  <span className="font-mono text-sm">
                    {label}{" "}
                    <svg
                      className="inline-block text-muted"
                      width="12"
                      height="12"
                      viewBox="0 0 12 12"
                      fill="none"
                      stroke="currentColor"
                      aria-hidden="true"
                      focusable="false"
                    >
                      <path d="M2 10 10 2M3 2h7v7" />
                    </svg>
                    <span className="sr-only"> (opens in a new tab)</span>
                  </span>
                  <span className="font-mono text-xs text-muted">{duration}</span>
                </a>
              </li>
            ))}
          </ul>
          <p className="body-sm mt-4 text-muted">
            For Simscape Battery Onramp, start with Simulink and{" "}
            <a
              className="text-link underline underline-offset-4"
              href="https://matlabacademy.mathworks.com/details/simscape-onramp/simscape"
              target="_blank"
              rel="noopener noreferrer"
            >
              Simscape Onramp<span className="sr-only"> (opens in a new tab)</span>
            </a>
            . Durations are approximate.
          </p>
        </div>
      </div>
    </section>
  );
}
