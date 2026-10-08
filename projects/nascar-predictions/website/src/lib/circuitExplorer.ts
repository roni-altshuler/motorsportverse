/** A reviewed schematic is distinct from the retained telemetry-derived maps. */
export interface ExplorerEvent {
  series: string;
  season: number;
  round: number;
  venueKey: string;
  layoutId: string;
  date: string;
}

export interface ExplorerReview {
  id: string;
  event: ExplorerEvent;
  title: string;
  manifestPath: string;
  checkedAt: string;
  assetSha256: string;
  manifestSha256: string;
}

export interface ExplorerCorner {
  number: number;
  name: string;
  /** Normalized coordinates on the complete, unrotated schematic image. */
  x: number;
  y: number;
  description: string;
}

export interface CircuitSchematic {
  id: string;
  event: ExplorerEvent;
  checkedAt: string;
  totalCorners: number;
  asset: { path: string; width: number; height: number; sha256: string; bytes: number };
  source: {
    creator: string;
    title: string;
    page: string;
    originalUrl: string;
    revision: string;
    sha1: string;
    sha256: string;
    bytes: number;
    width: number;
    height: number;
  };
  license: { id: "CC-BY-SA-4.0"; url: string };
  modifications: string;
  transform: { kind: "resize"; algorithm: "lanczos3"; crop: null; rotationDegrees: 0; colors: "unchanged"; overlay: "three interactive highlights" };
  disclaimer: string;
  references: Array<{ url: string; purpose: string }>;
  corners: ExplorerCorner[];
}

const sameEvent = (a: ExplorerEvent, b: ExplorerEvent) =>
  ["series", "season", "round", "venueKey", "layoutId", "date"].every(
    key => a[key as keyof ExplorerEvent] === b[key as keyof ExplorerEvent],
  );
const text = (value: unknown): value is string => typeof value === "string" && !!value.trim();
const validEvent = (value: ExplorerEvent) =>
  text(value.series) && text(value.venueKey) && text(value.layoutId) &&
  Number.isInteger(value.season) && value.season >= 1950 && Number.isInteger(value.round) && value.round > 0 &&
  typeof value.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value.date);
const sha256 = (value: unknown): value is string =>
  typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
const https = (value: unknown): value is string => {
  if (typeof value !== "string") return false;
  try { return new URL(value).protocol === "https:"; } catch { return false; }
};
const localAsset = (value: unknown): value is string =>
  typeof value === "string" && /^\/circuit-explorer\/[a-z0-9/-]+\.(png|json)$/.test(value)
    && !value.includes("..");

/** Unknown series, seasons and configurations have no explorer launch surface. */
export function findExplorerReview(event: ExplorerEvent, reviews: readonly ExplorerReview[]): ExplorerReview | null {
  if (!validEvent(event)) return null;
  return reviews.find(review => validEvent(review.event) && sameEvent(event, review.event)) ?? null;
}

/** Do not display artwork if identity, attribution or the reviewed asset changed. */
export function validateSchematic(value: unknown, review: ExplorerReview): CircuitSchematic | null {
  if (!value || typeof value !== "object") return null;
  const schematic = value as CircuitSchematic;
  if (
    schematic.id !== review.id || !schematic.event || !validEvent(schematic.event) || !sameEvent(schematic.event, review.event) ||
    schematic.checkedAt !== review.checkedAt || !/^\d{4}-\d{2}-\d{2}$/.test(schematic.checkedAt) ||
    !schematic.asset || !localAsset(schematic.asset.path) || !schematic.asset.path.endsWith(".png") ||
    !sha256(schematic.asset.sha256) || schematic.asset.sha256 !== review.assetSha256 ||
    !Number.isInteger(schematic.asset.width) || schematic.asset.width <= 0 ||
    !Number.isInteger(schematic.asset.height) || schematic.asset.height <= 0 ||
    !Number.isInteger(schematic.asset.bytes) || schematic.asset.bytes <= 0 ||
    !schematic.source || !text(schematic.source.creator) || !text(schematic.source.title) ||
    !https(schematic.source.page) || !https(schematic.source.originalUrl) || !text(schematic.source.revision) ||
    !/^[a-f0-9]{40}$/.test(schematic.source.sha1 ?? "") || !sha256(schematic.source.sha256) ||
    !Number.isInteger(schematic.source.bytes) || schematic.source.bytes <= 0 ||
    !Number.isInteger(schematic.source.width) || schematic.source.width <= 0 ||
    !Number.isInteger(schematic.source.height) || schematic.source.height <= 0 ||
    Math.abs(schematic.asset.width / schematic.source.width - schematic.asset.height / schematic.source.height) >
      Math.max(1 / schematic.source.width, 1 / schematic.source.height) ||
    schematic.license?.id !== "CC-BY-SA-4.0" || schematic.license.url !== "https://creativecommons.org/licenses/by-sa/4.0/" ||
    !text(schematic.modifications) || !text(schematic.disclaimer) ||
    schematic.transform?.kind !== "resize" || schematic.transform.algorithm !== "lanczos3" ||
    schematic.transform.crop !== null || schematic.transform.rotationDegrees !== 0 ||
    schematic.transform.colors !== "unchanged" || schematic.transform.overlay !== "three interactive highlights" ||
    !Array.isArray(schematic.references) || !schematic.references.length ||
    schematic.references.some(reference => !reference || !https(reference.url) || !text(reference.purpose)) ||
    !Number.isInteger(schematic.totalCorners) || schematic.totalCorners < 1 ||
    !Array.isArray(schematic.corners) || schematic.corners.length !== 3
  ) return null;
  let previous = 0;
  for (const corner of schematic.corners) {
    if (!corner || !Number.isInteger(corner.number) || corner.number <= previous ||
      corner.number > schematic.totalCorners || !text(corner.name) || !text(corner.description) ||
      !Number.isFinite(corner.x) || !Number.isFinite(corner.y) ||
      corner.x < 0 || corner.x > 1 || corner.y < 0 || corner.y > 1) return null;
    previous = corner.number;
  }
  return schematic;
}

export interface VerifiedSchematic {
  schematic: CircuitSchematic;
  /** Immutable downloaded bytes, never the mutable server asset path. */
  imageUrl: string;
  release: () => void;
}

async function digest(bytes: BufferSource): Promise<string> {
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, "0")).join("");
}
function checkAbort(signal?: AbortSignal) {
  if (signal?.aborted) throw new DOMException("Schematic loading cancelled", "AbortError");
}

export async function loadSchematic(review: ExplorerReview, basePath = "", signal?: AbortSignal): Promise<VerifiedSchematic> {
  checkAbort(signal);
  if (!localAsset(review.manifestPath) || !review.manifestPath.endsWith(".json"))
    throw new Error("Invalid schematic manifest path");
  const response = await fetch(`${basePath}${review.manifestPath}`, { signal });
  if (!response.ok) throw new Error("Schematic unavailable");
  const body = await response.text();
  const hash = await digest(new TextEncoder().encode(body));
  if (!sha256(review.manifestSha256) || hash !== review.manifestSha256) throw new Error("Schematic manifest changed");
  const schematic = validateSchematic(JSON.parse(body), review);
  if (!schematic) throw new Error("Schematic review does not match");
  checkAbort(signal);
  const imageResponse = await fetch(`${basePath}${schematic.asset.path}`, { signal });
  if (!imageResponse.ok) throw new Error("Schematic image unavailable");
  const bytes = await imageResponse.arrayBuffer();
  if (bytes.byteLength !== schematic.asset.bytes || await digest(bytes) !== review.assetSha256)
    throw new Error("Schematic image bytes changed");
  const signature = [137, 80, 78, 71, 13, 10, 26, 10];
  const header = new Uint8Array(bytes, 0, Math.min(bytes.byteLength, signature.length));
  if (signature.some((value, index) => header[index] !== value)) throw new Error("Schematic image is not PNG");
  checkAbort(signal);
  const imageUrl = URL.createObjectURL(new Blob([bytes], { type: "image/png" }));
  let released = false;
  const release = () => { if (!released) { released = true; URL.revokeObjectURL(imageUrl); } };
  const image = new Image();
  let rejectAbort: ((reason: DOMException) => void) | undefined;
  const cancelled = new Promise<never>((_, reject) => { rejectAbort = reject; });
  const cancel = () => {
    release(); image.src = "";
    rejectAbort?.(new DOMException("Schematic loading cancelled", "AbortError"));
  };
  signal?.addEventListener("abort", cancel, { once: true });
  try {
    image.src = imageUrl;
    await (signal ? Promise.race([image.decode(), cancelled]) : image.decode());
    checkAbort(signal);
    if (image.naturalWidth !== schematic.asset.width || image.naturalHeight !== schematic.asset.height)
      throw new Error("Schematic image dimensions changed");
    return { schematic, imageUrl, release };
  } catch (error) { release(); throw error; }
  finally { signal?.removeEventListener("abort", cancel); }
}
