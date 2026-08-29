export default function MetricCard({ label, value, unit, tone, accent }) {
  const valueColor = tone ? `var(--risk-${tone})` : "var(--text-primary)";
  return (
    <div
      className="panel"
      style={{
        padding: "16px 18px",
        borderLeft: accent ? `3px solid ${accent}` : undefined,
      }}
    >
      <p
        style={{
          fontSize: 11,
          letterSpacing: "0.04em",
          textTransform: "uppercase",
          color: "var(--text-secondary)",
          fontWeight: 600,
          margin: "0 0 8px",
        }}
      >
        {label}
      </p>
      <p
        className="mono"
        style={{
          fontSize: 26,
          fontWeight: 700,
          margin: 0,
          color: valueColor,
          lineHeight: 1.1,
        }}
      >
        {value}
        {unit && (
          <span style={{ fontSize: 13, color: "var(--text-secondary)", marginLeft: 4, fontFamily: "var(--font-sans)" }}>
            {unit}
          </span>
        )}
      </p>
    </div>
  );
}
