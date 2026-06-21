# Rebrand → RaceIQ: status & remaining manual steps

The product has been rebranded to **RaceIQ** at the presentation layer. This
document records what was changed in-repo and the remaining steps that must be
done **outside the codebase** (GitHub settings, deploy host) to complete a full
identifier rename. Those were intentionally deferred because doing them in a
code change alone would break the live GitHub Pages deploy and the cron
pipeline.

## Done in-repo (safe, presentation-only)

- **Brand assets** — logo at [`website/public/brand/raceiq-logo.png`](../website/public/brand/raceiq-logo.png)
  (+ web-optimized `raceiq-logo.webp`); favicon at [`website/src/app/icon.png`](../website/src/app/icon.png).
- **Navbar / Footer** wordmarks → RaceIQ ([`Navbar.tsx`](../website/src/components/Navbar.tsx),
  [`Footer.tsx`](../website/src/components/Footer.tsx)).
- **Metadata** — `SITE_TITLE`, OpenGraph `siteName`, Twitter card in
  [`layout.tsx`](../website/src/app/layout.tsx); OG image text in
  [`scripts/generate-og.tsx`](../website/scripts/generate-og.tsx) (regenerates on `prebuild`).
- **Docs** — README, ARCHITECTURE, this file, and the rest of `docs/`.

## Deliberately NOT changed (load-bearing — would break the live site)

These embed the literal `f1_predictions` slug and are coupled to the GitHub
repo name and Pages base path. Changing them in code without simultaneously
renaming the GitHub repo + Pages site breaks deploys and inbound links.

| Reference | File | Why deferred |
|---|---|---|
| Canonical site URL fallback | [`layout.tsx`](../website/src/app/layout.tsx) `SITE_URL` | GitHub Pages base path is `…/f1_predictions/` until the repo is renamed. |
| robots / sitemap base URL | [`robots.ts`](../website/src/app/robots.ts), [`sitemap.ts`](../website/src/app/sitemap.ts) | Same base path; SEO links would 404. |
| GitHub repo link | [`Navbar.tsx`](../website/src/components/Navbar.tsx) `GITHUB_URL` | Points at the actual repo. |
| Reusable-workflow ref | [`.github/workflows/update_predictions.yml`](../.github/workflows/update_predictions.yml) | Absolute `owner/repo@main` form; must match the live repo. |
| Conda env name | `f1_predictions` (see [`CLAUDE.md`](../CLAUDE.md)) | Local/CI Python env resolution. |
| On-disk directory | repo root `f1_predictions/` | Import paths, CI checkout, agent configs. |

## To complete the full rename (run by a maintainer with repo admin)

1. **Rename the GitHub repository** `f1_predictions` → `raceiq`
   (GitHub auto-301-redirects the old repo URL, but Pages base path changes).
2. **Update GitHub Pages** — the Pages base path becomes `/raceiq/`; the
   `PAGES_BASE_PATH` env is auto-detected by `actions/configure-pages`, so no
   code change is needed for relative links. Verify after the first deploy.
3. **Set `NEXT_PUBLIC_SITE_URL`** (repo/Actions variable) to
   `https://<owner>.github.io/raceiq` so absolute OG/sitemap URLs are correct,
   *or* update the hardcoded fallbacks in `layout.tsx` / `robots.ts` /
   `sitemap.ts` once the repo is renamed.
4. **Update the workflow ref** in `update_predictions.yml` to
   `<owner>/raceiq/.github/workflows/deploy.yml@main`.
5. **Rename the conda env** and update `CLAUDE.md` + `docs/DEVELOPMENT.md`.
6. **Optionally rename the local working directory** and re-clone.

Until step 1 happens, the in-repo presentation rebrand is complete and the live
site continues to deploy from the existing `f1_predictions` path.
