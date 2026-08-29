import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import RiskBadge from "../components/RiskBadge";
import { districts } from "../data/mockData";

export default function OverviewView() {
  const [searchQuery, setSearchQuery] = useState("");
  const [riskFilter, setRiskFilter] = useState("ALL"); // "ALL" | "HIGH" | "MEDIUM" | "LOW"

  const totalHousesDamaged = useMemo(() => districts.reduce((s, d) => s + d.m1.housesDamaged, 0), []);
  const totalRoadsFlooded = useMemo(() => Math.round(districts.reduce((s, d) => s + d.m2.floodedKm, 0)), []);
  const avgCropDamage = useMemo(() => Math.round(districts.reduce((s, d) => s + d.m3.damagePct, 0) / districts.length), []);
  const highRiskCount = useMemo(() => districts.filter((d) => d.m4.riskLevel === "HIGH").length, []);

  const moduleSummaries = [
    {
      key: "M1",
      label: "Building damage",
      sublabel: "Houses Damaged",
      color: "var(--m1)",
      bg: "var(--m1-bg)",
      border: "#93c5fd",
      to: "/m1",
      value: totalHousesDamaged.toLocaleString(),
      unit: "houses",
      icon: "🏢",
      desc: "Census & rainfall regression models",
    },
    {
      key: "M2",
      label: "Roads flooded",
      sublabel: "Inundated Network",
      color: "var(--m2)",
      bg: "var(--m2-bg)",
      border: "#5eead4",
      to: "/m2",
      value: totalRoadsFlooded.toLocaleString(),
      unit: "km",
      icon: "🛣️",
      desc: "U-Net Sentinel-1 SAR classification",
    },
    {
      key: "M3",
      label: "Crop damage avg",
      sublabel: "National Average",
      color: "var(--m3)",
      bg: "var(--m3-bg)",
      border: "#86efac",
      to: "/m3",
      value: avgCropDamage,
      unit: "%",
      icon: "🌾",
      desc: "Sentinel-2 NDVI difference & Random Forest",
    },
    {
      key: "M4",
      label: "Districts at high risk",
      sublabel: "Priority Alert",
      color: "var(--m4)",
      bg: "var(--m4-bg)",
      border: "#fda4af",
      to: "/m4",
      value: highRiskCount,
      unit: `of ${districts.length}`,
      icon: "⚠️",
      desc: "Sri Lanka Disaster Index (SLDI) composite",
    },
  ];

  const ranked = useMemo(() => {
    return [...districts].sort((a, b) => b.m4.sldi - a.m4.sldi);
  }, []);

  const filteredDistricts = useMemo(() => {
    return ranked.filter((d) => {
      const matchesSearch =
        d.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (d.province && d.province.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchesRisk = riskFilter === "ALL" || d.m4.riskLevel === riskFilter;
      return matchesSearch && matchesRisk;
    });
  }, [ranked, searchQuery, riskFilter]);

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto" }}>
      {/* Hero Alert & Header Banner */}
      <div
        className="panel"
        style={{
          padding: "20px 24px",
          marginBottom: 22,
          background: "linear-gradient(135deg, rgba(255,255,255,0.92) 0%, rgba(240,246,255,0.85) 100%)",
          border: "1px solid rgba(191, 219, 254, 0.8)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 3,
            background: "linear-gradient(90deg, #2563eb, #0d9488, #16a34a, #e11d48)",
          }}
        />

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 14 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "4px 10px",
                  borderRadius: 999,
                  background: "#fee2e2",
                  color: "#991b1b",
                  border: "1px solid #fca5a5",
                  fontSize: 11.5,
                  fontWeight: 700,
                }}
              >
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#ef4444", boxShadow: "0 0 6px #ef4444" }} />
                Active Monsoon Flood Emergency
              </span>
              <span style={{ fontSize: 12, color: "var(--text-muted)" }}>
                • National Multi-Hazard Ops Assessment
              </span>
            </div>

            <h1 style={{ fontFamily: "var(--font-display)", fontSize: 24, fontWeight: 800, margin: 0, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
              Disaster Operations Overview
            </h1>
            <p style={{ fontSize: 13.5, color: "var(--text-secondary)", margin: "4px 0 0" }}>
              Fused intelligence across all 4 satellite and machine learning modules for <strong>25 Sri Lankan administrative districts</strong>.
            </p>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div style={{ background: "rgba(255, 255, 255, 0.9)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 14px", textAlign: "right" }}>
              <p style={{ fontSize: 10.5, color: "var(--text-muted)", textTransform: "uppercase", margin: 0, fontWeight: 600 }}>National SLDI Status</p>
              <p className="mono" style={{ fontSize: 16, fontWeight: 800, color: "#dc2626", margin: 0 }}>
                Severe Alert
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Module Overview Cards Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        {moduleSummaries.map((m) => (
          <Link
            key={m.key}
            to={m.to}
            className="panel panel-interactive"
            style={{
              padding: "18px 20px",
              textDecoration: "none",
              color: "inherit",
              display: "flex",
              flexDirection: "column",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                right: 0,
                height: 3,
                background: m.color,
              }}
            />

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 18 }}>{m.icon}</span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    letterSpacing: "0.04em",
                    color: m.color,
                    background: m.bg,
                    padding: "3px 8px",
                    borderRadius: 6,
                    border: `1px solid ${m.border}`,
                  }}
                >
                  {m.key}
                </span>
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, color: m.color, display: "flex", alignItems: "center", gap: 4 }}>
                Explore →
              </span>
            </div>

            <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "0 0 2px", fontWeight: 600 }}>{m.label}</p>
            <p className="mono" style={{ fontSize: 26, fontWeight: 800, margin: "2px 0 6px", color: "var(--text-primary)" }}>
              {m.value} <span style={{ fontSize: 13, fontFamily: "var(--font-sans)", color: "var(--text-muted)", fontWeight: 500 }}>{m.unit}</span>
            </p>

            <p style={{ fontSize: 11, color: "var(--text-muted)", margin: "auto 0 0", borderTop: "1px solid var(--border)", paddingTop: 8 }}>
              {m.desc}
            </p>
          </Link>
        ))}
      </div>

      {/* District Priority Ranking Section with Search & Filter */}
      <div className="panel" style={{ padding: "20px 22px", marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <p className="panel-title" style={{ margin: 0 }}>
                District Disaster Priority Ranking (SLDI)
              </p>
              <span
                style={{
                  fontSize: 11,
                  padding: "2px 8px",
                  borderRadius: 12,
                  background: "var(--brand-dim)",
                  color: "var(--brand)",
                  fontWeight: 700,
                }}
              >
                {filteredDistricts.length} Districts
              </span>
            </div>
            <p style={{ fontSize: 12.5, color: "var(--text-secondary)", margin: "3px 0 0" }}>
              Composite score ranking based on population exposure, road cutoff, and crop devastation
            </p>
          </div>

          {/* Search Input & Risk Filters */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            {/* Search Box */}
            <div style={{ position: "relative" }}>
              <input
                type="text"
                placeholder="Search district or province..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  padding: "7px 12px 7px 30px",
                  fontSize: 13,
                  border: "1px solid var(--border-strong)",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--bg-input)",
                  color: "var(--text-primary)",
                  minWidth: 220,
                }}
              />
              <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", fontSize: 12, color: "var(--text-muted)" }}>
                🔍
              </span>
            </div>

            {/* Risk Filter Tabs */}
            <div style={{ display: "flex", background: "var(--bg-input)", border: "1px solid var(--border)", borderRadius: 8, padding: 2 }}>
              {[
                { id: "ALL", label: "All (25)" },
                { id: "HIGH", label: "🔴 High (10)" },
                { id: "MEDIUM", label: "🟡 Medium (10)" },
                { id: "LOW", label: "🟢 Low (5)" },
              ].map((tab) => {
                const active = riskFilter === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setRiskFilter(tab.id)}
                    style={{
                      border: "none",
                      background: active ? "var(--brand)" : "transparent",
                      color: active ? "#ffffff" : "var(--text-secondary)",
                      fontWeight: active ? 700 : 500,
                      fontSize: 12,
                      padding: "4px 10px",
                      borderRadius: 6,
                      cursor: "pointer",
                      transition: "all 0.15s ease",
                    }}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Priority Ranking Table */}
        <div style={{ overflowX: "auto", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-panel-raised)" }}>
                {["Rank", "District & Province", "SLDI Score", "Flood Risk", "Houses Damaged", "Roads Passable", "Crop Damage", "Quick Modules"].map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: "left",
                      padding: "12px 16px",
                      fontSize: 11,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      color: "var(--text-secondary)",
                      fontWeight: 700,
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredDistricts.map((d, i) => {
                const sldiTone = d.m4.sldi > 80 ? "#dc2626" : d.m4.sldi > 50 ? "#d97706" : "#16a34a";
                return (
                  <tr
                    key={d.id}
                    style={{
                      borderBottom: "1px solid var(--border)",
                      transition: "background 0.12s ease",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-panel-raised)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <td className="mono" style={{ padding: "12px 16px", color: "var(--text-muted)", fontWeight: 600 }}>
                      #{i + 1}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <strong style={{ color: "var(--text-primary)", fontWeight: 700 }}>{d.name}</strong>{" "}
                      <span style={{ fontSize: 12, color: "var(--text-muted)" }}>({d.province})</span>
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span
                        className="mono"
                        style={{
                          fontSize: 13,
                          fontWeight: 800,
                          padding: "2px 8px",
                          borderRadius: 6,
                          background: d.m4.sldi > 80 ? "#fee2e2" : d.m4.sldi > 50 ? "#fef3c7" : "#dcfce7",
                          color: sldiTone,
                          border: `1px solid ${d.m4.sldi > 80 ? "#fca5a5" : d.m4.sldi > 50 ? "#fde047" : "#86efac"}`,
                        }}
                      >
                        {d.m4.sldi}
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <RiskBadge tier={d.m4.riskLevel === "HIGH" ? "High" : d.m4.riskLevel === "MEDIUM" ? "Medium" : "Low"} />
                    </td>
                    <td className="mono" style={{ padding: "12px 16px", color: "var(--text-secondary)" }}>
                      {d.m1.housesDamaged.toLocaleString()}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ width: 50, height: 6, borderRadius: 3, background: "#fee2e2", overflow: "hidden" }}>
                          <div style={{ width: `${d.m2.passablePct}%`, height: "100%", background: "#16a34a" }} />
                        </div>
                        <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: d.m2.passablePct < 65 ? "#dc2626" : "inherit" }}>
                          {d.m2.passablePct}%
                        </span>
                      </div>
                    </td>
                    <td className="mono" style={{ padding: "12px 16px", fontWeight: 600, color: d.m3.damagePct > 35 ? "#dc2626" : d.m3.damagePct >= 20 ? "#16a34a" : "#ca8a04" }}>
                      {d.m3.damagePct}%
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <div style={{ display: "flex", gap: 5 }}>
                        <Link
                          to="/m2"
                          title="View Road GIS Map"
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            textDecoration: "none",
                            padding: "3px 8px",
                            borderRadius: 6,
                            background: "var(--m2-bg)",
                            color: "var(--m2)",
                            border: "1px solid var(--m2-border)",
                          }}
                        >
                          M2 Roads
                        </Link>
                        <Link
                          to="/m3"
                          title="View Agricultural Impact"
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            textDecoration: "none",
                            padding: "3px 8px",
                            borderRadius: 6,
                            background: "var(--m3-bg)",
                            color: "var(--m3)",
                            border: "1px solid var(--m3-border)",
                          }}
                        >
                          M3 Crops
                        </Link>
                        <Link
                          to="/m4"
                          title="View SLDI Prioritization"
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            textDecoration: "none",
                            padding: "3px 8px",
                            borderRadius: 6,
                            background: "var(--m4-bg)",
                            color: "var(--m4)",
                            border: "1px solid var(--m4-border)",
                          }}
                        >
                          M4 Risk
                        </Link>
                      </div>
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
