#!/usr/bin/env node
// Dataviz palette validator.
//
// The chart tokens in each site's tokens.css carry specific claims — "CVD ΔE
// 24.2", "light-end 2.13:1", "monotone L". This script is what makes those
// claims checkable. A palette comment citing measurements from a tool that does
// not exist is exactly the kind of unverifiable assertion the rest of this repo
// refuses to publish, so the tool exists.
//
//   node scripts/validate_palette.js                 # categorical + sequential
//   node scripts/validate_palette.js --ordinal       # stricter: sequential must
//                                                    # be single-hue + monotone
//   node scripts/validate_palette.js --pairs all     # every categorical pair,
//                                                    # not just model↔baseline
//   node scripts/validate_palette.js --site website  # one site instead of all
//
// Exits non-zero if any REQUIRED check fails. Pairs that are legal only with
// secondary encoding are reported as such rather than silently passing.
import { readFileSync, existsSync } from "node:fs";
import { readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));

// ── Thresholds. Each is a floor we chose; the script only measures. ──────────
const LIGHTNESS_BAND = [40, 75]; // categorical marks share a lightness band so
//                                  no series reads as "the important one"
const CHROMA_FLOOR = 20; //          a mark below this is a grey, not a series
const CVD_DELTA_FLOOR = 15; //       separation under simulated colour blindness
const NORMAL_DELTA_FLOOR = 20; //    separation for normal vision
const CONTRAST_FLOOR = 2.0; //       mark against the darkest surface it sits on
const DARK_SURFACE = "#000000";

// ── Colour maths ────────────────────────────────────────────────────────────
const hexToRgb = (h) => {
  const s = h.replace("#", "");
  const n = parseInt(s.length === 3 ? s.split("").map((c) => c + c).join("") : s, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const srgbToLinear = (c) => {
  const v = c / 255;
  return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
};
const linearToSrgb = (v) => {
  const c = v <= 0.0031308 ? v * 12.92 : 1.055 * Math.pow(Math.max(v, 0), 1 / 2.4) - 0.055;
  return Math.min(255, Math.max(0, Math.round(c * 255)));
};
function rgbToXyz([r, g, b]) {
  const [R, G, B] = [srgbToLinear(r), srgbToLinear(g), srgbToLinear(b)];
  return [
    R * 0.4124564 + G * 0.3575761 + B * 0.1804375,
    R * 0.2126729 + G * 0.7151522 + B * 0.072175,
    R * 0.0193339 + G * 0.119192 + B * 0.9503041,
  ];
}
function xyzToLab([x, y, z]) {
  const [xn, yn, zn] = [0.95047, 1.0, 1.08883];
  const f = (t) => (t > 216 / 24389 ? Math.cbrt(t) : (841 / 108) * t + 4 / 29);
  const [fx, fy, fz] = [f(x / xn), f(y / yn), f(z / zn)];
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}
const labOf = (hex) => xyzToLab(rgbToXyz(hexToRgb(hex)));
const chromaOf = (hex) => {
  const [, a, b] = labOf(hex);
  return Math.hypot(a, b);
};

// CIEDE2000. Long but standard; a simple Euclidean Lab distance materially
// over-reports separation in the blues, which is where these pairs live.
function deltaE2000(lab1, lab2) {
  const [L1, a1, b1] = lab1;
  const [L2, a2, b2] = lab2;
  const kL = 1, kC = 1, kH = 1;
  const C1 = Math.hypot(a1, b1);
  const C2 = Math.hypot(a2, b2);
  const Cbar = (C1 + C2) / 2;
  const G = 0.5 * (1 - Math.sqrt(Math.pow(Cbar, 7) / (Math.pow(Cbar, 7) + Math.pow(25, 7))));
  const a1p = (1 + G) * a1;
  const a2p = (1 + G) * a2;
  const C1p = Math.hypot(a1p, b1);
  const C2p = Math.hypot(a2p, b2);
  const deg = (r) => (r * 180) / Math.PI;
  const rad = (d) => (d * Math.PI) / 180;
  const h = (bb, aa) => {
    if (aa === 0 && bb === 0) return 0;
    const d = deg(Math.atan2(bb, aa));
    return d >= 0 ? d : d + 360;
  };
  const h1p = h(b1, a1p);
  const h2p = h(b2, a2p);
  const dLp = L2 - L1;
  const dCp = C2p - C1p;
  let dhp = 0;
  if (C1p * C2p !== 0) {
    dhp = h2p - h1p;
    if (dhp > 180) dhp -= 360;
    else if (dhp < -180) dhp += 360;
  }
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin(rad(dhp) / 2);
  const Lbp = (L1 + L2) / 2;
  const Cbp = (C1p + C2p) / 2;
  let hbp = h1p + h2p;
  if (C1p * C2p !== 0) {
    if (Math.abs(h1p - h2p) > 180) hbp = h1p + h2p < 360 ? hbp + 360 : hbp - 360;
    hbp /= 2;
  }
  const T =
    1 -
    0.17 * Math.cos(rad(hbp - 30)) +
    0.24 * Math.cos(rad(2 * hbp)) +
    0.32 * Math.cos(rad(3 * hbp + 6)) -
    0.2 * Math.cos(rad(4 * hbp - 63));
  const dTheta = 30 * Math.exp(-Math.pow((hbp - 275) / 25, 2));
  const Rc = 2 * Math.sqrt(Math.pow(Cbp, 7) / (Math.pow(Cbp, 7) + Math.pow(25, 7)));
  const Sl = 1 + (0.015 * Math.pow(Lbp - 50, 2)) / Math.sqrt(20 + Math.pow(Lbp - 50, 2));
  const Sc = 1 + 0.045 * Cbp;
  const Sh = 1 + 0.015 * Cbp * T;
  const Rt = -Math.sin(rad(2 * dTheta)) * Rc;
  return Math.sqrt(
    Math.pow(dLp / (kL * Sl), 2) +
      Math.pow(dCp / (kC * Sc), 2) +
      Math.pow(dHp / (kH * Sh), 2) +
      Rt * (dCp / (kC * Sc)) * (dHp / (kH * Sh)),
  );
}

// Machado, Oliveira & Fernandes (2009) severity-1.0 matrices. Applied in
// LINEAR light — applying them to gamma-encoded values is a common bug that
// flatters the result.
const CVD = {
  protan: [0.152286, 1.052583, -0.204868, 0.114503, 0.786281, 0.099216, -0.003882, -0.048116, 1.051998],
  deutan: [0.367322, 0.860646, -0.227968, 0.280085, 0.672501, 0.047413, -0.01182, 0.04294, 0.968881],
  tritan: [1.255528, -0.076749, -0.178779, -0.078411, 0.930809, 0.147602, 0.004733, 0.691367, 0.3039],
};
function simulate(hex, kind) {
  const m = CVD[kind];
  const [r, g, b] = hexToRgb(hex).map(srgbToLinear);
  const out = [
    m[0] * r + m[1] * g + m[2] * b,
    m[3] * r + m[4] * g + m[5] * b,
    m[6] * r + m[7] * g + m[8] * b,
  ].map(linearToSrgb);
  return `#${out.map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}
const relLuminance = (hex) => {
  const [r, g, b] = hexToRgb(hex).map(srgbToLinear);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => {
  const [la, lb] = [relLuminance(a), relLuminance(b)];
  const [hi, lo] = la > lb ? [la, lb] : [lb, la];
  return (hi + 0.05) / (lo + 0.05);
};

// ── Token extraction ────────────────────────────────────────────────────────
function readTokens(cssPath) {
  const css = readFileSync(cssPath, "utf8");
  const out = {};
  for (const m of css.matchAll(/(--viz-[a-z0-9-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\s*;/g)) {
    out[m[1]] = m[2].toLowerCase();
  }
  return out;
}
function siteDirs() {
  const dirs = [join(ROOT, "website")];
  const pj = join(ROOT, "projects");
  if (existsSync(pj)) {
    for (const p of readdirSync(pj)) {
      const d = join(pj, p, "website");
      if (existsSync(join(d, "src/styles/tokens.css"))) dirs.push(d);
    }
  }
  return dirs.filter((d) => existsSync(join(d, "src/styles/tokens.css")));
}

// ── Checks ──────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const ordinal = args.includes("--ordinal");
const allPairs = args[args.indexOf("--pairs") + 1] === "all" && args.includes("--pairs");
const onlySite = args.includes("--site") ? args[args.indexOf("--site") + 1] : null;

const CATEGORICAL = ["--viz-model", "--viz-baseline", "--viz-cat-3"];
const SEQUENTIAL = ["--viz-seq-1", "--viz-seq-2", "--viz-seq-3", "--viz-seq-4", "--viz-seq-5"];
// Pairs that are legal ONLY with secondary encoding (direct labels). Recorded
// here so the script reports them as a requirement rather than a pass.
const NEEDS_SECONDARY_ENCODING = new Set(["--viz-model|--viz-baseline|tritan"]);

let failures = 0;
let notes = 0;
const fail = (m) => {
  console.error(`  FAIL  ${m}`);
  failures++;
};
const note = (m) => {
  console.log(`  NOTE  ${m}`);
  notes++;
};
const pass = (m) => console.log(`  ok    ${m}`);

for (const dir of siteDirs()) {
  const rel = dir.replace(ROOT + "/", "");
  if (onlySite && !rel.includes(onlySite)) continue;
  const tokens = readTokens(join(dir, "src/styles/tokens.css"));
  if (Object.keys(tokens).length === 0) {
    console.log(`\n${rel}\n  (no --viz-* tokens)`);
    continue;
  }
  console.log(`\n${rel}`);

  for (const name of CATEGORICAL) {
    const hex = tokens[name];
    if (!hex) {
      fail(`${name} is missing`);
      continue;
    }
    const L = labOf(hex)[0];
    const C = chromaOf(hex);
    if (L < LIGHTNESS_BAND[0] || L > LIGHTNESS_BAND[1]) {
      fail(`${name} L=${L.toFixed(1)} outside band ${LIGHTNESS_BAND.join("-")}`);
    } else pass(`${name} L=${L.toFixed(1)} in band`);
    if (C < CHROMA_FLOOR) fail(`${name} chroma ${C.toFixed(1)} below floor ${CHROMA_FLOOR}`);
    else pass(`${name} chroma ${C.toFixed(1)}`);
    const cr = contrast(hex, DARK_SURFACE);
    if (cr < CONTRAST_FLOOR) fail(`${name} contrast ${cr.toFixed(2)}:1 on ${DARK_SURFACE}`);
    else pass(`${name} contrast ${cr.toFixed(2)}:1 on ${DARK_SURFACE}`);
  }

  const pairs = allPairs
    ? CATEGORICAL.flatMap((a, i) => CATEGORICAL.slice(i + 1).map((b) => [a, b]))
    : [["--viz-model", "--viz-baseline"]];
  for (const [a, b] of pairs) {
    if (!tokens[a] || !tokens[b]) continue;
    const dNormal = deltaE2000(labOf(tokens[a]), labOf(tokens[b]));
    if (dNormal < NORMAL_DELTA_FLOOR) fail(`${a}↔${b} normal-vision ΔE ${dNormal.toFixed(1)}`);
    else pass(`${a}↔${b} normal-vision ΔE ${dNormal.toFixed(1)}`);
    for (const kind of ["protan", "deutan", "tritan"]) {
      const d = deltaE2000(labOf(simulate(tokens[a], kind)), labOf(simulate(tokens[b], kind)));
      const key = `${a}|${b}|${kind}`;
      if (d < CVD_DELTA_FLOOR) {
        if (NEEDS_SECONDARY_ENCODING.has(key)) {
          note(`${a}↔${b} ${kind} ΔE ${d.toFixed(1)} — below floor; legal ONLY direct-labelled`);
        } else {
          fail(`${a}↔${b} ${kind} ΔE ${d.toFixed(1)} below floor ${CVD_DELTA_FLOOR}`);
        }
      } else pass(`${a}↔${b} ${kind} ΔE ${d.toFixed(1)}`);
    }
  }

  const seq = SEQUENTIAL.map((n) => tokens[n]).filter(Boolean);
  if (seq.length >= 2) {
    const Ls = seq.map((h) => labOf(h)[0]);
    const monotone = Ls.every((v, i) => i === 0 || v > Ls[i - 1]);
    if (!monotone) fail(`sequential lightness not monotone: ${Ls.map((v) => v.toFixed(1)).join(" → ")}`);
    else pass(`sequential monotone L ${Ls.map((v) => v.toFixed(1)).join(" → ")}`);
    const lightEnd = contrast(seq[seq.length - 1], DARK_SURFACE);
    if (lightEnd < CONTRAST_FLOOR) fail(`sequential light-end ${lightEnd.toFixed(2)}:1`);
    else pass(`sequential light-end ${lightEnd.toFixed(2)}:1`);
    if (ordinal) {
      // An ordinal scale must read as ONE hue; a rainbow implies categories.
      const hues = seq.map((h) => {
        const [, a, b] = labOf(h);
        const d = (Math.atan2(b, a) * 180) / Math.PI;
        return d < 0 ? d + 360 : d;
      });
      const spread = Math.max(...hues) - Math.min(...hues);
      if (spread > 20) fail(`sequential hue spread ${spread.toFixed(0)}° — not single-hue`);
      else pass(`sequential single hue (${spread.toFixed(0)}° spread)`);
      const dLs = Ls.slice(1).map((v, i) => v - Ls[i]);
      if (Math.min(...dLs) < 4) fail(`sequential adjacent ΔL min ${Math.min(...dLs).toFixed(1)}`);
      else pass(`sequential adjacent ΔL min ${Math.min(...dLs).toFixed(1)}`);
    }
  }
}

console.log(
  `\n${failures} failure(s)${notes ? `, ${notes} pair(s) requiring secondary encoding` : ""}`,
);
process.exit(failures ? 1 : 0);
