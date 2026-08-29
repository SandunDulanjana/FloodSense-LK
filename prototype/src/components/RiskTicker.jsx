import { districts } from "../data/mockData";

const toneVar = {
  LOW: { text: "var(--risk-low)", bg: "var(--risk-low-bg)", border: "#86efac" },
  MEDIUM: { text: "var(--risk-medium)", bg: "var(--risk-medium-bg)", border: "#fde047" },
  HIGH: { text: "var(--risk-high)", bg: "var(--risk-high-bg)", border: "#fca5a5" },
};

export default function RiskTicker() {
  const items = [...districts, ...districts];

  return (
    <div
      style={{
        overflow: "hidden",
        borderBottom: "1px solid var(--border)",
        background: "var(--bg-panel)",
        padding: "8px 0",
        position: "relative",
        display: "flex",
        alignItems: "center",
      }}
    >
      {/* Live Badge Label on the left */}
      <div
        style={{
          padding: "0 14px",
          background: "var(--bg-panel)",
          zIndex: 2,
          display: "flex",
          alignItems: "center",
          gap: 6,
          borderRight: "1px solid var(--border)",
          boxShadow: "4px 0 12px rgba(15, 27, 51, 0.04)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: "#ef4444",
            boxShadow: "0 0 6px #ef4444",
            display: "inline-block",
          }}
        />
        <span
          style={{
            fontSize: 10.5,
            fontWeight: 800,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            color: "var(--text-secondary)",
          }}
        >
          Live Alert
        </span>
      </div>

      {/* Scrolling Ticker Strip */}
      <div
        className="ticker-container"
        style={{
          display: "flex",
          gap: 40,
          whiteSpace: "nowrap",
          animation: "ticker-scroll 150s linear infinite",
          width: "max-content",
          cursor: "default",
        }}
      >
        {items.map((d, i) => {
          const tone = toneVar[d.m4.riskLevel] || toneVar.LOW;
          return (
            <span
              key={`${d.id}-${i}`}
              className="mono"
              style={{
                fontSize: 12.5,
                color: "var(--text-secondary)",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <strong style={{ color: "var(--text-primary)", fontWeight: 700 }}>
                {d.name.toUpperCase()}
              </strong>

              <span
                style={{
                  fontSize: 10.5,
                  fontWeight: 700,
                  padding: "1px 6px",
                  borderRadius: 4,
                  color: tone.text,
                  background: tone.bg,
                  border: `1px solid ${tone.border}`,
                }}
              >
                {d.m4.riskLevel}
              </span>

              <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                flood prob <strong style={{ color: "var(--text-primary)", fontWeight: 600 }}>{Math.round(d.m4.floodProbability * 100)}%</strong> · sldi <strong style={{ color: "var(--text-primary)", fontWeight: 600 }}>{d.m4.sldi}</strong>
              </span>

              <span style={{ color: "var(--border-strong)", margin: "0 4px" }}>•</span>
            </span>
          );
        })}
      </div>

      <style>{`
        @keyframes ticker-scroll {
          from { transform: translateX(0); }
          to { transform: translateX(-50%); }
        }
        .ticker-container:hover {
          animation-play-state: paused !important;
        }
        @media (prefers-reduced-motion: reduce) {
          .ticker-container { animation: none !important; }
        }
      `}</style>
    </div>
  );
}
