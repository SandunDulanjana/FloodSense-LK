import { districts } from "../data/mockData";

const toneVar = {
  LOW: "var(--risk-low)",
  MEDIUM: "var(--risk-medium)",
  HIGH: "var(--risk-high)",
};

export default function RiskTicker() {
  const items = [...districts, ...districts];

  return (
    <div
      style={{
        overflow: "hidden",
        borderBottom: "1px solid var(--border)",
        background: "var(--bg-panel)",
        padding: "9px 0",
      }}
    >
      <div
        style={{
          display: "flex",
          gap: 36,
          whiteSpace: "nowrap",
          animation: "ticker-scroll 28s linear infinite",
          width: "max-content",
        }}
      >
        {items.map((d, i) => (
          <span key={`${d.id}-${i}`} className="mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
            {d.name.toUpperCase()}{" "}
            <span style={{ color: toneVar[d.m4.riskLevel] || "var(--text-primary)", fontWeight: 700 }}>
              {d.m4.riskLevel}
            </span>{" "}
            <span style={{ color: "var(--text-muted)" }}>
              flood prob {Math.round(d.m4.floodProbability * 100)}% · sldi {d.m4.sldi}
            </span>
          </span>
        ))}
      </div>
      <style>{`
        @keyframes ticker-scroll {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
        @media (prefers-reduced-motion: reduce) {
          div[style*="ticker-scroll"] { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
