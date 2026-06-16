// Prefix a public asset path with the deploy basePath.
//
// next/image with `unoptimized` + `output: "export"` does NOT prepend basePath
// to image src, so on a GitHub Pages project site (/motorsportverse) raw
// "/brand/x.png" would 404. Wrap every image src with asset() so it resolves
// both locally (basePath "") and in production.
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

export function asset(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//.test(path)) return path; // external URL — leave as-is
  return `${BASE_PATH}${path.startsWith("/") ? "" : "/"}${path}`;
}
