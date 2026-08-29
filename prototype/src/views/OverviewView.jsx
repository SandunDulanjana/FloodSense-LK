import { Link } from "react-router-dom";
import RiskBadge from "../components/RiskBadge";
import { districts } from "../data/mockData";

const moduleSummaries = [
  { key: "M1", label: "Building damage", color: "var(--m1)", bg: "var(--m1-bg)", to: "/m1",
    value: districts.reduce((s, d) => s + d.m1.housesDamaged, 0).toLocaleString(), unit: "houses" },
  { key: "M2", label: "Roads flooded", color: "var(--m2)", bg: "var(--m2-bg)", to: "/m2",
    value: Math.round(districts.reduce((s, d) => s + d.m2.floodedKm, 0)), unit: "km" },
  { key: "M3", label: "Crop damage avg", color: "var(--m3)", bg: "var(--m3-bg)", to: "/m3",
    value: Math.round(districts.reduce((s, d) => s + d.m3.damagePct, 0) / districts.length), unit: "%" },
  { key: "M4", label: "Districts at high risk", color: "var(--m4)", bg: "var(--m4-bg)", to: "/m4",
    value: districts.filter((d) => d.m4.riskLevel === "HIGH").length, unit: `of ${districts.length}` },
];

export default function OverviewView() {
  const ranked = [...districts].sort((a, b) => b.m4.sldi - a.m4.sldi);

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 700, margin: 0 }}>
          Disaster overview
        </h1>
        <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: "4px 0 0" }}>
          Live status across all four assessment modules, fused into the Sri Lanka Disaster Index
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 24 }}>
        {moduleSummaries.map((m) => (
          <Link
            key={m.key}
            to={m.to}
            className="panel"
            style={{ padding: "16px 18px", textDecoration: "none", color: "inherit", display: "block" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: "0.04em",
                  color: m.color,
                  background: m.bg,
                  padding: "3px 8px",
                  borderRadius: 6,
                }}
              >
                {m.key}
              </span>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>View →</span>
            </div>
            <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "0 0 6px" }}>{m.label}</p>
            <p className="mono" style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
              {m.value} <span style={{ fontSize: 12, fontFamily: "var(--font-sans)", color: "var(--text-muted)" }}>{m.unit}</span>
            </p>
          </Link>
        ))}
      </div>

      <p className="panel-title" style={{ marginBottom: 10 }}>District priority ranking</p>
      <div className="panel" style={{ padding: 0, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-panel-raised)" }}>
              {["Rank", "District", "SLDI", "Flood risk", "Houses damaged", "Roads passable", "Crop damage", ""].map((h) => (
                <th
                  key={h}
                  style={{
                    textAlign: "left",
                    padding: "12px 16px",
                    fontSize: 11,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    color: "var(--text-secondary)",
                    fontWeight: 600,
                  }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ranked.map((d, i) => (
              <tr key={d.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td className="mono" style={{ padding: "12px 16px", color: "var(--text-muted)" }}>{i + 1}</td>
                <td style={{ padding: "12px 16px", fontWeight: 500 }}>{d.name}</td>
                <td className="mono" style={{ padding: "12px 16px", color: d.m4.sldi > 80 ? "var(--risk-severe)" : "var(--text-primary)", fontWeight: 700 }}>
                  {d.m4.sldi}
                </td>
                <td style={{ padding: "12px 16px" }}>
                  <RiskBadge tier={d.m4.riskLevel === "HIGH" ? "High" : d.m4.riskLevel === "MEDIUM" ? "Medium" : "Low"} />
                </td>
                <td className="mono" style={{ padding: "12px 16px", color: "var(--text-secondary)" }}>{d.m1.housesDamaged.toLocaleString()}</td>
                <td className="mono" style={{ padding: "12px 16px", color: "var(--text-secondary)" }}>{d.m2.passablePct}%</td>
                <td className="mono" style={{ padding: "12px 16px", color: "var(--text-secondary)" }}>{d.m3.damagePct}%</td>
                <td style={{ padding: "12px 16px" }}>
                  <Link
                    to="/m4"
                    style={{
                      fontSize: 12,
                      fontWeight: 500,
                      textDecoration: "none",
                      border: "1px solid var(--border-strong)",
                      padding: "5px 12px",
                      borderRadius: 999,
                      color: "var(--text-primary)",
                    }}
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 16 }}>
        This view fuses the mock outputs of all four modules. In the live system, this table refreshes from
        the M1–M4 model APIs and the SLDI is recomputed as new rainfall and river-level data arrives.
      </p>
    </div>
  );
}
