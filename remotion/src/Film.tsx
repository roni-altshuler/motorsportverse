/**
 * MotorsportVerseFilm — a cinematic, screen-recorded-style product film that
 * walks through the prediction engine end to end: intro → ingest → model engine
 * → calibrate → simulate → forecast → self-grade → outro. Mirrors the website's
 * visual language (dark canvas, crimson + teal, mono data type) so the rendered
 * MP4 reads as the same product, just filmed.
 */

import React from "react";
import {
  AbsoluteFill,
  Easing,
  Img,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const WIDTH = 1280;
export const HEIGHT = 720;
export const FPS = 30;

const SCENES = [
  { key: "intro", dur: 90 },
  { key: "ingest", dur: 150 },
  { key: "engine", dur: 168 },
  { key: "calibrate", dur: 150 },
  { key: "simulate", dur: 168 },
  { key: "forecast", dur: 150 },
  { key: "grade", dur: 168 },
  { key: "outro", dur: 108 },
] as const;

export const FILM_DURATION = SCENES.reduce((a, s) => a + s.dur, 0);

const C = {
  canvas: "#060910",
  surface: "#0c1119",
  surface2: "#111824",
  surface3: "#18202e",
  ink: "#f4f7fb",
  inkMuted: "#aeb8c6",
  inkDim: "#6c7787",
  accent: "#e7102f",
  accentBright: "#ff2d49",
  teal: "#38e1c6",
  blue: "#6aa6ff",
  line: "rgba(255,255,255,0.09)",
  lineStrong: "rgba(255,255,255,0.16)",
};
const SANS = "Inter, 'Helvetica Neue', Arial, sans-serif";
const MONO = "'SF Mono', 'JetBrains Mono', ui-monospace, monospace";

const STEP_LABELS = ["Ingest", "Model engine", "Calibrate", "Simulate", "Forecast", "Self-grade"];

/* ----------------------------------------------------------------- helpers */

const fadeInOut = (frame: number, dur: number, f = 16) =>
  interpolate(frame, [0, f, dur - f, dur], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

/* ---------------------------------------------------------------- chrome */

const FilmBackground: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = (sp: number, ph: number) => Math.sin(frame * sp + ph);
  const trail = (y: number, sp: number, w: number, col: string, op: number) => {
    const x = ((frame * sp) % (WIDTH + 600)) - 300;
    return (
      <div
        style={{
          position: "absolute",
          top: y,
          left: x,
          width: w,
          height: 2,
          background: `linear-gradient(90deg, transparent, ${col})`,
          opacity: op,
          filter: "blur(0.4px)",
        }}
      />
    );
  };
  return (
    <AbsoluteFill style={{ background: C.canvas, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(50% 42% at ${50 + drift(0.004, 0) * 6}% -6%, rgba(231,16,47,0.16), transparent 60%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(42% 38% at ${86 + drift(0.005, 2) * 5}% 12%, rgba(56,225,198,0.08), transparent 58%)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(46% 40% at ${8 + drift(0.005, 4) * 5}% 32%, rgba(106,166,255,0.06), transparent 58%)`,
        }}
      />
      {trail(120, 7, 360, "rgba(244,247,251,0.5)", 0.5)}
      {trail(300, 4.5, 520, "rgba(255,45,73,0.5)", 0.45)}
      {trail(470, 9, 280, "rgba(56,225,198,0.45)", 0.4)}
      {trail(610, 6, 440, "rgba(106,166,255,0.4)", 0.38)}
    </AbsoluteFill>
  );
};

const AppWindow: React.FC<{
  step: number;
  children: React.ReactNode;
}> = ({ step, children }) => {
  return (
    <div
      style={{
        position: "absolute",
        left: 140,
        right: 140,
        top: 96,
        bottom: 150,
        borderRadius: 20,
        border: `1px solid ${C.lineStrong}`,
        background: "linear-gradient(180deg, rgba(20,26,36,0.72), rgba(8,11,18,0.9))",
        boxShadow: "0 40px 120px -40px rgba(0,0,0,0.9)",
        overflow: "hidden",
        backdropFilter: "blur(8px)",
      }}
    >
      {/* title bar */}
      <div
        style={{
          height: 46,
          display: "flex",
          alignItems: "center",
          gap: 14,
          padding: "0 18px",
          borderBottom: `1px solid ${C.line}`,
        }}
      >
        <div style={{ display: "flex", gap: 7 }}>
          {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
            <div key={c} style={{ width: 11, height: 11, borderRadius: 99, background: c, opacity: 0.85 }} />
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Dot />
          <span style={{ fontFamily: MONO, fontSize: 12.5, letterSpacing: 1.5, color: C.inkMuted }}>
            motorsportverse — prediction engine
          </span>
        </div>
        <div
          style={{
            marginLeft: "auto",
            fontFamily: MONO,
            fontSize: 12,
            color: C.inkDim,
            border: `1px solid ${C.line}`,
            borderRadius: 99,
            padding: "3px 12px",
          }}
        >
          step {String(step).padStart(2, "0")} / 06
        </div>
      </div>
      <div style={{ position: "absolute", inset: "46px 0 0 0" }}>{children}</div>
    </div>
  );
};

const Dot: React.FC = () => {
  const frame = useCurrentFrame();
  const o = 0.5 + 0.5 * Math.sin(frame * 0.18);
  return <div style={{ width: 8, height: 8, borderRadius: 99, background: C.teal, opacity: o, boxShadow: `0 0 8px ${C.teal}` }} />;
};

const Caption: React.FC<{ step: number; title: string; blurb: string; local: number }> = ({
  step,
  title,
  blurb,
  local,
}) => {
  const y = interpolate(local, [0, 18], [16, 0], { extrapolateRight: "clamp" });
  const o = interpolate(local, [0, 18], [0, 1], { extrapolateRight: "clamp" });
  return (
    <div style={{ position: "absolute", left: 140, bottom: 70, transform: `translateY(${y}px)`, opacity: o }}>
      <div style={{ fontFamily: MONO, fontSize: 13, letterSpacing: 2, color: C.accentBright, textTransform: "uppercase" }}>
        Step {step} · {STEP_LABELS[step - 1]}
      </div>
      <div style={{ fontFamily: SANS, fontSize: 30, fontWeight: 700, color: C.ink, marginTop: 6 }}>{title}</div>
      <div style={{ fontFamily: SANS, fontSize: 16, color: C.inkMuted, marginTop: 4, maxWidth: 640 }}>{blurb}</div>
    </div>
  );
};

const StepStrip: React.FC<{ active: number }> = ({ active }) => (
  <div style={{ position: "absolute", left: 140, right: 140, bottom: 34, display: "flex", gap: 8 }}>
    {STEP_LABELS.map((label, i) => {
      const on = i + 1 === active;
      return (
        <div key={label} style={{ flex: 1, display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{
              width: 20,
              height: 20,
              borderRadius: 99,
              background: on ? C.accent : C.surface3,
              color: on ? "#fff" : C.inkDim,
              boxShadow: on ? `0 0 14px ${C.accent}` : "none",
              fontFamily: MONO,
              fontSize: 10,
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            {i + 1}
          </div>
          <span style={{ fontFamily: MONO, fontSize: 10.5, letterSpacing: 1, textTransform: "uppercase", color: on ? C.ink : C.inkDim }}>
            {label}
          </span>
        </div>
      );
    })}
  </div>
);

const Stage: React.FC<{
  step: number;
  title: string;
  blurb: string;
  dur: number;
  children: React.ReactNode;
}> = ({ step, title, blurb, dur, children }) => {
  const local = useCurrentFrame();
  return (
    <AbsoluteFill style={{ opacity: fadeInOut(local, dur) }}>
      <AppWindow step={step}>{children}</AppWindow>
      <Caption step={step} title={title} blurb={blurb} local={local} />
      <StepStrip active={step} />
    </AbsoluteFill>
  );
};

/* small reusable bits */
const Panel: React.FC<{ style?: React.CSSProperties; children: React.ReactNode }> = ({ style, children }) => (
  <div
    style={{
      border: `1px solid ${C.line}`,
      borderRadius: 14,
      background: "rgba(12,17,25,0.7)",
      padding: 22,
      ...style,
    }}
  >
    {children}
  </div>
);

const monoChip = (text: string, color = C.inkMuted): React.CSSProperties => ({
  fontFamily: MONO,
  fontSize: 13,
  color,
});

/* ---------------------------------------------------------------- scenes */

const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 200 } });
  const logoScale = interpolate(s, [0, 1], [0.86, 1]);
  const o = fadeInOut(frame, SCENES[0].dur, 18);
  const lineW = interpolate(frame, [18, 50], [0, 320], { extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: o }}>
      <Img
        src={staticFile("motorsportverse-logo.png")}
        style={{ width: 560, transform: `scale(${logoScale})`, filter: "drop-shadow(0 10px 60px rgba(231,16,47,0.3))" }}
      />
      <div style={{ height: 2, width: lineW, marginTop: 14, background: `linear-gradient(90deg, transparent, ${C.accent}, transparent)` }} />
      <div style={{ fontFamily: SANS, fontSize: 34, fontWeight: 700, color: C.ink, marginTop: 26, letterSpacing: -0.5 }}>
        How the prediction engine works
      </div>
      <div style={{ fontFamily: MONO, fontSize: 14, letterSpacing: 3, color: C.inkDim, marginTop: 12, textTransform: "uppercase" }}>
        raw timing → AI model → a result that grades itself
      </div>
    </AbsoluteFill>
  );
};

const IngestScene: React.FC = () => {
  const frame = useCurrentFrame();
  const sources = ["FastF1", "Jolpica", "Archives", "Live timing"];
  const rows = [
    ["VER", "1:18.204", "S1"],
    ["NOR", "1:18.411", "S2"],
    ["LEC", "1:18.538", "S1"],
    ["PIA", "1:18.602", "S3"],
    ["RUS", "1:18.690", "S2"],
    ["HAM", "1:18.744", "S1"],
  ];
  return (
    <Stage
      step={1}
      dur={SCENES[1].dur}
      title="Every timing feed, one schema"
      blurb="Official lap times and decades of race archives flow into one canonical store."
    >
      <div style={{ padding: 30, display: "flex", gap: 26, height: "100%" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, width: 200 }}>
          <div style={monoChip("SOURCES", C.inkDim)} />
          {sources.map((src, i) => {
            const o = interpolate(frame, [10 + i * 8, 24 + i * 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const x = interpolate(frame, [10 + i * 8, 24 + i * 8], [-18, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div
                key={src}
                style={{
                  opacity: o,
                  transform: `translateX(${x}px)`,
                  border: `1px solid ${C.lineStrong}`,
                  borderRadius: 99,
                  background: C.surface2,
                  padding: "8px 14px",
                  fontFamily: MONO,
                  fontSize: 13,
                  color: C.inkMuted,
                }}
              >
                ↳ {src}
              </div>
            );
          })}
        </div>
        <Panel style={{ flex: 1 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 14 }}>
            <span style={monoChip("history.duckdb", C.inkDim)} />
            <span style={monoChip(`${Math.min(6, Math.floor((frame - 30) / 8) + 1 > 0 ? Math.min(6, Math.floor((frame - 30) / 8) + 1) : 0)} / 6 rows`, C.teal)} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {rows.map((r, i) => {
              const start = 30 + i * 9;
              const o = interpolate(frame, [start, start + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              const x = interpolate(frame, [start, start + 12], [-26, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
              return (
                <div
                  key={r[0]}
                  style={{
                    opacity: o,
                    transform: `translateX(${x}px)`,
                    display: "flex",
                    justifyContent: "space-between",
                    border: `1px solid ${C.line}`,
                    borderRadius: 8,
                    background: C.canvas,
                    padding: "10px 14px",
                    fontFamily: MONO,
                    fontSize: 14,
                  }}
                >
                  <span style={{ color: C.ink, fontWeight: 600 }}>{r[0]}</span>
                  <span style={{ color: C.inkMuted }}>{r[1]}</span>
                  <span style={{ color: C.teal }}>{r[2]} ✓</span>
                </div>
              );
            })}
          </div>
        </Panel>
      </div>
    </Stage>
  );
};

const EngineScene: React.FC = () => {
  const frame = useCurrentFrame();
  const features = ["Quali pace", "Circuit type", "Driver form", "Tyre model", "Weather"];
  const scores = [
    ["VER", "0.94"],
    ["NOR", "0.88"],
    ["LEC", "0.85"],
  ];
  const pulse = 1 + 0.12 * Math.sin(frame * 0.22);
  return (
    <Stage
      step={2}
      dur={SCENES[2].dur}
      title="The ML engine turns pace into skill"
      blurb="Features stream into a gradient-boosted ensemble that scores every driver's true pace."
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 70px", height: "100%" }}>
        {/* features in */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10, width: 220 }}>
          {features.map((f, i) => {
            const o = interpolate(frame, [8 + i * 7, 22 + i * 7], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={f} style={{ opacity: o, border: `1px solid ${C.line}`, borderRadius: 9, background: C.canvas, padding: "10px 14px", fontFamily: MONO, fontSize: 13, color: C.inkMuted }}>
                {f}
              </div>
            );
          })}
        </div>
        {/* engine core */}
        <div style={{ position: "relative", width: 220, height: 220, display: "flex", alignItems: "center", justifyContent: "center" }}>
          {[0, 1, 2, 3].map((r) => {
            const rp = 0.5 + 0.5 * Math.sin(frame * 0.14 - r * 0.6);
            return (
              <div
                key={r}
                style={{
                  position: "absolute",
                  width: 80 + r * 38,
                  height: 80 + r * 38,
                  borderRadius: 99,
                  border: `1.5px solid ${C.accent}`,
                  opacity: 0.18 + rp * 0.45,
                }}
              />
            );
          })}
          <div
            style={{
              width: 74,
              height: 74,
              borderRadius: 99,
              transform: `scale(${pulse})`,
              background: `radial-gradient(circle, ${C.accentBright}, ${C.accent} 60%, #7a0a18)`,
              boxShadow: `0 0 40px ${C.accent}`,
            }}
          />
          <div style={{ position: "absolute", bottom: -6, fontFamily: MONO, fontSize: 11, letterSpacing: 1.5, color: C.inkDim }}>
            GBR + XGB
          </div>
        </div>
        {/* scores out */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, width: 200 }}>
          {scores.map((sc, i) => {
            const o = interpolate(frame, [60 + i * 12, 78 + i * 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const x = interpolate(frame, [60 + i * 12, 78 + i * 12], [22, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={sc[0]} style={{ opacity: o, transform: `translateX(${x}px)`, display: "flex", justifyContent: "space-between", border: `1px solid ${C.lineStrong}`, borderRadius: 9, background: C.canvas, padding: "11px 16px", fontFamily: MONO, fontSize: 15 }}>
                <span style={{ color: C.ink, fontWeight: 600 }}>{sc[0]}</span>
                <span style={{ color: C.teal }}>{sc[1]}</span>
              </div>
            );
          })}
        </div>
      </div>
    </Stage>
  );
};

const CalibrateScene: React.FC = () => {
  const frame = useCurrentFrame();
  const bars = [
    { name: "Win", raw: 0.62, cal: 0.44 },
    { name: "Podium", raw: 0.88, cal: 0.71 },
    { name: "Points", raw: 0.97, cal: 0.93 },
  ];
  const t = interpolate(frame, [20, 70], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) });
  const badge = interpolate(frame, [70, 86], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Stage step={3} dur={SCENES[3].dur} title="Probabilities that tell the truth" blurb="Raw model output is calibrated against history — confidence the data actually supports.">
      <div style={{ padding: "44px 80px", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 26 }}>
          <span style={monoChip("PROBABILITY CALIBRATION", C.inkDim)} />
          <span style={{ ...monoChip("CALIBRATED", C.teal), opacity: badge, border: `1px solid ${C.teal}`, borderRadius: 99, padding: "3px 12px", fontSize: 11 }} />
        </div>
        {bars.map((b) => {
          const w = b.raw + (b.cal - b.raw) * t;
          return (
            <div key={b.name} style={{ marginBottom: 22 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontFamily: MONO, fontSize: 13, color: C.inkMuted, marginBottom: 7 }}>
                <span>{b.name}</span>
                <span style={{ color: C.ink }}>{Math.round(w * 100)}%</span>
              </div>
              <div style={{ height: 12, borderRadius: 99, background: C.canvas, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${w * 100}%`, borderRadius: 99, background: `linear-gradient(90deg, ${C.accent}, ${C.teal})` }} />
              </div>
            </div>
          );
        })}
      </div>
    </Stage>
  );
};

const SimulateScene: React.FC = () => {
  const frame = useCurrentFrame();
  const runs = Math.min(5000, Math.max(0, Math.round(interpolate(frame, [10, 120], [0, 5000]))));
  const podium = interpolate(frame, [110, 140], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Stage step={4} dur={SCENES[4].dur} title="Thousands of races, one grid" blurb="A Monte-Carlo race engine runs the weekend over and over to map every outcome.">
      <div style={{ padding: "36px 70px", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 18 }}>
          <span style={monoChip("MONTE-CARLO RACE ENGINE", C.inkDim)} />
          <span style={monoChip(`run ${runs.toLocaleString()} / 5,000`, C.teal)} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(20, 1fr)", gap: 6 }}>
          {Array.from({ length: 60 }).map((_, i) => {
            const flick = 0.3 + 0.7 * Math.abs(Math.sin(frame * 0.3 + i * 1.7));
            const top3 = i % 20 < 3;
            return (
              <div
                key={i}
                style={{
                  aspectRatio: "1",
                  borderRadius: 4,
                  background: top3 ? C.accent : C.surface3,
                  opacity: top3 ? 0.7 + 0.3 * flick : 0.25 + 0.5 * flick,
                }}
              />
            );
          })}
        </div>
        <div style={{ display: "flex", gap: 12, marginTop: 26, opacity: podium }}>
          {["P1 · VER", "P2 · NOR", "P3 · LEC"].map((p, i) => (
            <div key={p} style={{ flex: 1, textAlign: "center", border: `1px solid ${i === 0 ? C.accent : C.lineStrong}`, borderRadius: 10, background: C.canvas, padding: "12px 0", fontFamily: MONO, fontSize: 15, color: C.ink }}>
              {p}
            </div>
          ))}
        </div>
      </div>
    </Stage>
  );
};

const ForecastScene: React.FC = () => {
  const frame = useCurrentFrame();
  const podium = [
    { pos: "1", code: "VER", p: 0.41 },
    { pos: "2", code: "NOR", p: 0.27 },
    { pos: "3", code: "LEC", p: 0.19 },
  ];
  return (
    <Stage step={5} dur={SCENES[5].dur} title="A podium, with a confidence band" blurb="The result: a predicted finishing order for every session, each with its own margin.">
      <div style={{ padding: "44px 90px", height: "100%", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={monoChip("PREDICTED PODIUM · NEXT GRAND PRIX", C.inkDim)} />
        <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 22 }}>
          {podium.map((d, i) => {
            const start = 12 + i * 14;
            const o = interpolate(frame, [start, start + 14], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            const w = interpolate(frame, [start + 6, start + 36], [0, d.p], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
            return (
              <div key={d.code} style={{ opacity: o, display: "flex", alignItems: "center", gap: 16, border: `1px solid ${C.line}`, borderRadius: 12, background: C.canvas, padding: "14px 18px" }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: i === 0 ? C.accent : C.surface3, color: i === 0 ? "#fff" : C.ink, fontFamily: SANS, fontWeight: 700, fontSize: 18, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {d.pos}
                </div>
                <div style={{ fontFamily: MONO, fontSize: 18, fontWeight: 600, color: C.ink, width: 70 }}>{d.code}</div>
                <div style={{ flex: 1, height: 10, borderRadius: 99, background: C.surface3, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${w * 100}%`, background: C.accent, borderRadius: 99 }} />
                </div>
                <div style={{ fontFamily: MONO, fontSize: 15, color: C.inkMuted, width: 54, textAlign: "right" }}>{Math.round(w * 100)}%</div>
              </div>
            );
          })}
        </div>
      </div>
    </Stage>
  );
};

const GradeScene: React.FC = () => {
  const frame = useCurrentFrame();
  const pct = interpolate(frame, [16, 70], [0, 87], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
  const R = 78;
  const Cc = 2 * Math.PI * R;
  return (
    <Stage step={6} dur={SCENES[6].dur} title="It scores its own homework" blurb="After the race, every prediction is graded against reality — round after round.">
      <div style={{ height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <div style={monoChip("MODEL vs REALITY · SEASON ACCURACY", C.inkDim)} />
        <div style={{ position: "relative", width: 220, height: 220, marginTop: 18 }}>
          <svg width="220" height="220" style={{ transform: "rotate(-90deg)" }}>
            <circle cx="110" cy="110" r={R} fill="none" stroke={C.surface3} strokeWidth="12" />
            <circle
              cx="110"
              cy="110"
              r={R}
              fill="none"
              stroke={C.teal}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={Cc}
              strokeDashoffset={Cc * (1 - pct / 100)}
              style={{ filter: `drop-shadow(0 0 10px ${C.teal})` }}
            />
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
            <div style={{ fontFamily: SANS, fontWeight: 700, fontSize: 52, color: C.ink }}>{Math.round(pct)}%</div>
            <div style={{ fontFamily: MONO, fontSize: 11, letterSpacing: 1.5, color: C.inkDim, textTransform: "uppercase" }}>podium-weighted</div>
          </div>
        </div>
      </div>
    </Stage>
  );
};

const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({ frame, fps, config: { damping: 200 } });
  const o = fadeInOut(frame, SCENES[7].dur, 18);
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: o }}>
      <Img src={staticFile("motorsportverse-logo.png")} style={{ width: 460, transform: `scale(${interpolate(s, [0, 1], [0.92, 1])})` }} />
      <div style={{ fontFamily: SANS, fontSize: 30, fontWeight: 700, color: C.ink, marginTop: 26 }}>Every motorsport. One engine.</div>
      <div style={{ fontFamily: MONO, fontSize: 15, letterSpacing: 2, color: C.teal, marginTop: 14 }}>
        roni-altshuler.github.io/motorsportverse
      </div>
    </AbsoluteFill>
  );
};

/* ---------------------------------------------------------------- film */

const SCENE_COMPONENTS: Record<string, React.FC> = {
  intro: IntroScene,
  ingest: IngestScene,
  engine: EngineScene,
  calibrate: CalibrateScene,
  simulate: SimulateScene,
  forecast: ForecastScene,
  grade: GradeScene,
  outro: OutroScene,
};

export const Film: React.FC = () => {
  let from = 0;
  return (
    <AbsoluteFill style={{ background: C.canvas, fontFamily: SANS }}>
      <FilmBackground />
      {SCENES.map((sc) => {
        const Comp = SCENE_COMPONENTS[sc.key];
        const seq = (
          <Sequence key={sc.key} from={from} durationInFrames={sc.dur} name={sc.key}>
            <Comp />
          </Sequence>
        );
        from += sc.dur;
        return seq;
      })}
      {/* film grain / vignette */}
      <AbsoluteFill style={{ boxShadow: "inset 0 0 240px rgba(0,0,0,0.6)", pointerEvents: "none" }} />
    </AbsoluteFill>
  );
};
