/**
 * Resolve a driver 3-letter code to a public-rooted headshot path.
 *
 * The Python pipeline does not populate `classification[*].headshotUrl` for
 * every round — when it's null, the website still needs a stable path so the
 * `DriverPortrait` component can attempt the load (and fall back to the
 * team-tinted code-only badge via its own onError handler).
 *
 * The headshot assets ship under `website/public/headshots/<CODE>.webp` and
 * are guaranteed by `scripts/fetch_driver_headshots.py` to exist for every
 * driver on the 2026 grid.
 */
export function driverHeadshotPath(driver: string): string | null {
  if (!driver) return null;
  const code = driver.trim().toUpperCase();
  if (!/^[A-Z]{2,4}$/.test(code)) return null;
  return `/headshots/${code}.webp`;
}

/**
 * Prefer the value the Python pipeline emitted; fall back to the
 * code-derived path when the field is null/undefined.
 */
export function resolveDriverHeadshot(
  driver: string,
  fromData?: string | null,
): string | null {
  if (fromData) return fromData;
  return driverHeadshotPath(driver);
}
