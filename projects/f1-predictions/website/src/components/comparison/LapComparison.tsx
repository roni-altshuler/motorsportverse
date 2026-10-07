"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeftRight, ArrowUpRight, RefreshCw } from "lucide-react";
import DriverPortrait from "@/components/standings/DriverPortrait";
import { HUDPanel } from "@/components/ui/HUDPanel";
import { formatLapTime } from "@/lib/data";
import {
  COMPARISON_SOURCE_HASH,
  fetchSessionComparison,
  formatTimingDelta,
  timingDelta,
} from "@/lib/sessionComparison";
import type { SessionComparisonData, SessionComparisonDriver } from "@/types";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: SessionComparisonData };

const control =
  "border border-[color:var(--hairline-strong)] bg-[color:var(--canvas)] text-[color:var(--ink)] focus-visible:outline-2! focus-visible:outline-offset-4! focus-visible:outline-[color:var(--ink)]!";

function DriverChoice({
  lane,
  driver,
  drivers,
  onChange,
}: {
  lane: "A" | "B";
  driver: SessionComparisonDriver;
  drivers: SessionComparisonDriver[];
  onChange: (code: string) => void;
}) {
  return (
    <div className="min-w-0 space-y-5">
      <label htmlFor={`driver-${lane}`} className="eyebrow block text-[color:var(--muted)]">
        Driver {lane}
      </label>
      <select
        id={`driver-${lane}`}
        value={driver.code}
        onChange={(event) => onChange(event.target.value)}
        className={`${control} w-full min-h-12 px-3 text-sm font-medium`}
      >
        {drivers.map((entry) => (
          <option key={entry.code} value={entry.code}>
            {entry.fullName}
          </option>
        ))}
      </select>
      <div className="flex items-center gap-4">
        <DriverPortrait
          key={driver.code}
          driver={driver.code}
          driverFullName={driver.fullName}
          team=""
          headshotUrl={driver.portraitPath}
          fallbackOnly={!driver.portraitPath}
          size={52}
        />
        <div className="min-w-0">
          <p className="font-mono text-2xl sm:text-3xl tracking-tight tabular-nums">
            {formatLapTime(driver.lapMs / 1000)}
          </p>
          <p className="text-xs text-[color:var(--muted)] mt-1">Fastest complete stored lap</p>
        </div>
      </div>
      <p className="text-xs text-[color:var(--muted)]">
        {driver.completeRows} complete of {driver.storedRows} stored timing rows
      </p>
    </div>
  );
}

function TimingPair({ data }: { data: SessionComparisonData }) {
  const initialA = data.drivers.find((d) => d.code === "NOR")?.code ?? data.drivers[0].code;
  const initialB =
    data.drivers.find((d) => d.code === "RUS" && d.code !== initialA)?.code ??
    data.drivers.find((d) => d.code !== initialA)!.code;
  const [aCode, setA] = useState(initialA);
  const [bCode, setB] = useState(initialB);
  const a = data.drivers.find((d) => d.code === aCode)!;
  const b = data.drivers.find((d) => d.code === bCode)!;
  const lapDelta = timingDelta(a.lapMs, b.lapMs);
  const quicker = lapDelta > 0 ? a : b;
  const sectorDeltas = a.sectorMs.map((ms, i) => timingDelta(ms, b.sectorMs[i]));
  const maxDelta = Math.max(1, ...sectorDeltas.map(Math.abs));

  function chooseA(code: string) {
    if (code === bCode) setB(aCode);
    setA(code);
  }
  function chooseB(code: string) {
    if (code === aCode) setA(bCode);
    setB(code);
  }

  return (
    <>
      <HUDPanel title="Choose your drivers" kicker="The timing duel" bodyClassName="p-5 sm:p-8">
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-6 sm:gap-8 items-center">
          <DriverChoice lane="A" driver={a} drivers={data.drivers} onChange={chooseA} />
          <button
            type="button"
            aria-label="Swap drivers"
            onClick={() => {
              setA(bCode);
              setB(aCode);
            }}
            className={`${control} justify-self-center w-12 h-12 flex items-center justify-center hover:bg-[color:var(--surface-elevated)]`}
          >
            <ArrowLeftRight size={18} aria-hidden="true" />
          </button>
          <DriverChoice lane="B" driver={b} drivers={data.drivers} onChange={chooseB} />
        </div>
      </HUDPanel>

      <section className="mt-10" aria-labelledby="sector-heading">
        <div className="flex flex-wrap justify-between gap-3 items-end mb-6">
          <div>
            <p className="eyebrow text-[color:var(--muted)] mb-2">
              Three splits. One stored lap each.
            </p>
            <h2 id="sector-heading" className="title-md">
              Where the time differs
            </h2>
          </div>
          <p className="text-xs text-[color:var(--muted)]">Delta = B − A · seconds</p>
        </div>
        <div className="grid grid-cols-3 gap-3 sm:gap-8 text-xs text-[color:var(--muted)] pb-3 px-4 sm:px-6">
          <span>A · {a.fullName}</span>
          <span className="text-center">Sector / delta</span>
          <span className="text-right">B · {b.fullName}</span>
        </div>
        <div className="border-y border-[color:var(--hairline-strong)]">
          {sectorDeltas.map((delta, i) => (
            <div
              key={i}
              className="grid grid-cols-3 gap-3 sm:gap-8 items-center p-4 sm:p-6 border-b last:border-b-0 border-[color:var(--hairline)]"
            >
              <p className="font-mono text-lg sm:text-2xl tabular-nums">
                {(a.sectorMs[i] / 1000).toFixed(3)}
                <span className="text-xs text-[color:var(--muted)] ml-1">s</span>
              </p>
              <div className="text-center">
                <p className="eyebrow text-[color:var(--muted)] mb-2">Sector {i + 1}</p>
                <p className="font-mono text-base sm:text-lg tabular-nums">
                  {formatTimingDelta(delta)}
                </p>
                <div aria-hidden="true" className="relative h-1 my-3 bg-[color:var(--hairline)]">
                  <span
                    className="absolute top-0 h-1 bg-[color:var(--ink)]"
                    style={{
                      left: delta >= 0 ? `${50 - (Math.abs(delta) / maxDelta) * 50}%` : "50%",
                      width: `${(Math.abs(delta) / maxDelta) * 50}%`,
                    }}
                  />
                  <span className="absolute left-1/2 -top-1 w-px h-3 bg-[color:var(--muted)]" />
                </div>
                <p className="text-[10px] sm:text-xs text-[color:var(--muted)]">
                  {delta === 0 ? "Equal timing" : `${delta > 0 ? "A" : "B"} quicker`}
                </p>
              </div>
              <p className="font-mono text-lg sm:text-2xl tabular-nums text-right">
                {(b.sectorMs[i] / 1000).toFixed(3)}
                <span className="text-xs text-[color:var(--muted)] ml-1">s</span>
              </p>
            </div>
          ))}
        </div>
        <div
          className="flex flex-wrap justify-between gap-4 py-6 border-b border-[color:var(--hairline)]"
          aria-live="polite"
          aria-atomic="true"
        >
          <p className="text-sm">
            {lapDelta === 0 ? (
              "These stored lap times are equal."
            ) : (
              <>
                <strong>{quicker.fullName}</strong> has the quicker stored lap.
              </>
            )}
          </p>
          <p
            className="font-mono text-xl tabular-nums"
            aria-label={`Lap delta ${formatTimingDelta(lapDelta)}`}
          >
            {formatTimingDelta(lapDelta)}
          </p>
        </div>
      </section>
    </>
  );
}

export default function LapComparison() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    fetchSessionComparison(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setState({ status: "ready", data });
      })
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: "error" });
      });
    return () => controller.abort();
  }, [attempt]);

  return (
    <div className="max-w-6xl mx-auto px-5 sm:px-8 pt-32 sm:pt-40 pb-20">
      <div className="flex flex-wrap justify-between gap-3 border-b border-[color:var(--hairline)] pb-5 mb-8">
        <p className="eyebrow text-[color:var(--muted)]">RaceIQ / Lap comparison</p>
        <span className="eyebrow border border-[color:var(--hairline-strong)] px-3 py-1">
          2025 archive
        </span>
      </div>
      <header className="mb-10 sm:mb-14 max-w-3xl">
        <p className="eyebrow text-[color:var(--accent-f1-red-bright)] mb-4">
          Monaco · Race · 25 May 2025
        </p>
        <h1 className="font-display text-4xl sm:text-6xl tracking-tight leading-none mb-6">
          Every split tells
          <br className="hidden sm:block" /> a different story.
        </h1>
        <p className="text-base sm:text-lg text-[color:var(--body)] leading-relaxed max-w-2xl">
          Compare two drivers’ fastest complete stored laps from the 2025 Monaco race. All three
          sectors stay together, exactly as recorded in each lap.
        </p>
      </header>

      {state.status === "loading" && (
        <HUDPanel title="Opening the archive">
          <p role="status" className="text-sm text-[color:var(--muted)]">
            Loading the 2025 Monaco timing snapshot…
          </p>
        </HUDPanel>
      )}
      {state.status === "error" && (
        <HUDPanel title="Timings unavailable">
          <p role="alert" className="text-sm text-[color:var(--body)] mb-5">
            We couldn’t load and verify this archive. Try again to compare drivers.
          </p>
          <button
            type="button"
            className={`${control} inline-flex items-center gap-2 px-4 min-h-12 text-sm`}
            onClick={() => {
              setState({ status: "loading" });
              setAttempt((n) => n + 1);
            }}
          >
            <RefreshCw size={16} aria-hidden="true" /> Try again
          </button>
        </HUDPanel>
      )}
      {state.status === "ready" &&
        (state.data.drivers.length < 2 ? (
          <HUDPanel title="No comparison available">
            <p role="status" className="text-sm text-[color:var(--body)]">
              This archive has fewer than two drivers with complete, consistent lap timings.
            </p>
          </HUDPanel>
        ) : (
          <TimingPair data={state.data} />
        ))}

      <aside
        className="mt-10 sm:mt-14 grid sm:grid-cols-[1fr_2fr] gap-5 sm:gap-12 border-t border-[color:var(--hairline)] pt-6"
        aria-labelledby="archive-note"
      >
        <h2 id="archive-note" className="eyebrow">
          Read the comparison
        </h2>
        <div className="text-sm text-[color:var(--muted)] leading-relaxed space-y-4">
          <p>
            Each driver’s sectors come from their own fastest complete stored lap. They can come
            from different parts of the race, under different conditions. This is a timing
            comparison, not a controlled pace test.
          </p>
          <p>
            The archived snapshot has no lap numbers, tyre information, pit or track-status flags,
            or accuracy flags. These are stored timing records, not a verified clean-lap or official
            fastest-lap ranking. Portraits identify drivers and may be from a later season.
          </p>
          <p>
            Only this archived session is available here. Current-season forecasts and Race Theatre
            have separate data.
          </p>
          <div className="flex flex-wrap gap-6 pt-2">
            <Link
              href="/calendar"
              className="inline-flex items-center gap-2 text-[color:var(--ink)] underline underline-offset-4"
            >
              Season calendar <ArrowUpRight size={14} aria-hidden="true" />
            </Link>
            <details className="min-w-0">
              <summary className="cursor-pointer text-[color:var(--ink)] underline underline-offset-4">
                Archive source
              </summary>
              <p className="mt-3 max-w-lg text-xs break-words">
                FastF1-derived committed lap snapshot · 2025_Monaco_R · offline export. Source
                SHA-256: <span className="font-mono break-all">{COMPARISON_SOURCE_HASH}</span>
              </p>
            </details>
          </div>
        </div>
      </aside>
    </div>
  );
}
