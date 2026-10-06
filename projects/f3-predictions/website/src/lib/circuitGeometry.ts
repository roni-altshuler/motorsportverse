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
    season: number;
    event: string;
    session: string;
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

function validShape(geometry: CircuitShape): boolean {
  if (
    typeof geometry.path !== "string" ||
    !geometry.path.trim() ||
    typeof geometry.viewBox !== "string" ||
    !Array.isArray(geometry.corners)
  )
    return false;
  const box = geometry.viewBox.trim().split(/\s+/).map(Number);
  if (box.length !== 4 || !box.every(Number.isFinite) || box[2] <= 0 || box[3] <= 0) return false;
  const numbers = new Set<number>();
  return geometry.corners.every((corner) => {
    if (
      !corner ||
      !Number.isInteger(corner.number) ||
      corner.number < 1 ||
      !Number.isFinite(corner.x) ||
      !Number.isFinite(corner.y) ||
      numbers.has(corner.number)
    )
      return false;
    numbers.add(corner.number);
    return true;
  });
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
    review.source?.event?.trim() &&
    review.source?.session?.trim() &&
    review.source?.venueKey?.trim() &&
    review.source?.layoutId?.trim() &&
    Number.isInteger(review.source?.season) &&
    review.source.season >= 1950 &&
    httpsUrl(review.source.url) &&
    httpsUrl(review.referenceUrl) &&
    /^\d{4}-\d{2}-\d{2}$/.test(review.checkedAt) &&
    review.reuse?.basis?.trim() &&
    review.reuse?.attribution?.trim() &&
    httpsUrl(review.reuse?.evidenceUrl),
  );
}

/** Reject conflicts before considering reviews. Repeated rounds at one layout are valid. */
export function assessCircuitGeometry<T extends CircuitShape>(
  identity: CircuitIdentity,
  geometry: T | null | undefined,
  catalog: readonly CircuitCandidate[] = [],
  reviews: readonly CircuitGeometryReview[] = [],
): { status: CircuitGeometryStatus; geometry: T | null } {
  const reject = (status: CircuitGeometryStatus) => ({ status, geometry: null });
  if (!geometry) return reject("missing");
  if (!validShape(geometry)) return reject("invalid");
  if (
    CIRCUIT_GEOMETRY_QUARANTINES.some(
      (entry) =>
        entry.series === identity.series &&
        entry.season === identity.season &&
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
        validShape(candidate.geometry) &&
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
    !Number.isInteger(identity.season)
  ) {
    return reject("identity-mismatch");
  }
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
