// Accent → readable text color on the dark canvas.
//
// Registry accents are brand colors, not UI colors — some (IMSA navy,
// Le Mans green) are too dark to read as text on the canvas. Mirror the
// tokens.css pattern (--accent #e7102f → --accent-text #ff5168) by mixing
// toward white for any text/icon rendered in a project's accent.
// fs-free — safe in client components.

export function accentText(accent: string): string {
  return `color-mix(in srgb, ${accent} 70%, white)`;
}

/** Registry hex accents retain their hue; solid buttons choose readable ink. */
export function accentInk(accent: string): string {
  const match = /^#([\da-f]{3}|[\da-f]{6})$/i.exec(accent);
  if (!match) return "var(--accent-ink)";
  const hex =
    match[1].length === 3
      ? [...match[1]].map((digit) => digit + digit).join("")
      : match[1];
  const luminance = (channels: number[]) =>
    channels.reduce((sum, value, i) => {
      const srgb = value / 255;
      const linear =
        srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
      return sum + linear * [0.2126, 0.7152, 0.0722][i];
    }, 0);
  const background = luminance(
    [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16)),
  );
  const dark = luminance([6, 9, 16]);
  const darkContrast = (background + 0.05) / (dark + 0.05);
  const whiteContrast = 1.05 / (background + 0.05);
  return darkContrast > whiteContrast ? "#060910" : "#ffffff";
}
