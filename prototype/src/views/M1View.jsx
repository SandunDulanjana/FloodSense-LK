import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import DistrictSelector from "../components/DistrictSelector";
import MetricCard from "../components/MetricCard";
import RiskBadge from "../components/RiskBadge";
import { districts, getDistrictById } from "../data/mockData";

const tierToTone = { Low: "low", Medium: "medium", High: "high", Severe: "severe" };

export default function M1View() {
  const [selectedId, setSelectedId] = useState(districts[0].id);
  const district = getDistrictById(selectedId);
  const { m1 } = district;

  const modelData = Object.entries(m1.modelScores).map(([name, r2]) => ({
    name: name === "randomForest" ? "Random forest" : name === "xgboost" ? "XGBoost" : name === "lightgbm" ? "LightGBM" : "Linear",
    r2,
    isBest: name === m1.bestModel,
  }));

  const barData = districts.map((d) => ({ name: d.name, houses: d.m1.housesDamaged }));

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--m1)", background: "var(--m1-bg)", padding: "3px 8px", borderRadius: 6 }}>M1</span>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, margin: 0 }}>Building damage prediction</h1>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
            Regression models trained on DMC records, census, rainfall, and elevation data
          </p>
        </div>
        <DistrictSelector selectedId={selectedId} onChange={setSelectedId} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        <MetricCard label="Predicted houses damaged" value={m1.housesDamaged.toLocaleString()} />
        <MetricCard label="Affected families" value={m1.affectedFamilies.toLocaleString()} />
        <MetricCard label="Sri Lanka flood damage index" value={m1.slfdi} tone={tierToTone[m1.riskTier]} />
        <div className="panel" style={{ padding: "14px 16px" }}>
          <p style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-secondary)", margin: "0 0 10px" }}>
            Risk tier
          </p>
          <RiskBadge tier={m1.riskTier} />
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16 }}>
        <div className="panel" style={{ padding: 18 }}>
          <p className="panel-title">Predicted damage by district</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={barData}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
              <YAxis stroke="var(--text-muted)" fontSize={12} />
              <Tooltip
                contentStyle={{ background: "var(--bg-panel-raised)", border: "1px solid var(--border-strong)", borderRadius: 8 }}
                labelStyle={{ color: "var(--text-primary)" }}
              />
              <Bar dataKey="houses" fill="var(--accent)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel" style={{ padding: 18 }}>
          <p className="panel-title">Model comparison (R²)</p>
          <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
            <tbody>
              {modelData.map((m) => (
                <tr key={m.name} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 0", color: m.isBest ? "var(--text-primary)" : "var(--text-secondary)", fontWeight: m.isBest ? 500 : 400 }}>
                    {m.name}
                  </td>
                  <td className="mono" style={{ padding: "8px 0", textAlign: "right", color: m.isBest ? "var(--accent)" : "var(--text-muted)", fontWeight: m.isBest ? 700 : 400 }}>
                    {m.r2.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 12 }}>
            Best-performing model selected for deployment: <span style={{ color: "var(--text-primary)" }}>{modelData.find((m) => m.isBest)?.name}</span>
          </p>
        </div>
      </div>
    </div>
  );
}
