export default function MetricCard({ label, value, unit, tone, accent }) {
  const valueColor = tone ? `var(--risk-${tone})` : "var(--text-primary)";
  const toneBg = tone ? `var(--risk-${tone}-bg)` : "transparent";

  return (
    <div
      className="panel panel-interactive"
      style={{
        padding: "16px 18px",
        borderLeft: accent ? `4px solid ${accent}` : undefined,
        position: "relative",
        overflow: "hidden",
      }}
    >
      <p
        style={{
          fontSize: 11,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          color: "var(--text-secondary)",
          fontWeight: 700,
          margin: "0 0 8px",
        }}
      >
        {label}
      </p>
      <p
        className="mono"
        style={{
          fontSize: 26,
          fontWeight: 800,
          margin: 0,
          color: valueColor,
          lineHeight: 1.1,
          letterSpacing: "-0.02em",
        }}
      >
        {value}
        {unit && (
          <span style={{ fontSize: 13, color: "var(--text-muted)", marginLeft: 4, fontFamily: "var(--font-sans)", fontWeight: 500 }}>
            {unit}
          </span>
        )}
      </p>
    </div>
  );
}
