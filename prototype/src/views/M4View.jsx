import { useState } from "react";
import DistrictSelector from "../components/DistrictSelector";
import MetricCard from "../components/MetricCard";
import { getDistrictById } from "../data/mockData";

const factorLabels = {
  populationExposure: "Population exposure",
  infrastructureAccessibility: "Infrastructure accessibility",
  historicalVulnerability: "Historical vulnerability",
};

export default function M4View() {
  const [selectedId, setSelectedId] = useState("colombo");
  const district = getDistrictById(selectedId);
  const { m4 } = district;

  const riskTone = m4.riskLevel === "HIGH" ? "high" : m4.riskLevel === "MEDIUM" ? "medium" : "low";

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--m4)", background: "var(--m4-bg)", padding: "3px 8px", borderRadius: 6 }}>M4</span>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, margin: 0 }}>Flood risk and disaster prioritization</h1>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
            Random forest / XGBoost flood probability, fused into the Sri Lanka Disaster Index
          </p>
        </div>
        <DistrictSelector selectedId={selectedId} onChange={setSelectedId} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 20 }}>
        <MetricCard label="Flood probability" value={Math.round(m4.floodProbability * 100)} unit="%" tone={riskTone} />
        <MetricCard label="Risk level" value={m4.riskLevel} tone={riskTone} />
        <MetricCard label="SLDI composite score" value={m4.sldi} tone={m4.sldi > 80 ? "severe" : riskTone} />
      </div>

      <div className="panel" style={{ padding: 18 }}>
        <p className="panel-title">SLDI factor breakdown</p>
        <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 16px" }}>
          Flood probability, population exposure, infrastructure accessibility and historical vulnerability
          combine into one resource-prioritization score.
        </p>
        {Object.entries(factorLabels).map(([key, label]) => (
          <div key={key} style={{ marginBottom: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
              <span style={{ color: "var(--text-secondary)" }}>{label}</span>
              <span className="mono" style={{ color: "var(--text-primary)" }}>{m4[key]}</span>
            </div>
            <div style={{ height: 7, borderRadius: 4, background: "var(--bg-input)", overflow: "hidden" }}>
              <div style={{ width: `${m4[key]}%`, height: "100%", background: "var(--accent)" }} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
