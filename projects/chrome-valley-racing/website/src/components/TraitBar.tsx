export default function TraitBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  return (
    <div style={{ "--racer-color": color } as React.CSSProperties}>
      <div className="mb-1 flex items-baseline justify-between">
        <span className="mono-label">{label}</span>
        <span className="mono-label font-tabular text-[color:var(--body-strong)]">{value}</span>
      </div>
      <div className="trait-bar" role="meter" aria-label={label} aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
        <div className="trait-bar-fill" style={{ width: `${value}%` }} />
      </div>
    </div>
  );
}
