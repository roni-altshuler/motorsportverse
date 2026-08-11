/**
 * Inline "RaceIQ IMSA" wordmark. Rendered as SVG (not an <img>) so the accent
 * always resolves to the live IMSA-red token in tokens.css — the chevron mark
 * and the "IMSA" line pick up `--accent-f1-red` and its bright small-text
 * variant.
 */
export default function Wordmark({
  className,
  opacity,
}: {
  className?: string;
  opacity?: number;
}) {
  return (
    <svg
      viewBox="0 0 300 80"
      className={className}
      role="img"
      aria-label="RaceIQ IMSA"
      style={opacity != null ? { opacity } : undefined}
    >
      <g transform="translate(4,22)" fill="var(--accent-f1-red)">
        <path d="M0 0 L15.12 0 L25.92 18 L15.12 36 L0 36 L10.8 18 Z" />
        <path d="M14.4 0 L29.52 0 L40.32 18 L29.52 36 L14.4 36 L25.2 18 Z" opacity="0.55" />
      </g>
      <g fontFamily="'Saira Condensed','Arial Narrow',system-ui,sans-serif" fontWeight={700}>
        <text x="58" y="46" fontSize="34" letterSpacing="1.5" fill="#f4f5f7">
          Race
          <tspan fill="var(--accent-f1-red-bright)">IQ</tspan>
        </text>
        <text x="60" y="66" fontSize="15" letterSpacing="6" fill="var(--accent-f1-red-bright)">
          IMSA
        </text>
      </g>
    </svg>
  );
}
