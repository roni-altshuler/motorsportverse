import { parseReplayCapture, type ReplayCapture } from "./replayStream";

/** Original fictional oval: not a venue, circuit survey or historical race. */
export function fictionalCapture(): ReplayCapture {
  const points = Array.from({ length: 81 }, (_, i) => {
    const angle = (i / 80) * Math.PI * 2;
    return [Math.cos(angle) * 320, Math.sin(angle) * 180];
  });
  const identities = [
    ["D01", "Alex Rivera"],
    ["D02", "Jamie Brooks"],
    ["D03", "Morgan Lee"],
  ];
  const lines = Array.from({ length: 24 }, (_, i) =>
    JSON.stringify({
      frame_index: i,
      frame: {
        t: i * 2,
        drivers: Object.fromEntries(
          identities.map(([code, name], driver) => {
            const angle = (i / 24) * Math.PI * 2 - driver * 0.6;
            return [code, { name, x: Math.cos(angle) * 320, y: Math.sin(angle) * 180 }];
          }),
        ),
      },
      driver_colors: { D01: "#FF8866", D02: "#69CCCC", D03: "#DACD69" },
      ...(i === 0
        ? {
            track_geometry: {
              x: points.map((p) => p[0]),
              y: points.map((p) => p[1]),
              rotation_deg: 15,
            },
          }
        : {}),
    }),
  );
  return {
    ...parseReplayCapture(lines.join("\n"), "Fictional circuit demonstration"),
    source: "fictional",
  };
}
