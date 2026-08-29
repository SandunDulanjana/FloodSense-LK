const TONES = {
  Low: { fg: "var(--risk-low)", bg: "var(--risk-low-bg)" },
  Medium: { fg: "var(--risk-medium)", bg: "var(--risk-medium-bg)" },
  High: { fg: "var(--risk-high)", bg: "var(--risk-high-bg)" },
  Severe: { fg: "var(--risk-severe)", bg: "var(--risk-severe-bg)" },
};

export default function RiskBadge({ tier }) {
  const tone = TONES[tier] || TONES.Medium;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "3px 10px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 500,
        color: tone.fg,
        background: tone.bg,
      }}
    >
      {tier}
    </span>
  );
}
