import { useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import DistrictSelector from "../components/DistrictSelector";
import MetricCard from "../components/MetricCard";
import RiskBadge from "../components/RiskBadge";
import { getDistrictById } from "../data/mockData";

const CROP_COLORS = {
  paddy: "#2dd4bf",
  tea: "#7f9cf5",
  vegetables: "#f2a63c",
  other: "#5b6580",
};

export default function M3View() {
  const [selectedId, setSelectedId] = useState("colombo");
  const district = getDistrictById(selectedId);
  const { m3 } = district;

  const pieData = Object.entries(m3.cropBreakdown)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name: name[0].toUpperCase() + name.slice(1), value, key: name }));

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--m3)", background: "var(--m3-bg)", padding: "3px 8px", borderRadius: 6 }}>M3</span>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, margin: 0 }}>Agricultural and livelihood impact</h1>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
            Sentinel-2 NDVI difference and Random Forest crop classification
          </p>
        </div>
        <DistrictSelector selectedId={selectedId} onChange={setSelectedId} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        <MetricCard label="Crop damage" value={m3.damagePct} unit="%" tone={m3.damagePct > 45 ? "high" : "medium"} />
        <MetricCard label="Affected farmers" value={m3.affectedFarmers.toLocaleString()} />
        <div className="panel" style={{ padding: "14px 16px" }}>
          <p style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-secondary)", margin: "0 0 10px" }}>
            Livelihood impact
          </p>
          <RiskBadge tier={m3.livelihoodImpact} />
        </div>
        <MetricCard label="Crop zones tracked" value={pieData.length} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.3fr", gap: 16 }}>
        <div className="panel" style={{ padding: 18 }}>
          <p className="panel-title">Crop type composition</p>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80} paddingAngle={2}>
                {pieData.map((entry) => (
                  <Cell key={entry.key} fill={CROP_COLORS[entry.key]} stroke="var(--bg-panel)" />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "var(--bg-panel-raised)", border: "1px solid var(--border-strong)", borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="panel" style={{ padding: 18 }}>
          <p className="panel-title">Damage detection method</p>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
            NDVI is computed before and after the flood event for each classified crop zone. A drop in NDVI
            beyond a calibrated threshold flags vegetation loss. Damage percentage is combined with
            agricultural population density to produce the district-level livelihood impact score shown above.
          </p>
          <div style={{ marginTop: 16, height: 8, borderRadius: 4, background: "var(--bg-input)", overflow: "hidden" }}>
            <div
              style={{
                width: `${m3.damagePct}%`,
                height: "100%",
                background: m3.damagePct > 45 ? "var(--risk-high)" : "var(--risk-medium)",
              }}
            />
          </div>
          <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
            {m3.damagePct}% of tracked cropland showing flood-induced vegetation loss
          </p>
        </div>
      </div>
    </div>
  );
}
