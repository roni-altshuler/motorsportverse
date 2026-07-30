"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import type { ReplayData, ReplayDriver, SeasonData } from "@/types";
import { fetchReplayData, fetchSeasonData } from "@/lib/data";
import { useSeason } from "@/lib/SeasonProvider";
import { useReducedMotion } from "@/lib/useReducedMotion";
import LoadingTire from "@/components/ui/LoadingTire";
import { cn } from "@/components/ui/cn";

interface Props {
  round: number;
}

/* ── tyre compound → colour (F1 broadcast convention) ─────────────────────── */
const COMPOUND_COLORS: Record<string, string> = {
  SOFT: "#E8002D",
  MEDIUM: "#FFD166",
  HARD: "#E6E6E6",
  INTERMEDIATE: "#43B02A",
  WET: "#0067C0",
  UNKNOWN: "#666666",
};
const compoundLetter = (c: string) => (c ? c[0].toUpperCase() : "?");

/* Surname for the tower, skipping trailing suffixes (Sainz "Jr." etc.). */
const SUFFIXES = new Set(["jr", "jr.", "sr", "sr.", "ii", "iii", "iv"]);
function lastName(full: string): string {
  const parts = full.trim().split(/\s+/);
  let i = parts.length - 1;
  while (i > 0 && SUFFIXES.has(parts[i].toLowerCase())) i--;
  return parts[i] || full;
}

/* ── track-status code → HUD accent ───────────────────────────────────────── */
const STATUS_TINT: Record<string, string> = {
  "1": "#43B02A", // green
  "2": "#FFD166", // yellow
  "3": "#FFD166",
  "4": "#FF8000", // safety car
  "5": "#E10600", // red
  "6": "#FFD166", // vsc
  "7": "#FFD166",
};
const isNeutral = (code: string) => code === "1";

/* Parse the "M x y L x y … Z" geometry path into a point list. */
function parsePath(path: string): Array<[number, number]> {
  const nums = path.match(/-?\d+(\.\d+)?/g);
  if (!nums) return [];
  const pts: Array<[number, number]> = [];
  for (let i = 0; i + 1 < nums.length; i += 2) {
    pts.push([parseFloat(nums[i]), parseFloat(nums[i + 1])]);
  }
  return pts;
}

function fmtClock(sec: number): string {
  if (!isFinite(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function fmtGap(gap: number | null, position: number): string {
  if (position === 1) return "LEADER";
  if (gap == null) return "—";
  if (gap > 200) return `+${Math.floor(gap / 90)} LAP`; // > ~2 laps → lapped
  return `+${gap.toFixed(1)}`;
}

const SPEEDS = [1, 2, 4, 8] as const;

interface TowerRow {
  driver: ReplayDriver;
  position: number;
  gap: number | null;
  lap: number;
  compound: string;
  running: boolean;
}

export default function RaceTheatre({ round }: Props) {
  const { basePath } = useSeason();
  const reduced = useReducedMotion();

  const [replay, setReplay] = useState<ReplayData | null>(null);
  const [season, setSeason] = useState<SeasonData | null>(null);
  const [loading, setLoading] = useState(true);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(1);
  const [focused, setFocused] = useState<string | null>(null);
  const [uiCursor, setUiCursor] = useState(0); // throttled session seconds for the HUD

  // Imperative animation state (refs — never trigger re-render).
  const cursorRef = useRef(0);
  const playingRef = useRef(false);
  const speedRef = useRef(1);
  const focusedRef = useRef<string | null>(null);
  const drawRef = useRef<() => void>(() => {});
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const dimsRef = useRef({ w: 0, h: 0, dpr: 1 });

  playingRef.current = playing;
  speedRef.current = speed;
  focusedRef.current = focused;

  /* ── data load ── */
  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([fetchReplayData(round, basePath), fetchSeasonData(basePath).catch(() => null)]).then(
      ([r, s]) => {
        if (!active) return;
        setReplay(r);
        setSeason(s);
        setLoading(false);
        cursorRef.current = 0;
        setUiCursor(0);
        setPlaying(r != null && !reduced); // autoplay the full experience; respect reduced-motion
      },
    );
    return () => {
      active = false;
    };
  }, [round, basePath, reduced]);

  const trackPoints = useMemo(
    () => (replay?.geometry?.path ? parsePath(replay.geometry.path) : []),
    [replay],
  );

  /* ── position sampling ── */
  const carAt = useCallback(
    (code: string, t: number): { x: number; y: number } | null => {
      if (!replay) return null;
      const car = replay.cars[code];
      if (!car) return null;
      const dt = replay.dt || 1;
      const fi = t / dt;
      const i = Math.floor(fi);
      const frac = fi - i;
      const n = car.x.length;
      if (i < 0 || i >= n) return null;
      const x0 = car.x[i];
      const y0 = car.y[i];
      if (x0 == null || y0 == null) return null;
      const x1 = i + 1 < n ? car.x[i + 1] : null;
      const y1 = i + 1 < n ? car.y[i + 1] : null;
      if (x1 == null || y1 == null) return { x: x0, y: y0 };
      return { x: x0 + (x1 - x0) * frac, y: y0 + (y1 - y0) * frac };
    },
    [replay],
  );

  // Frame index for a session time (all per-driver arrays share frameCount).
  const frameIndex = useCallback(
    (t: number): number => {
      if (!replay) return 0;
      const dt = replay.dt || 1;
      return Math.min(Math.max(Math.round(t / dt), 0), replay.frameCount - 1);
    },
    [replay],
  );

  /* current track-status segment at time t */
  const statusAt = useCallback(
    (t: number) => {
      if (!replay || replay.trackStatus.length === 0) return { code: "1", label: "Green" };
      let cur = replay.trackStatus[0];
      for (const s of replay.trackStatus) {
        if (s.t <= t) cur = s;
        else break;
      }
      return cur;
    },
    [replay],
  );

  /* running order at time t */
  const orderAt = useCallback(
    (t: number): TowerRow[] => {
      if (!replay) return [];
      const rows: TowerRow[] = [];
      const idx = frameIndex(t);
      for (const d of replay.drivers) {
        const car = replay.cars[d.code];
        if (!car) continue;
        const running = car.x[idx] != null;
        const lap = car.lap[idx] ?? 0;
        const gap = car.gap[idx];
        // tyre compound from stints by lap
        let compound = "UNKNOWN";
        const stints = replay.stints[d.code] || [];
        for (const st of stints) {
          if (lap >= st.startLap && lap <= st.endLap) compound = st.compound;
        }
        rows.push({ driver: d, position: 0, gap, lap, compound, running });
      }
      // order: running cars by gap ascending; retired/not-yet cars sink to the bottom.
      rows.sort((a, b) => {
        if (a.running !== b.running) return a.running ? -1 : 1;
        const ga = a.gap ?? 1e9;
        const gb = b.gap ?? 1e9;
        return ga - gb;
      });
      rows.forEach((r, i) => (r.position = i + 1));
      return rows;
    },
    [replay, frameIndex],
  );

  /* ── canvas sizing (DPR-aware) ── */
  const resize = useCallback(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const rect = wrap.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    dimsRef.current = { w: rect.width, h: rect.height, dpr };
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    canvas.style.width = `${rect.width}px`;
    canvas.style.height = `${rect.height}px`;
    drawRef.current();
  }, []);

  useEffect(() => {
    resize();
    const ro = new ResizeObserver(resize);
    if (wrapRef.current) ro.observe(wrapRef.current);
    window.addEventListener("resize", resize);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, [resize, replay]);

  /* ── draw closure (rebuilt when static inputs change) ── */
  useEffect(() => {
    drawRef.current = () => {
      const canvas = canvasRef.current;
      if (!canvas || !replay) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const { w, h, dpr } = dimsRef.current;
      if (w === 0 || h === 0) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      const margin = 46;
      const scale = Math.min(w, h) / (1000 + margin * 2);
      const ox = (w - 1000 * scale) / 2;
      const oy = (h - 1000 * scale) / 2;
      const px = (x: number) => ox + x * scale;
      const py = (y: number) => oy + y * scale;

      const t = cursorRef.current;
      const status = statusAt(t);
      const tint = STATUS_TINT[status.code] || "#43B02A";
      const neutral = isNeutral(status.code);

      // ── track ribbon ──
      if (trackPoints.length > 1) {
        const stroke = (width: number, color: string, dash?: number[]) => {
          ctx.beginPath();
          ctx.moveTo(px(trackPoints[0][0]), py(trackPoints[0][1]));
          for (let i = 1; i < trackPoints.length; i++)
            ctx.lineTo(px(trackPoints[i][0]), py(trackPoints[i][1]));
          ctx.closePath();
          ctx.lineJoin = "round";
          ctx.lineCap = "round";
          ctx.setLineDash(dash || []);
          ctx.lineWidth = width;
          ctx.strokeStyle = color;
          ctx.stroke();
          ctx.setLineDash([]);
        };
        // outer glow when a flag is out
        if (!neutral) {
          ctx.shadowColor = tint;
          ctx.shadowBlur = 26;
          stroke(15, tint + "55");
          ctx.shadowBlur = 0;
        }
        stroke(15, "#242424"); // asphalt edge
        stroke(11, "#3a3a3a"); // asphalt
        stroke(1.4, neutral ? "#5a5a5a" : tint + "cc", [2, 7]); // centre line / flag
      }

      // ── start/finish bar ──
      if (trackPoints.length > 2) {
        const [sx, sy] = trackPoints[0];
        const [nx, ny] = trackPoints[1];
        const dx = nx - sx;
        const dy = ny - sy;
        const len = Math.hypot(dx, dy) || 1;
        const perpX = (-dy / len) * 15;
        const perpY = (dx / len) * 15;
        ctx.strokeStyle = "#f5f5f5";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(px(sx + perpX), py(sy + perpY));
        ctx.lineTo(px(sx - perpX), py(sy - perpY));
        ctx.stroke();
      }

      // ── corner number pills ──
      if (replay.geometry.corners?.length) {
        ctx.font = `${Math.max(9, 12 * scale * 1.2)}px var(--font-mono, monospace)`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        for (const c of replay.geometry.corners) {
          ctx.beginPath();
          ctx.arc(px(c.x), py(c.y), 8.5, 0, Math.PI * 2);
          ctx.fillStyle = "#0d0d0d";
          ctx.fill();
          ctx.lineWidth = 1;
          ctx.strokeStyle = "#3a3a3a";
          ctx.stroke();
          ctx.fillStyle = "#8a8a8a";
          ctx.fillText(String(c.number), px(c.x), py(c.y) + 0.5);
        }
      }

      // ── cars ──
      const rows = orderAt(t);
      const focusedCode = focusedRef.current;
      // draw retired/backmarkers first, leaders + focused last (on top)
      const draw = [...rows].reverse();
      const carR = Math.max(6, 10.5 * scale * 1.3);
      for (const row of draw) {
        if (!row.running) continue;
        const pos = carAt(row.driver.code, t);
        if (!pos) continue;
        const cx = px(pos.x);
        const cy = py(pos.y);
        const isFocus = focusedCode === row.driver.code;
        const dim = focusedCode != null && !isFocus;
        const color = row.driver.teamColor || "#cccccc";

        ctx.globalAlpha = dim ? 0.28 : 1;
        // halo for leader / focused
        if (row.position === 1 || isFocus) {
          ctx.beginPath();
          ctx.arc(cx, cy, carR + 4, 0, Math.PI * 2);
          ctx.fillStyle = (isFocus ? "#ffffff" : color) + "33";
          ctx.fill();
        }
        ctx.beginPath();
        ctx.arc(cx, cy, carR, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = isFocus ? "#ffffff" : "#0a0a0a";
        ctx.stroke();
        // tricode label
        ctx.globalAlpha = dim ? 0.4 : 1;
        ctx.font = `${Math.max(8, 9.5 * scale * 1.25)}px var(--font-mono, monospace)`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "#ffffff";
        ctx.fillText(row.driver.code, cx, cy + 0.5);
        ctx.globalAlpha = 1;
      }
    };
    drawRef.current();
  }, [replay, trackPoints, carAt, orderAt, statusAt]);

  /* ── RAF driver ── */
  useEffect(() => {
    if (!replay) return;
    let raf = 0;
    let last = performance.now();
    let lastUi = 0;
    const loop = (now: number) => {
      const dtReal = (now - last) / 1000;
      last = now;
      if (playingRef.current) {
        cursorRef.current += dtReal * speedRef.current;
        if (cursorRef.current >= replay.duration) {
          cursorRef.current = replay.duration;
          playingRef.current = false;
          setPlaying(false);
        }
      }
      drawRef.current();
      if (now - lastUi > 66) {
        // ~15fps HUD refresh
        lastUi = now;
        setUiCursor(cursorRef.current);
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [replay]);

  /* ── controls ── */
  const seek = useCallback(
    (t: number) => {
      if (!replay) return;
      cursorRef.current = Math.min(Math.max(0, t), replay.duration);
      setUiCursor(cursorRef.current);
      drawRef.current();
    },
    [replay],
  );

  const togglePlay = useCallback(() => {
    if (!replay) return;
    if (cursorRef.current >= replay.duration) cursorRef.current = 0;
    setPlaying((p) => !p);
  }, [replay]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      } else if (e.code === "ArrowRight") {
        seek(cursorRef.current + 5);
      } else if (e.code === "ArrowLeft") {
        seek(cursorRef.current - 5);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlay, seek]);

  /* ── derived HUD state (from throttled uiCursor) ── */
  const rows = useMemo(() => (replay ? orderAt(uiCursor) : []), [replay, orderAt, uiCursor]);
  const status = useMemo(() => (replay ? statusAt(uiCursor) : null), [replay, statusAt, uiCursor]);
  const leaderLap = rows.length ? rows[0].lap : 0;
  const calendarName =
    season?.calendar?.find((e) => e.round === round)?.name || replay?.name || `Round ${round}`;

  if (loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <LoadingTire label="Loading race replay" />
      </div>
    );
  }

  if (!replay) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center gap-4 px-6 text-center">
        <div className="hud-kicker text-[color:var(--muted)]">Race Theatre</div>
        <h1 className="display-md text-[color:var(--ink)]">Replay not available yet</h1>
        <p className="body-md text-[color:var(--body)]">
          {calendarName} hasn&rsquo;t been reconstructed for the Theatre yet. Replays are baked from
          race telemetry after the chequered flag.
        </p>
        <Link href="/calendar" className="button-label mt-2 text-[color:var(--link)]">
          ← Back to the calendar
        </Link>
      </div>
    );
  }

  const tint = status ? STATUS_TINT[status.code] || "#43B02A" : "#43B02A";
  const flagActive = status ? !isNeutral(status.code) : false;

  return (
    <div className="mx-auto max-w-[1500px] px-3 py-4 sm:px-5">
      {/* header */}
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="hud-kicker text-[color:var(--muted)]">
            Race Theatre · Round {replay.round}
          </div>
          <h1 className="display-sm text-[color:var(--ink)]">{calendarName}</h1>
        </div>
        <div className="flex items-center gap-4 font-[family-name:var(--font-mono)] text-[color:var(--body)]">
          <div className="flex flex-col items-end leading-tight">
            <span className="text-[10px] uppercase tracking-wider text-[color:var(--muted)]">Lap</span>
            <span className="font-tabular text-lg text-[color:var(--ink)]">
              {leaderLap}
              <span className="text-[color:var(--muted)]">/{replay.totalLaps}</span>
            </span>
          </div>
          <div
            className="rounded-sm px-3 py-1.5 text-xs font-semibold uppercase tracking-wider"
            style={{
              color: flagActive ? "#0a0a0a" : tint,
              background: flagActive ? tint : "transparent",
              border: `1px solid ${tint}`,
            }}
          >
            {status?.label || "Green"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_320px]">
        {/* ── stage ── */}
        <div className="flex flex-col gap-2">
          <div
            ref={wrapRef}
            className="relative aspect-[4/3] w-full overflow-hidden rounded-[4px] border border-[color:var(--hairline)] bg-[color:var(--surface-soft)] sm:aspect-[16/10]"
            style={{
              boxShadow: flagActive ? `inset 0 0 90px ${tint}22` : undefined,
            }}
          >
            <canvas ref={canvasRef} className="absolute inset-0" />
          </div>

          {/* transport + scrubber */}
          <div className="flex flex-col gap-2 rounded-[4px] border border-[color:var(--hairline)] bg-[color:var(--surface-card)] px-3 py-2.5">
            <div className="flex items-center gap-3">
              <button
                onClick={togglePlay}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[color:var(--hairline-strong)] bg-[color:var(--surface-elevated)] text-[color:var(--ink)] transition-colors hover:border-[color:var(--accent-f1-red)]"
                aria-label={playing ? "Pause" : "Play"}
              >
                {playing ? (
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                    <rect x="2" y="1" width="3.5" height="12" />
                    <rect x="8.5" y="1" width="3.5" height="12" />
                  </svg>
                ) : (
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
                    <path d="M2 1l11 6-11 6z" />
                  </svg>
                )}
              </button>

              {/* scrubber with flag markers */}
              <div className="relative flex-1">
                <div className="pointer-events-none absolute inset-x-0 top-1/2 flex h-1.5 -translate-y-1/2 overflow-hidden rounded-full">
                  {replay.trackStatus.map((s, i) => {
                    const next = replay.trackStatus[i + 1];
                    const start = (s.t / replay.duration) * 100;
                    const end = ((next ? next.t : replay.duration) / replay.duration) * 100;
                    return (
                      <span
                        key={i}
                        className="absolute top-0 h-full"
                        style={{
                          left: `${start}%`,
                          width: `${Math.max(0, end - start)}%`,
                          background: isNeutral(s.code)
                            ? "var(--hairline-strong)"
                            : STATUS_TINT[s.code],
                          opacity: isNeutral(s.code) ? 1 : 0.9,
                        }}
                      />
                    );
                  })}
                </div>
                <input
                  type="range"
                  min={0}
                  max={replay.duration}
                  step={0.5}
                  value={uiCursor}
                  onChange={(e) => seek(parseFloat(e.target.value))}
                  className="theatre-scrubber relative w-full"
                  aria-label="Race timeline"
                />
              </div>

              <span className="font-tabular shrink-0 text-xs text-[color:var(--muted)]">
                {fmtClock(uiCursor)} / {fmtClock(replay.duration)}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1">
                {SPEEDS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setSpeed(s)}
                    className={cn(
                      "rounded-sm px-2 py-1 text-xs font-[family-name:var(--font-mono)] transition-colors",
                      speed === s
                        ? "bg-[color:var(--surface-elevated)] text-[color:var(--ink)]"
                        : "text-[color:var(--muted)] hover:text-[color:var(--body)]",
                    )}
                  >
                    {s}×
                  </button>
                ))}
                <button
                  onClick={() => {
                    seek(0);
                    setPlaying(true);
                  }}
                  className="ml-2 rounded-sm px-2 py-1 text-xs font-[family-name:var(--font-mono)] text-[color:var(--muted)] transition-colors hover:text-[color:var(--body)]"
                >
                  ↺ Restart
                </button>
              </div>
              <div className="hidden text-[10px] uppercase tracking-wider text-[color:var(--muted)] sm:block">
                Space play/pause · ← → seek · click a driver to track
              </div>
            </div>
          </div>
        </div>

        {/* ── timing tower ── */}
        <div className="flex flex-col rounded-[4px] border border-[color:var(--hairline)] bg-[color:var(--surface-card)]">
          <div className="flex items-center justify-between border-b border-[color:var(--hairline)] px-3 py-2">
            <span className="hud-kicker text-[color:var(--muted)]">Timing Tower</span>
            <span className="hud-kicker text-[color:var(--muted)]">Gap</span>
          </div>
          <div className="max-h-[560px] overflow-y-auto lg:max-h-[calc(56vh)]">
            {rows.map((row) => {
              const isFocus = focused === row.driver.code;
              return (
                <button
                  key={row.driver.code}
                  onClick={() => setFocused(isFocus ? null : row.driver.code)}
                  className={cn(
                    "flex w-full items-center gap-2 border-b border-[color:var(--hairline)] px-2 py-1.5 text-left transition-colors last:border-b-0",
                    isFocus
                      ? "bg-[color:var(--surface-elevated)]"
                      : "hover:bg-[color:var(--surface-soft)]",
                    !row.running && "opacity-40",
                  )}
                >
                  <span className="font-tabular w-5 shrink-0 text-center text-xs text-[color:var(--muted)]">
                    {row.running ? row.position : "—"}
                  </span>
                  <span
                    className="h-5 w-1 shrink-0 rounded-full"
                    style={{ background: row.driver.teamColor }}
                  />
                  <span className="font-[family-name:var(--font-mono)] w-9 shrink-0 text-sm font-semibold text-[color:var(--ink)]">
                    {row.driver.code}
                  </span>
                  <span
                    className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold"
                    style={{
                      border: `1.5px solid ${COMPOUND_COLORS[row.compound] || COMPOUND_COLORS.UNKNOWN}`,
                      color: COMPOUND_COLORS[row.compound] || COMPOUND_COLORS.UNKNOWN,
                    }}
                    title={row.compound}
                  >
                    {compoundLetter(row.compound)}
                  </span>
                  <span className="flex-1 truncate text-xs text-[color:var(--body)]">
                    {lastName(row.driver.name)}
                  </span>
                  <span
                    className={cn(
                      "font-tabular shrink-0 text-xs",
                      row.position === 1
                        ? "text-[color:var(--accent-podium-1)]"
                        : "text-[color:var(--muted)]",
                    )}
                  >
                    {row.running ? fmtGap(row.gap, row.position) : "OUT"}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* scoped scrubber styling */}
      <style
        dangerouslySetInnerHTML={{
          __html: `
        .theatre-scrubber { -webkit-appearance: none; appearance: none; background: transparent; height: 20px; cursor: pointer; }
        .theatre-scrubber::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 14px; height: 14px; border-radius: 9999px; background: var(--ink); border: 2px solid var(--canvas); box-shadow: 0 0 0 1px var(--hairline-strong); }
        .theatre-scrubber::-moz-range-thumb { width: 14px; height: 14px; border-radius: 9999px; background: var(--ink); border: 2px solid var(--canvas); }
      `,
        }}
      />
    </div>
  );
}
