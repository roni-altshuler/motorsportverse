/** A map absence is information; never substitute a generic circuit outline. */
export default function CircuitMapUnavailable({ venue }: { venue?: string | null }) {
  return (
    <div role="status" aria-label="Circuit map availability" className="px-6 text-center">
      <p className="eyebrow text-[color:var(--ink)]">Circuit map unavailable</p>
      <p className="mt-3 text-sm text-[color:var(--muted)]">
        {venue
          ? `A verified layout is not published for ${venue}.`
          : "A verified layout is not published for this event."}
      </p>
    </div>
  );
}
