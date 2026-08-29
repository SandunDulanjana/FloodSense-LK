import { useState } from "react";
import DistrictSelector from "../components/DistrictSelector";
import MetricCard from "../components/MetricCard";
import SriLankaRoadMap from "../components/SriLankaRoadMap";
import { districts, getDistrictById } from "../data/mockData";
import { districtRoadNetworks } from "../data/sriLankaRoadNetworks";

export default function M2View() {
  const [selectedId, setSelectedId] = useState("colombo");
  const [selectedRoadId, setSelectedRoadId] = useState(null);

  const district = getDistrictById(selectedId) || districts[0];
  const { m2 } = district;

  const roads = districtRoadNetworks[selectedId] || [];
  const floodedRoads = roads.filter((r) => r.status === "flooded");
  const passableRoads = roads.filter((r) => r.status === "passable");

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
                color: "var(--m2)",
                background: "var(--m2-bg)",
                padding: "3px 8px",
                borderRadius: 6,
              }}
            >
              M2
            </span>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: 20, fontWeight: 700, margin: 0 }}>
              Road accessibility classification
            </h1>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
            U-Net fine-tuned on Sentinel-1 SAR change detection with interactive road network GIS overlay
          </p>
        </div>
        <DistrictSelector selectedId={selectedId} onChange={setSelectedId} />
      </div>

      {/* Metric Cards Row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        <MetricCard label="Total road network" value={m2.totalRoadsKm} unit="km" />
        <MetricCard label="Flooded (Cannot Use)" value={m2.floodedKm} unit="km" tone="high" />
        <MetricCard label="Passable (Open)" value={m2.passableKm} unit="km" tone="low" />
        <MetricCard label="Passable share" value={m2.passablePct} unit="%" tone={m2.passablePct > 70 ? "low" : "high"} />
      </div>

      {/* Main Grid: Interactive Road Map (Left) + Analysis & Performance Panels (Right) */}
      <div style={{ display: "grid", gridTemplateColumns: "1.25fr 1fr", gap: 18, marginBottom: 20 }}>
        {/* Interactive Sri Lanka Road Map */}
        <SriLankaRoadMap
          selectedId={selectedId}
          onSelectDistrict={setSelectedId}
          selectedRoadId={selectedRoadId}
          onSelectRoad={(roadKey) => setSelectedRoadId(roadKey)}
        />

        {/* Right Details Column */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Selected District Road Status Snapshot */}
          <div
            className="panel"
            style={{
              padding: "16px 18px",
              background: "linear-gradient(135deg, var(--bg-panel) 0%, var(--bg-panel-raised) 100%)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <span style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 600 }}>
                  District Road Accessibility
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
                  color: m2.passablePct >= 70 ? "#166534" : "#991b1b",
                  background: m2.passablePct >= 70 ? "#dcfce7" : "#fee2e2",
                  border: `1px solid ${m2.passablePct >= 70 ? "#15803d" : "#dc2626"}`,
                }}
              >
                {m2.passablePct}% Passable
              </span>
            </div>

            {/* Accessibility Progress Bar */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6 }}>
                <span style={{ color: "var(--text-secondary)" }}>Network Clearance:</span>
                <span className="mono" style={{ fontWeight: 600 }}>
                  <strong style={{ color: "#16a34a" }}>{m2.passableKm} km</strong> passable / <strong style={{ color: "#ef4444" }}>{m2.floodedKm} km</strong> flooded
                </span>
              </div>
              <div style={{ height: 10, borderRadius: 6, background: "#fee2e2", border: "1px solid var(--border)", overflow: "hidden", display: "flex" }}>
                <div
                  style={{
                    width: `${m2.passablePct}%`,
                    height: "100%",
                    background: "#16a34a",
                    transition: "width 0.4s ease-out",
                  }}
                />
                <div
                  style={{
                    width: `${100 - m2.passablePct}%`,
                    height: "100%",
                    background: "#ef4444",
                  }}
                />
              </div>
            </div>

            {/* Quick Stat Counters */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div style={{ background: "#fee2e2", padding: "10px 12px", borderRadius: 8, border: "1px solid #fca5a5" }}>
                <p style={{ fontSize: 11, color: "#991b1b", margin: "0 0 2px", fontWeight: 600 }}>🔴 Inundated Routes</p>
                <p className="mono" style={{ fontSize: 17, fontWeight: 700, margin: 0, color: "#b91c1c" }}>
                  {floodedRoads.length} Segments ({m2.floodedKm} km)
                </p>
              </div>
              <div style={{ background: "#dcfce7", padding: "10px 12px", borderRadius: 8, border: "1px solid #86efac" }}>
                <p style={{ fontSize: 11, color: "#166534", margin: "0 0 2px", fontWeight: 600 }}>🟢 Open Routes</p>
                <p className="mono" style={{ fontSize: 17, fontWeight: 700, margin: 0, color: "#15803d" }}>
                  {passableRoads.length} Segments ({m2.passableKm} km)
                </p>
              </div>
            </div>
          </div>

          {/* Model Performance & Radar SAR Analysis */}
          <div className="panel" style={{ padding: 18, flex: 1 }}>
            <p className="panel-title" style={{ margin: "0 0 10px" }}>
              U-Net Segmentation Performance
            </p>
            <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse", marginBottom: 14 }}>
              <tbody>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 0", color: "var(--text-secondary)" }}>F1 score (Intersection over Road)</td>
                  <td className="mono" style={{ padding: "8px 0", textAlign: "right", color: "var(--accent)", fontWeight: 700 }}>
                    {m2.f1.toFixed(2)}
                  </td>
                </tr>
                <tr style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "8px 0", color: "var(--text-secondary)" }}>IoU (Jaccard Index)</td>
                  <td className="mono" style={{ padding: "8px 0", textAlign: "right", color: "var(--accent)", fontWeight: 700 }}>
                    {m2.iou.toFixed(2)}
                  </td>
                </tr>
                <tr>
                  <td style={{ padding: "8px 0", color: "var(--text-secondary)" }}>Base SAR Satellite</td>
                  <td className="mono" style={{ padding: "8px 0", textAlign: "right", color: "var(--text-primary)", fontWeight: 600 }}>
                    Sentinel-1 C-Band
                  </td>
                </tr>
              </tbody>
            </table>

            <p style={{ fontSize: 12.5, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>
              The model detects water backscatter attenuation across road polygons from Sentinel-1 SAR change detection,
              isolating inundated road segments without cloud obstruction.
            </p>
          </div>
        </div>
      </div>

      {/* District Road Segments Detail Table */}
      <div className="panel" style={{ padding: 18 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <div>
            <p className="panel-title" style={{ margin: 0 }}>
              Road Network Inspection ({district.name})
            </p>
            <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "3px 0 0" }}>
              Live classification of individual highways, expressways, and arterial corridors. Click to inspect on map.
            </p>
          </div>

          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
            Showing {roads.length} classified corridors
          </div>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", background: "var(--bg-panel-raised)" }}>
                {["Status", "Route / Highway Name", "Route Code", "Type", "Length", "Field Alert / Condition", "Map Action"].map((h) => (
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
              {roads.map((road, idx) => {
                const isFlooded = road.status === "flooded";
                const isSelected = selectedRoadId === `${selectedId}-${idx}`;

                return (
                  <tr
                    key={`${selectedId}-${idx}`}
                    onClick={() => setSelectedRoadId(`${selectedId}-${idx}`)}
                    style={{
                      borderBottom: "1px solid var(--border)",
                      background: isSelected ? "var(--brand-dim)" : isFlooded ? "rgba(239, 68, 68, 0.04)" : "transparent",
                      cursor: "pointer",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.background = isFlooded ? "rgba(239, 68, 68, 0.08)" : "var(--bg-panel-raised)";
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) e.currentTarget.style.background = isFlooded ? "rgba(239, 68, 68, 0.04)" : "transparent";
                    }}
                  >
                    <td style={{ padding: "10px 14px" }}>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          padding: "3px 8px",
                          borderRadius: 999,
                          fontSize: 11,
                          fontWeight: 700,
                          color: isFlooded ? "#991b1b" : "#166534",
                          background: isFlooded ? "#fee2e2" : "#dcfce7",
                          border: `1px solid ${isFlooded ? "#dc2626" : "#15803d"}`,
                        }}
                      >
                        <span
                          style={{
                            width: 6,
                            height: 6,
                            borderRadius: "50%",
                            background: isFlooded ? "#ef4444" : "#16a34a",
                            boxShadow: `0 0 4px ${isFlooded ? "#ef4444" : "#16a34a"}`,
                          }}
                        />
                        {isFlooded ? "FLOODED" : "PASSABLE"}
                      </span>
                    </td>
                    <td style={{ padding: "10px 14px", fontWeight: 600, color: "var(--text-primary)" }}>
                      {road.name}
                    </td>
                    <td className="mono" style={{ padding: "10px 14px", color: "var(--text-secondary)", fontWeight: 600 }}>
                      {road.code}
                    </td>
                    <td style={{ padding: "10px 14px", color: "var(--text-secondary)" }}>
                      {road.type}
                    </td>
                    <td className="mono" style={{ padding: "10px 14px", fontWeight: 600 }}>
                      {road.lengthKm} km
                    </td>
                    <td style={{ padding: "10px 14px", color: isFlooded ? "#b91c1c" : "var(--text-secondary)", fontSize: 12 }}>
                      {road.note}
                    </td>
                    <td style={{ padding: "10px 14px" }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedRoadId(`${selectedId}-${idx}`);
                        }}
                        style={{
                          fontSize: 11,
                          fontWeight: 600,
                          border: isSelected ? "1px solid var(--brand)" : "1px solid var(--border-strong)",
                          background: isSelected ? "var(--brand)" : "var(--bg-panel)",
                          color: isSelected ? "#ffffff" : "var(--text-primary)",
                          padding: "3px 8px",
                          borderRadius: 6,
                          cursor: "pointer",
                        }}
                      >
                        {isSelected ? "Inspecting" : "Locate"}
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
