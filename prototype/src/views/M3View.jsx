import { useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import DistrictSelector from "../components/DistrictSelector";
import MetricCard from "../components/MetricCard";
import SriLankaMap from "../components/SriLankaMap";
import { districts, getDistrictById, getDamageTier, getDamageColor, DAMAGE_COLORS } from "../data/mockData";

const CROP_COLORS = {
  paddy: "#2dd4bf",
  tea: "#7f9cf5",
  vegetables: "#f2a63c",
  other: "#5b6580",
};

export default function M3View() {
  const [selectedId, setSelectedId] = useState("colombo");
  const district = getDistrictById(selectedId) || districts[0];
  const { m3 } = district;

  const damageTier = getDamageTier(m3.damagePct);
  const damageColor = getDamageColor(damageTier);

  const pieData = Object.entries(m3.cropBreakdown)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name: name[0].toUpperCase() + name.slice(1), value, key: name }));

  // Sort districts by damage descending for summary ranking
  const sortedDistricts = [...districts].sort((a, b) => b.m3.damagePct - a.m3.damagePct);

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto" }}>
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "var(--m3)",
                background: "var(--m3-bg)",
                padding: "3px 8px",
                borderRadius: 6,
              }}
            >
              M3
            </span>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 700, margin: 0 }}>
              Agricultural and livelihood impact
            </h1>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
            Sentinel-2 NDVI difference and Random Forest crop classification with interactive Sri Lanka GIS map
          </p>
        </div>
        <DistrictSelector selectedId={selectedId} onChange={setSelectedId} />
      </div>

      {/* Top Metric Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        <MetricCard
          label="Crop damage"
          value={m3.damagePct}
          unit="%"
          tone={damageTier === "High" ? "high" : damageTier === "Medium" ? "medium" : "low"}
        />
        <MetricCard label="Affected farmers" value={m3.affectedFarmers.toLocaleString()} />
        <div className="panel" style={{ padding: "14px 16px" }}>
          <p style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-secondary)", margin: "0 0 8px" }}>
            Damage Level
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                padding: "4px 12px",
                borderRadius: 999,
                fontSize: 12.5,
                fontWeight: 700,
                color: damageColor.badgeText,
                background: damageColor.badgeBg,
                border: `1px solid ${damageColor.border}`,
              }}
            >
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: damageColor.fill,
                  boxShadow: `0 0 6px ${damageColor.fill}`,
                }}
              />
              {damageTier} Damage
            </span>
          </div>
        </div>
        <MetricCard label="Crop zones tracked" value={pieData.length} />
      </div>

      {/* Main Grid: Interactive Map (Left) + Analysis & Crop Panels (Right) */}
      <div style={{ display: "grid", gridTemplateColumns: "1.25fr 1fr", gap: 18, marginBottom: 20 }}>
        {/* Interactive Sri Lanka Map */}
        <SriLankaMap selectedId={selectedId} onSelectDistrict={setSelectedId} />

        {/* Right Details Column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Selected District Snapshot Card */}
          <div
            className="panel"
            style={{
              padding: "16px 18px",
              background: "linear-gradient(135deg, var(--bg-panel) 0%, var(--bg-panel-raised) 100%)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div>
                <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
                  Selected District Details
                </span>
                <h2 style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 700, margin: "2px 0 0" }}>
                  {district.name}{" "}
                  <span style={{ fontSize: 13, fontWeight: 400, color: "var(--text-secondary)" }}>
                    ({district.province} Province)
                  </span>
                </h2>
              </div>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "4px 10px",
                  borderRadius: 6,
                  color: damageColor.badgeText,
                  background: damageColor.badgeBg,
                  border: `1px solid ${damageColor.border}`,
                }}
              >
                {damageTier} Severity
              </span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10, marginTop: 12 }}>
              <div style={{ background: "var(--bg-panel)", padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)" }}>
                <p style={{ fontSize: 11, color: "var(--text-secondary)", margin: "0 0 4px" }}>Crop Damage</p>
                <p className="mono" style={{ fontSize: 18, fontWeight: 700, margin: 0, color: damageColor.text }}>
                  {m3.damagePct}%
                </p>
              </div>
              <div style={{ background: "var(--bg-panel)", padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)" }}>
                <p style={{ fontSize: 11, color: "var(--text-secondary)", margin: "0 0 4px" }}>Affected Farmers</p>
                <p className="mono" style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>
                  {m3.affectedFarmers.toLocaleString()}
                </p>
              </div>
              <div style={{ background: "var(--bg-panel)", padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border)" }}>
                <p style={{ fontSize: 11, color: "var(--text-secondary)", margin: "0 0 4px" }}>Livelihood Impact</p>
                <p style={{ fontSize: 14, fontWeight: 700, margin: "2px 0 0", color: damageColor.text }}>
                  {m3.livelihoodImpact}
                </p>
              </div>
            </div>
          </div>

          {/* Crop Composition Donut Chart */}
          <div className="panel" style={{ padding: 18, flex: 1 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <p className="panel-title" style={{ margin: 0 }}>
                Crop type composition — {district.name}
              </p>
              <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Hectares %</span>
            </div>

            <ResponsiveContainer width="100%" height={210}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={78} paddingAngle={3}>
                  {pieData.map((entry) => (
                    <Cell key={entry.key} fill={CROP_COLORS[entry.key]} stroke="var(--bg-panel)" strokeWidth={2} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-panel-raised)",
                    border: "1px solid var(--border-strong)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(val) => [`${val}%`, "Share"]}
                />
                <Legend wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Damage Detection Method Panel */}
          <div className="panel" style={{ padding: 18 }}>
            <p className="panel-title" style={{ margin: "0 0 8px" }}>
              NDVI Damage Detection Analysis
            </p>
            <p style={{ fontSize: 12.5, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>
              NDVI is computed before and after the flood event for each classified crop zone. A drop in NDVI
              beyond calibrated thresholds flags vegetation loss for <strong>{district.name}</strong>.
            </p>

            <div style={{ marginTop: 14, height: 10, borderRadius: 6, background: "var(--bg-input)", border: "1px solid var(--border)", overflow: "hidden" }}>
              <div
                style={{
                  width: `${m3.damagePct}%`,
                  height: "100%",
                  background: damageColor.fill,
                  transition: "width 0.4s ease-out, background 0.4s",
                }}
              />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--text-muted)", marginTop: 6 }}>
              <span>{m3.damagePct}% flood-induced vegetation loss</span>
              <span style={{ fontWeight: 600, color: damageColor.text }}>{damageTier} Damage Zone</span>
            </div>
          </div>
        </div>
      </div>

      {/* Sri Lanka All-Districts Agricultural Damage Overview Table */}
      <div className="panel" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div>
            <p className="panel-title" style={{ margin: 0 }}>
              National Agricultural Damage Ranking (All 25 Districts)
            </p>
            <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "3px 0 0" }}>
              Ranked by flood-induced crop loss percentage. Click any row to view on map.
            </p>
          </div>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-panel-raised)" }}>
                {["Rank", "District", "Province", "Crop Damage", "Severity Level", "Affected Farmers", "Primary Crop", "Action"].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: "left",
                      padding: "10px 14px",
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
              {sortedDistricts.map((d, i) => {
                const tier = getDamageTier(d.m3.damagePct);
                const col = getDamageColor(tier);
                const isCurrent = d.id === selectedId;

                // Find primary crop
                const primaryCropEntry = Object.entries(d.m3.cropBreakdown).sort((a, b) => b[1] - a[1])[0];
                const primaryCrop = primaryCropEntry ? `${primaryCropEntry[0][0].toUpperCase() + primaryCropEntry[0].slice(1)} (${primaryCropEntry[1]}%)` : "—";

                return (
                  <tr
                    key={d.id}
                    onClick={() => setSelectedId(d.id)}
                    style={{
                      borderBottom: "1px solid var(--border)",
                      background: isCurrent ? "var(--brand-dim)" : "transparent",
                      cursor: "pointer",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={(e) => {
                      if (!isCurrent) e.currentTarget.style.background = "var(--bg-panel-raised)";
                    }}
                    onMouseLeave={(e) => {
                      if (!isCurrent) e.currentTarget.style.background = "transparent";
                    }}
                  >
                    <td className="mono" style={{ padding: "10px 14px", color: "var(--text-muted)" }}>
                      {i + 1}
                    </td>
                    <td style={{ padding: "10px 14px", fontWeight: isCurrent ? 700 : 500, color: isCurrent ? "var(--brand)" : "inherit" }}>
                      {d.name} {isCurrent && <span style={{ fontSize: 11, marginLeft: 4 }}>📍</span>}
                    </td>
                    <td style={{ padding: "10px 14px", color: "var(--text-secondary)" }}>{d.province}</td>
                    <td className="mono" style={{ padding: "10px 14px", fontWeight: 700, color: col.text }}>
                      {d.m3.damagePct}%
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 5,
                          padding: "2px 8px",
                          borderRadius: 999,
                          fontSize: 11.5,
                          fontWeight: 600,
                          color: col.badgeText,
                          background: col.badgeBg,
                        }}
                      >
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: col.fill }} />
                        {tier}
                      </span>
                    </td>
                    <td className="mono" style={{ padding: "10px 14px", color: "var(--text-secondary)" }}>
                      {d.m3.affectedFarmers.toLocaleString()}
                    </td>
                    <td style={{ padding: "10px 14px", color: "var(--text-secondary)" }}>{primaryCrop}</td>
                    <td style={{ padding: "10px 14px" }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedId(d.id);
                        }}
                        style={{
                          fontSize: 11.5,
                          fontWeight: 600,
                          border: isCurrent ? "1px solid var(--brand)" : "1px solid var(--border-strong)",
                          background: isCurrent ? "var(--brand)" : "var(--bg-panel)",
                          color: isCurrent ? "#ffffff" : "var(--text-primary)",
                          padding: "4px 10px",
                          borderRadius: 6,
                          cursor: "pointer",
                        }}
                      >
                        {isCurrent ? "Active" : "Select"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
