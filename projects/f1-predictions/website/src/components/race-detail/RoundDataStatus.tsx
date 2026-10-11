/** Missing transport data cannot establish whether a forecast was published or released. */
export default function RoundDataStatus({ status }: { status: "loading" | "unavailable" }) {
  return (
    <section
      aria-label="Forecast data availability"
      className="border border-[var(--hairline)] bg-[var(--surface-soft)] p-5 sm:p-8"
    >
      <p className="eyebrow text-[var(--muted)] mb-4">
        {status === "loading" ? "Checking race data" : "Race data unavailable"}
      </p>
      <h2 className="display-sm mb-4">Forecast status cannot currently be verified</h2>
      <p className="body-md max-w-3xl text-[var(--muted)]">
        {status === "loading"
          ? "This round’s data is still loading. Forecasts and the grid baseline stay hidden until their current inputs can be checked."
          : "This round’s data could not be loaded. Forecasts and the grid baseline stay hidden; this does not establish their publication or review status. Try refreshing the page."}
      </p>
    </section>
  );
}
