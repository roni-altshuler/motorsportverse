import type { Metadata } from "next";

import TraitBar from "@/components/TraitBar";
import { getRoster } from "@/lib/data";

export const metadata: Metadata = {
  title: "The Garage — Chrome Valley Racing League",
  description:
    "The full roster of the Chrome Valley Racing League — twelve original, simulated racers with trait bars and short bios.",
};

export default function GaragePage() {
  const roster = getRoster();

  return (
    <section className="section-valley">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <p className="eyebrow eyebrow-accent mb-4">The Garage</p>
        <h1 className="display-lg max-w-3xl">
          Twelve racers, four traits, no shortage of opinions
        </h1>
        <p className="body-md mt-5 max-w-2xl">
          Every racer in the valley runs on the same four gauges: grit for when the track fights
          back, showboat for when the crowd is watching (which is always), consistency for the
          laps nobody claps for, and heart for the ones everybody remembers. The simulator reads
          these numbers. So should you, before you bet a slice of pie on Sunday&apos;s race.
        </p>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {roster.characters.map((c) => (
            <article
              key={c.slug}
              className="card racer-stripe flex flex-col p-6"
              style={{ "--racer-color": c.color } as React.CSSProperties}
            >
              <div className="flex items-baseline justify-between">
                <p className="mono-label">#{c.number}</p>
                <p className="mono-label">{c.hometown}</p>
              </div>
              <h2 className="title-md mt-2">{c.name}</h2>
              <p className="eyebrow eyebrow-accent mt-1">{c.role}</p>
              <p className="body-sm mt-1 text-[color:var(--muted)]">{c.car}</p>
              <p className="body-md mt-4 flex-1">{c.bio}</p>
              <div className="mt-6 flex flex-col gap-3">
                <TraitBar label="Grit" value={c.traits.grit} color={c.color} />
                <TraitBar label="Showboat" value={c.traits.showboat} color={c.color} />
                <TraitBar label="Consistency" value={c.traits.consistency} color={c.color} />
                <TraitBar label="Heart" value={c.traits.heart} color={c.color} />
              </div>
              <div className="hairline-divider-top mt-5 flex items-baseline justify-between pt-4">
                <span className="mono-label">Base pace</span>
                <span className="font-tabular text-[color:var(--ink)]">{c.basePace}</span>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
