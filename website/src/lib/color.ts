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
