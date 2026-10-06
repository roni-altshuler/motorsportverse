import { CIRCUIT_GEOMETRY_QUARANTINES } from "./circuitGeometryQuarantines";

/** A stored SVG is a candidate, not evidence that it depicts this event's layout. */
export interface CircuitShape {
  viewBox: string;
  path: string;
  corners: Array<{ number: number; x: number; y: number; name?: string | null }>;
}

export interface CircuitIdentity {
  series: string;
  season: number;
  venueKey: string;
  layoutId?: string | null;
}

export interface CircuitCandidate extends CircuitIdentity {
  geometry?: CircuitShape | null;
}

/** Maintainer-reviewed evidence, kept separately from provider exports. */
export interface CircuitGeometryReview extends CircuitIdentity {
  layoutId: string;
  geometrySignature: string;
  source: {
    kind: "telemetry" | "geographic";
    /** Required for telemetry, not for a geographic layout or licensed diagram. */
    season?: number;
    event?: string;
    session?: string;
    /** A pinned map revision/version is required for geographic sources. */
    revision?: string;
    venueKey: string;
    layoutId: string;
    url: string;
  };
  referenceUrl: string;
  checkedAt: string;
  reuse: { basis: string; evidenceUrl: string; attribution: string };
}

export type CircuitGeometryStatus =
  | "missing"
  | "invalid"
  | "identity-conflict"
  | "unverified"
  | "review-invalid"
  | "identity-mismatch"
  | "geometry-changed"
  | "verified";

/** Coordinate binding, not a cryptographic signature or a rights determination. */
export function circuitGeometrySignature(geometry: CircuitShape): string {
  return JSON.stringify([
    geometry.viewBox.trim().split(/\s+/).map(Number),
    geometry.path.trim().replace(/\s+/g, " "),
    geometry.corners.map(({ number, x, y, name }) => [number, x, y, name ?? null]),
  ]);
}

function validOutline(geometry: CircuitShape): boolean {
  if (
    typeof geometry.path !== "string" ||
    !geometry.path.trim() ||
    typeof geometry.viewBox !== "string"
  )
    return false;
  const box = geometry.viewBox.trim().split(/\s+/).map(Number);
  return box.length === 4 && box.every(Number.isFinite) && box[2] > 0 && box[3] > 0;
}

function unambiguousCorners(geometry: CircuitShape): CircuitShape["corners"] {
  if (!Array.isArray(geometry.corners)) return [];
  const counts = new Map<number, number>();
  for (const corner of geometry.corners) {
    if (corner && Number.isInteger(corner.number))
      counts.set(corner.number, (counts.get(corner.number) ?? 0) + 1);
  }
  return geometry.corners.filter(
    (corner) =>
      corner &&
      Number.isInteger(corner.number) &&
      corner.number > 0 &&
      counts.get(corner.number) === 1 &&
      Number.isFinite(corner.x) &&
      Number.isFinite(corner.y),
  );
}

function validCorners(geometry: CircuitShape): boolean {
  return (
    Array.isArray(geometry.corners) &&
    unambiguousCorners(geometry).length === geometry.corners.length
  );
}

function sameOutline(a: CircuitShape, b: CircuitShape): boolean {
  return (
    a.path.trim().replace(/\s+/g, " ") === b.path.trim().replace(/\s+/g, " ") &&
    a.viewBox.trim().replace(/\s+/g, " ") === b.viewBox.trim().replace(/\s+/g, " ")
  );
}

function httpsUrl(value: string): boolean {
  try {
    return new URL(value).protocol === "https:";
  } catch {
    return false;
  }
}

function validReview(review: CircuitGeometryReview): boolean {
  return Boolean(
    review.layoutId?.trim() &&
    (review.source?.kind === "telemetry"
      ? review.source.event?.trim() &&
        review.source.session?.trim() &&
        Number.isInteger(review.source.season) &&
        (review.source.season ?? 0) >= 1950
      : review.source?.kind === "geographic" && review.source.revision?.trim()) &&
    review.source?.venueKey?.trim() &&
    review.source?.layoutId?.trim() &&
    httpsUrl(review.source.url) &&
    httpsUrl(review.referenceUrl) &&
    /^\d{4}-\d{2}-\d{2}$/.test(review.checkedAt) &&
    review.reuse?.basis?.trim() &&
    review.reuse?.attribution?.trim() &&
    httpsUrl(review.reuse?.evidenceUrl),
  );
}

/** Preserve existing presentation without treating it as reviewed explorer data. */
export function assessCircuitOutline<T extends CircuitShape>(
  identity: Omit<CircuitIdentity, "season"> & { season?: number },
  geometry: T | null | undefined,
  catalog: readonly CircuitCandidate[] = [],
): {
  status: CircuitGeometryStatus | "legacy-unreviewed";
  geometry: T | null;
  cornersSuppressed?: boolean;
} {
  const reject = (status: CircuitGeometryStatus) => ({ status, geometry: null });
  if (!geometry) return reject("missing");
  if (!validOutline(geometry)) return reject("invalid");
  if (
    CIRCUIT_GEOMETRY_QUARANTINES.some(
      (entry) =>
        entry.series === identity.series &&
        (identity.season === undefined || entry.season === identity.season) &&
        sameOutline(geometry, { ...entry, corners: [] }),
    )
  ) {
    return reject("identity-conflict");
  }
  if (
    catalog.some(
      (candidate) =>
        candidate.series === identity.series &&
        candidate.season === identity.season &&
        candidate.geometry &&
        validOutline(candidate.geometry) &&
        sameOutline(geometry, candidate.geometry) &&
        (candidate.venueKey !== identity.venueKey ||
          Boolean(
            candidate.layoutId && identity.layoutId && candidate.layoutId !== identity.layoutId,
          )),
    )
  ) {
    return reject("identity-conflict");
  }
  if (
    !identity.series?.trim() ||
    !identity.venueKey?.trim() ||
    (identity.season !== undefined && !Number.isInteger(identity.season))
  ) {
    return reject("identity-mismatch");
  }
  const corners = unambiguousCorners(geometry);
  const cornersSuppressed = !validCorners(geometry);
  return {
    status: "legacy-unreviewed",
    geometry: cornersSuppressed ? { ...geometry, corners } : geometry,
    cornersSuppressed,
  };
}

/** Strict gate for a NEW explorer; never use missing reviews to remove legacy presentation. */
export function assessCircuitGeometry<T extends CircuitShape>(
  identity: CircuitIdentity,
  geometry: T | null | undefined,
  catalog: readonly CircuitCandidate[] = [],
  reviews: readonly CircuitGeometryReview[] = [],
): { status: CircuitGeometryStatus; geometry: T | null } {
  const reject = (status: CircuitGeometryStatus) => ({ status, geometry: null });
  if (!Number.isInteger(identity.season)) return reject("identity-mismatch");
  const outline = assessCircuitOutline(identity, geometry, catalog);
  if (outline.status !== "legacy-unreviewed") return reject(outline.status);
  if (!geometry || !validCorners(geometry)) return reject("invalid");
  const review = reviews.find(
    (entry) =>
      entry.series === identity.series &&
      entry.season === identity.season &&
      entry.venueKey === identity.venueKey &&
      entry.layoutId === identity.layoutId,
  );
  if (!review) return reject("unverified");
  if (!validReview(review)) return reject("review-invalid");
  if (
    review.source.venueKey !== identity.venueKey ||
    review.source.layoutId !== identity.layoutId
  ) {
    return reject("identity-mismatch");
  }
  if (review.geometrySignature !== circuitGeometrySignature(geometry))
    return reject("geometry-changed");
  return { status: "verified", geometry };
}
