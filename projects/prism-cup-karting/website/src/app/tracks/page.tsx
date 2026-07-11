import type { Metadata } from "next";

import { getTracks } from "@/lib/data";
import type { Track } from "@/lib/types";

export const metadata: Metadata = {
  title: "The Tracks — Prism Cup Karting",
  description:
    "Eight original fantasy circuits: hazard ratings, lap counts and boost-pad density. A fan-made simulated league.",
};

function HazardDots({ level }: { level: number }) {
  return (
    <span className="inline-flex items-center gap-1.5" aria-label={`Hazard ${level} of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={`hazard-dot ${i <= level ? "on" : ""}`} />
      ))}
    </span>
  );
}

function TrackCard({ track }: { track: Track }) {
  return (
    <div className="card p-6 flex flex-col">
      <div
        className="h-1.5 -mx-6 -mt-6 mb-5"
        style={{
          background: `linear-gradient(90deg, ${track.color}, transparent 85%)`,
        }}
      />
      <h3 className="title-md mb-2" style={{ color: "var(--ink)" }}>
        {track.name}
      </h3>
      <p className="body-sm mb-6" style={{ color: "var(--body)" }}>
        {track.character}
      </p>
      <div className="mt-auto flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="mono-label">Hazard</span>
          <HazardDots level={track.hazard} />
        </div>
        <div className="flex items-center justify-between">
          <span className="mono-label">Laps</span>
          <span className="font-mono text-[11px] font-tabular" style={{ color: "var(--body-strong)" }}>
            {track.laps}
          </span>
        </div>
        <div className="flex items-center justify-between gap-6">
          <span className="mono-label shrink-0">Boost pads</span>
          <div className="stat-bar max-w-[120px]">
            <div
              className="stat-bar-fill"
              style={{ width: `${track.boostPadDensity * 100}%`, background: track.color }}
            />
          </div>
          <span className="font-mono text-[11px] font-tabular" style={{ color: "var(--body-strong)" }}>
            {Math.round(track.boostPadDensity * 100)}%
          </span>
        </div>
      </div>
    </div>
  );
}

export default function TracksPage() {
  const { tracks } = getTracks();

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
      <p className="eyebrow mb-3" style={{ color: "var(--accent-prism-bright)" }}>
        The calendar · 8 circuits
      </p>
      <h1 className="display-lg mb-4">The Tracks</h1>
      <p className="body-md max-w-2xl mb-14">
        Hazard is the chaos dial: on a five, storms and Seeker Orbs decide as
        much as pace does. Boost-pad density is how much free speed the brave
        can chain together. Each circuit hosts two rounds a season.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {tracks.map((track) => (
          <TrackCard key={track.id} track={track} />
        ))}
      </div>
    </div>
  );
}
