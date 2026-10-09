# Next.js frontend maintenance — 2026-10-09

The hub and ten series sites pin Next.js and eslint-config-next to **16.3.8**
(previously 16.1.6). Required resolutions include Sharp **0.35.5**, PostCSS
**8.5.23**, and baseline-browser-mapping **2.11.28** within Next's declared range.
React/react-dom remain **19.2.3**, source-map-js **1.2.2**, and the existing
`legacy-peer-deps=true` policies are unchanged. Node **20.20.2** / npm **10.9.9**
were used for local validation; Next requires Node >=20.9.0.

The [official Next advisory](https://github.com/advisories/GHSA-cjq9-62q9-8jv4)
and [16.3.8 release](https://github.com/vercel/next.js/releases/tag/v16.3.8)
identify the patched release. All eleven sites remain static exports with
unoptimized images. An exposed deployed image optimizer or incident has not
been established. No application UI, branding, data, model, installation policy,
workflow or deployment behavior changes in this evidence-compaction follow-up.

## Scope and evidence compaction

The independently reviewed implementation head is
`e01f36efabc1f5d443963acf1183fcd4f1559392`; the base is
`5ec3ee2c303e6b8e1b169c4662f0b416733a0ae6`. Its PR diff had **199 files,
285,277 added / 2,795 removed lines**. The bulk was repeated machine output:

| Original diff category | Files | Added lines | Final-file bytes |
| --- | ---: | ---: | ---: |
| Dependency locks | 11 | 3,225 | 4,733,698 |
| Dependency manifests and diagnostic test | 12 | 35 | 20,577 |
| Root documentation | 2 | 20 | 40,235 |
| QA/audit/log evidence excluding screenshots | 166 | 282,017 | 10,074,565 |
| Original screenshots | 8 | binary | 966,697 |

Bytes here are the contents of changed paths at the reviewed head, not a wire
transfer or textual-patch size. Two all-site browser JSON files alone contributed
**182,722 added lines / 6,488,949 bytes**.

The new representation preserves all **174 original evidence files** (11,041,262
bytes). Twelve concise records/screenshots stay in place; 162 files move,
byte-for-byte, into three deterministic archives totaling **601,127 bytes**.
The original README is archived too, so full reconstruction restores the complete
reviewed evidence tree. Original uncompressed captures remain in saved cloud
recovery and the local branch `recovery/next-maintenance-full-evidence-e01f36e`.
No history rewrite, new service, access change or additional artifact destination
is used. [Compaction validation](compaction-validation.json) records byte equivalence,
archive regeneration and rejection of altered archives, member hashes and summary counts. This changes review representation, not tested behavior or audit results.

## Readable verification results

[Site check counts](verification-summary.json), [locked inputs](check-inputs.json),
[QA runner hashes](qa-runner-hashes.json), and the [browser summary](browser-summary.json)
remain directly readable. [Exact source tree hashes](tested-source-trees.json)
cover every tracked app, asset, data file, dependency lock, diagnostic test,
QA runner and workflow. They must match the reviewed implementation head.
All eight original PNGs retain their exact paths and SHA-256s.

- **55 local site checks passed**: clean install, lint, Jest, types and a production
  build for each frontend, including prebuilds and actual Pages base paths.
- **2,256 tests passed / eight hub tests skipped** by existing series-data
  discovery guards; **29 lint warnings / zero errors**. No gate was disabled.
- F1's full build produced **85 static pages**, including OG/WebP generation.
  Ordinary CI's existing F1 build exclusion remains explicit. The controlled
  hydration diagnostic keeps genuine mismatch checks, and verifies its boundary
  removal through source hashes. The final guard was followed by successful F1
  lint, all 256 tests, and types.
- Chromium **151.0.7922.173** passed four all-site variants (40 series journeys),
  four energy journeys, 32 freshness cases and four hydration transitions.
  Desktop/mobile, light/dark, normal/reduced motion, navigation, profiles,
  standings, lap archive failure states, local captures and recovery were covered.
- The all-site runner recorded zero page errors and zero unexpected HTTP failures
  under its explicit fixture/portrait exceptions. Consoles are **not clean**:
  128 all-site + 15 freshness chart-sizing warnings, 24 WEC/IMSA SVG attribute
  errors, and 201 unique missing portrait paths remain recorded. Saved Next
  16.1.6 controls reproduce the SVG error and chart-warning category; missing
  portrait paths are absent in both source/export trees. Warning frequency,
  especially F1's, was not compared across equivalent prior-build runs.

Browser exports and the local F1 build are reused because the complete tested
source trees and locked inputs are unchanged. CI links for the compaction head
are recorded in PR18. No new public-deployment claim or production dispatch is made.

## Audit snapshot

| Site | Full findings before → after | Critical/high before → after | Production-only before → after |
| --- | --- | --- | --- |
| hub | 16 → 12 | 1/11 → 0/9 | 5 → 0 |
| f1 | 21 → 16 | 1/13 → 0/10 | 5 → 0 |
| f2 | 32 → 28 | 1/11 → 0/9 | 5 → 0 |
| f3 | 16 → 12 | 1/11 → 0/9 | 5 → 0 |
| formula-e | 32 → 28 | 1/11 → 0/9 | 5 → 0 |
| indycar | 31 → 26 | 1/11 → 0/8 | 5 → 0 |
| nascar | 32 → 28 | 1/11 → 0/9 | 5 → 0 |
| motogp | 28 → 25 | 1/9 → 0/7 | 3 → 0 |
| wec | 28 → 25 | 1/9 → 0/7 | 3 → 0 |
| imsa | 28 → 25 | 1/9 → 0/7 | 3 → 0 |
| wrc | 28 → 25 | 1/9 → 0/7 | 3 → 0 |

All eleven production-only snapshots report zero findings; full audits retain
12–28 development/tooling findings per site. This is an npm inventory result,
not a vulnerability-free application claim. The
[braces advisory](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) lists no patched
release for the ESLint chain. Some development PostCSS/Jest/parser trees also
remain affected. No forced audit fix or major tooling downgrade was applied.

## Detailed records and reproduction

[The manifest](evidence-manifest.json) lists every original path, storage location,
byte count and SHA-256, plus each archive hash. Archive members retain the reviewed
bytes exactly, including previously normalized text logs and their original-hash
record. Raw JSON is not redacted, sampled, regenerated or semantically rewritten.

| Archive | Original files | Payload bytes | Compressed bytes |
| --- | ---: | ---: | ---: |
| [Audit details](audit-details.tar.gz): 44 raw responses, query summaries, registry metadata, lock deltas | 49 | 1,089,116 | 70,447 |
| [Browser details](browser-details.tar.gz): all reports/consoles, baselines, HTML/source hashes, portrait inventory | 26 | 8,429,681 | 384,080 |
| [Validation details](validation-details.tar.gz): every command log, probes, preservation hashes and original README | 87 | 548,980 | 146,600 |

Run from the repository root with Python 3.11+ and Git. The verifier checks all
archive/member hashes, complete inventory, unchanged source trees, inputs and
runners. `--reference` additionally compares every original byte with the reviewed
Git commit; that commit remains reachable through the PR's unchanged history.

```sh
python docs/qa/next-maintenance/verify_evidence.py --reference e01f36efabc1f5d443963acf1183fcd4f1559392
python docs/qa/next-maintenance/verify_evidence.py --reference e01f36efabc1f5d443963acf1183fcd4f1559392 --extract /tmp/next-original-evidence
python docs/qa/next-maintenance/verify_evidence.py --repack /tmp/next-repacked-evidence
```

Extraction reconstructs all 174 original files in a new directory. Repacking was
verified to regenerate identical compressed bytes in the saved producer runtime
(Python 3.12.14, zlib 1.3.2); it uses sorted regular files, zero timestamps/owners,
mode 0644, gzip level 9 and an empty gzip filename. Other compression-library
versions can change compressed bytes; extraction and member verification remain
independent of that regeneration check.

To repeat the original audits, run `npm audit --json` and
`npm audit --json --omit=dev` per site. Counts are dated snapshots; later registry
results may differ. Full-audit exit 1 reflects retained findings. For frontend
regression checks use Node 20, each existing `.npmrc`, `npm ci`, `npm run lint`,
`npm test -- --ci --runInBand`, `npm run typecheck` and `npm run build` with
`PAGES_BASE_PATH=/motorsportverse` for the hub and `/motorsportverse/projects/<series>`
for series sites. Rebuilt exports can be checked with the unchanged runners:

```sh
node scripts/qa_theme_journeys.mjs <output>/sites final
node scripts/qa/energy_sandbox.mjs projects/f1-predictions/website/out <output>/energy
node scripts/qa/prediction_freshness.mjs projects/f1-predictions/website/out <output>/freshness
node scripts/qa/hydration_routes.mjs projects/f1-predictions/website/out <output>/hydration 4
```

For supplemental logging, use `--import /path/to/console-monitor.mjs` and set
`NEXT_MAINTENANCE_CONSOLE_LOG` to an output JSON path. No new credentials or provider
scraping is required. Laptop-only weekend navigation remains untransferred.

[Desktop exercise](browser-energy/desktop-overview.png) ·
[Mobile chart](browser-energy/mobile-chart.png) ·
[Mobile controls](browser-energy/mobile-controls.png) ·
[Freshness journey](browser-freshness/desktop-actual-journey.png) ·
[Conflicting metadata fixture](browser-freshness/desktop-source-conflict.png) ·
[Archived lap comparison](browser-sites/desktop-light-lap.png) ·
[Mobile hub](browser-sites/mobile-light-hub-home.png) ·
[Mobile MotoGP profile](browser-sites/mobile-light-motogp-profile.png)
