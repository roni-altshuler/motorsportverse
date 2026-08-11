"use client";

import Link from "next/link";
import { useState } from "react";
import { motion } from "framer-motion";

import ClassSelector from "@/components/ClassSelector";
import CountryFlag from "@/components/CountryFlag";
import EntryIdentity from "@/components/EntryIdentity";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Stat } from "@/components/ui/Stat";
import { pct } from "@/lib/format";
import type { CalibrationSummary, ImsaData } from "@/types/imsa";

// Entrance animation runs on MOUNT (not whileInView): every section animates in
// at load, so below-the-fold content is guaranteed visible when scrolled to —
// scroll-reveal must never leave content permanently invisible in a static export.
const reveal = {
  initial: { opacity: 0, y: 16 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] },
};

export default function HomePage({
  data,
  calibration,
}: {
  data: ImsaData;
  calibration: CalibrationSummary | null;
}) {
  const classes = data.classes;
  const [activeClass, setActiveClass] = useState(classes[0]?.key ?? "");

  const totalCars = Object.values(data.standings).reduce((n, rows) => n + rows.length, 0);
  const next = data.nextPrediction;
  const nextClass = next?.classes.find((c) => c.key === activeClass) ?? next?.classes[0];
  const podium = (nextClass?.race ?? []).slice(0, 3);

  const remaining = data.championship[activeClass]?.remainingRounds ?? null;

  return (
    <div className="w-full">
      {/* ── Hero ─────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-b border-[color:var(--hairline)]">
        <div
          aria-hidden
          className="absolute inset-0"
          style={{ background: "var(--gradient-paddock)" }}
        />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-14 sm:pt-24 sm:pb-20">
          <motion.p {...reveal} className="eyebrow mb-4">
            IMSA WeatherTech SportsCar Championship · {data.season}
          </motion.p>
          <motion.h1
            {...reveal}
            transition={{ ...reveal.transition, delay: 0.05 }}
            className="display-xl max-w-4xl"
          >
            Every car, every class — a probability, not a guess.
          </motion.h1>
          <motion.p
            {...reveal}
            transition={{ ...reveal.transition, delay: 0.1 }}
            className="body-md mt-6 max-w-2xl text-[color:var(--body)]"
          >
            Win and podium forecasts for every class — GTP, LMP2, GTD PRO and GTD — from the sprint
            rounds to the Rolex 24 At Daytona — plus each class&rsquo;s title fight, scored honestly
            against real results after every round.
          </motion.p>

          <motion.div
            {...reveal}
            transition={{ ...reveal.transition, delay: 0.15 }}
            className="mt-8 flex flex-wrap gap-3"
          >
            <Link
              href="/predictions"
              className="inline-flex items-center h-11 px-6 rounded-full font-mono uppercase text-[13px] tracking-[0.16em]"
              style={{ background: "var(--accent)", color: "var(--accent-ink)" }}
            >
              Next-Round Forecast →
            </Link>
            <Link href="/standings" className="btn-bugatti">
              Championships
            </Link>
          </motion.div>

          <motion.div
            {...reveal}
            transition={{ ...reveal.transition, delay: 0.2 }}
            className="mt-12 grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-3xl"
          >
            <Stat label="Rounds scored" value={data.completedRounds} hint="completed this season" />
            <Stat label="Classes" value={classes.length} hint={classes.map((c) => c.label).join(" · ")} />
            <Stat label="Cars tracked" value={totalCars} hint="across all classes" />
            <Stat
              label="Podium accuracy"
              value={pct(data.seasonAccuracy?.overall.podiumHitRate)}
              hint="predicted podium hit"
            />
          </motion.div>
        </div>
      </section>

      {/* ── Next-round forecast ──────────────────────────────────── */}
      {next && nextClass && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <motion.div {...reveal} className="flex flex-wrap items-end justify-between gap-4 mb-6">
            <div>
              <p className="eyebrow mb-2">Next round · R{next.round}</p>
              <h2 className="display-md">{next.event === `Round ${next.round}` ? "Next-round forecast" : next.event}</h2>
              <p className="body-sm mt-2 text-[color:var(--muted)]">
                Predicted podium for the selected class. Full grid on the forecast page.
              </p>
            </div>
            <ClassSelector classes={classes} value={activeClass} onChange={setActiveClass} />
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {podium.map((e, i) => (
              <motion.div
                key={e.code}
                {...reveal}
                transition={{ ...reveal.transition, delay: 0.05 * i }}
              >
                <Card teamColor={e.teamColor} className="relative p-5 h-full">
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className="inline-flex items-center justify-center w-8 h-8 rounded-full font-mono text-[13px]"
                      style={{
                        border: `1px solid ${
                          i === 0 ? "var(--accent-podium-1)" : i === 1 ? "var(--accent-podium-2)" : "var(--accent-podium-3)"
                        }`,
                        color:
                          i === 0 ? "var(--accent-podium-1)" : i === 1 ? "var(--accent-podium-2)" : "var(--accent-podium-3)",
                      }}
                    >
                      P{i + 1}
                    </span>
                    <span className="font-tabular text-[13px] text-[color:var(--ink)]">
                      {pct(e.pWin, 1)} <span className="text-[color:var(--muted)]">win</span>
                    </span>
                  </div>
                  <EntryIdentity
                    number={e.number}
                    team={e.team}
                    manufacturer={e.manufacturer}
                    vehicle={e.vehicle}
                    teamColor={e.teamColor}
                    drivers={e.drivers}
                    href={`/entry/${e.code}`}
                  />
                  <div className="mt-4 pt-3 border-t border-[color:var(--hairline)] flex items-center justify-between">
                    <span className="eyebrow">Podium chance</span>
                    <span className="font-tabular text-[13px] text-[color:var(--ink)]">{pct(e.pPodium, 1)}</span>
                  </div>
                </Card>
              </motion.div>
            ))}
          </div>

          <div className="mt-6">
            <Link href="/predictions" className="link-bugatti body-sm">
              Full {nextClass.label} forecast + every class →
            </Link>
          </div>
        </section>
      )}

      {/* ── Championship leaders (per class) ─────────────────────── */}
      <section className="border-t border-[color:var(--hairline)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <motion.div {...reveal} className="mb-6">
            <p className="eyebrow mb-2">Title fights</p>
            <h2 className="display-md">Who&rsquo;s leading each class</h2>
            {remaining != null && (
              <p className="body-sm mt-2 text-[color:var(--muted)]">
                Projected over the rest of the season · {remaining} round{remaining === 1 ? "" : "s"} remaining.
              </p>
            )}
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {classes.map((c, ci) => {
              const champ = data.championship[c.key];
              const leader = champ?.entries?.[0];
              const standingLeader = data.standings[c.key]?.[0];
              if (!leader) return null;
              return (
                <motion.div key={c.key} {...reveal} transition={{ ...reveal.transition, delay: 0.05 * ci }}>
                  <Card teamColor={leader.teamColor} className="p-5 h-full" data-class={c.key}>
                    <div className="flex items-center justify-between mb-4">
                      <span className="class-chip" data-class={c.key} style={{ ["--class-color" as string]: c.color }}>
                        {c.label}
                      </span>
                      <Badge variant="muted">Title favourite</Badge>
                    </div>
                    <EntryIdentity
                      number={leader.number}
                      team={leader.team}
                      manufacturer={leader.manufacturer}
                      vehicle={leader.vehicle}
                      teamColor={leader.teamColor}
                      drivers={leader.drivers}
                      href={`/entry/${leader.code}`}
                    />
                    <div className="mt-5 grid grid-cols-3 gap-3">
                      <div>
                        <p className="eyebrow">Title odds</p>
                        <p className="title-md font-tabular mt-1" style={{ color: c.color }}>
                          {pct(leader.pTitle)}
                        </p>
                      </div>
                      <div>
                        <p className="eyebrow">Points now</p>
                        <p className="title-md font-tabular mt-1 text-[color:var(--ink)]">
                          {standingLeader?.points ?? leader.currentPoints}
                        </p>
                      </div>
                      <div>
                        <p className="eyebrow">Proj. final</p>
                        <p className="title-md font-tabular mt-1 text-[color:var(--ink)]">
                          {Math.round(leader.projMean)}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4">
                      <Link href="/standings" className="link-bugatti body-sm">
                        {c.label} standings →
                      </Link>
                    </div>
                  </Card>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Calendar strip ───────────────────────────────────────── */}
      <section className="border-t border-[color:var(--hairline)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
          <motion.div {...reveal} className="flex items-end justify-between mb-6">
            <div>
              <p className="eyebrow mb-2">Season</p>
              <h2 className="display-md">Calendar</h2>
            </div>
            <Link href="/calendar" className="link-bugatti body-sm">
              Full calendar →
            </Link>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {data.calendar.map((r, i) => (
              <motion.div key={r.round} {...reveal} transition={{ ...reveal.transition, delay: 0.03 * i }}>
                <Link href={`/round/${r.round}`}>
                  <Card interactive className="p-5 h-full">
                    <div className="flex items-center justify-between mb-3">
                      <span className="eyebrow">Round {r.round}</span>
                      {r.isEnduranceCup ? (
                        <Badge variant="live" className="!text-[color:var(--accent-podium-1)] !border-[color:var(--accent-podium-1)]">
                          Endurance
                        </Badge>
                      ) : (
                        <Badge variant="positive">Done</Badge>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <CountryFlag country={r.country} size={28} />
                      <div className="min-w-0">
                        <p className="title-sm truncate">{r.name}</p>
                        <p className="text-[11px] text-[color:var(--muted)] truncate">{r.country}</p>
                      </div>
                    </div>
                  </Card>
                </Link>
              </motion.div>
            ))}
            {next && (
              <motion.div {...reveal} transition={{ ...reveal.transition, delay: 0.03 * data.calendar.length }}>
                <Link href="/predictions">
                  <Card interactive className="p-5 h-full border-dashed">
                    <div className="flex items-center justify-between mb-3">
                      <span className="eyebrow">Round {next.round}</span>
                      <Badge variant="live">Next</Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-2xl" aria-hidden>🏁</span>
                      <div className="min-w-0">
                        <p className="title-sm truncate">{next.place}</p>
                        <p className="text-[11px] text-[color:var(--muted)]">Forecast ready</p>
                      </div>
                    </div>
                  </Card>
                </Link>
              </motion.div>
            )}
          </div>

          {calibration?.applied && (
            <p className="mt-8 text-[11px] text-[color:var(--muted-soft)] max-w-2xl">
              Forecasts are calibrated on {calibration.trainingRounds} real round
              {calibration.trainingRounds === 1 ? "" : "s"} of results, per class. {calibration.dataLimitation}
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
