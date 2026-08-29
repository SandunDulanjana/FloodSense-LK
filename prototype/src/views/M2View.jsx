import { useState } from "react";
import DistrictSelector from "../components/DistrictSelector";
import MetricCard from "../components/MetricCard";
import { getDistrictById } from "../data/mockData";

export default function M2View() {
  const [selectedId, setSelectedId] = useState("colombo");
  const district = getDistrictById(selectedId);
  const { m2 } = district;

  const passableBlocks = Math.round(m2.passablePct / 5);
  const floodedBlocks = 20 - passableBlocks;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--m2)", background: "var(--m2-bg)", padding: "3px 8px", borderRadius: 6 }}>M2</span>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, margin: 0 }}>Road accessibility classification</h1>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
            U-Net fine-tuned on Sentinel-1 SAR change detection, pre-trained on SpaceNet 8
          </p>
        </div>
        <DistrictSelector selectedId={selectedId} onChange={setSelectedId} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        <MetricCard label="Total road network" value={m2.totalRoadsKm} unit="km" />
        <MetricCard label="Flooded" value={m2.floodedKm} unit="km" tone="high" />
        <MetricCard label="Passable" value={m2.passableKm} unit="km" tone="low" />
        <MetricCard label="Passable share" value={m2.passablePct} unit="%" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 16 }}>
        <div className="panel" style={{ padding: 18 }}>
          <p className="panel-title">Road segment status (mock grid — replace with GIS overlay)</p>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 14px" }}>
            Each cell represents a classified road segment for {district.name}
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(10, 1fr)", gap: 6 }}>
            {Array.from({ length: 20 }).map((_, i) => (
              <div
                key={i}
                style={{
                  aspectRatio: "1",
                  borderRadius: 4,
                  background: i < floodedBlocks ? "var(--risk-high-bg)" : "var(--risk-low-bg)",
                  border: `1px solid ${i < floodedBlocks ? "var(--risk-high)" : "var(--risk-low)"}`,
                }}
              />
            ))}
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 14, fontSize: 12, color: "var(--text-secondary)" }}>
            <span><span style={{ color: "var(--risk-high)" }}>■</span> Flooded</span>
            <span><span style={{ color: "var(--risk-low)" }}>■</span> Passable</span>
          </div>
        </div>

        <div className="panel" style={{ padding: 18 }}>
          <p className="panel-title">Model performance</p>
          <table style={{ width: "100%", fontSize: 13, borderCollapse: "collapse" }}>
            <tbody>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "8px 0", color: "var(--text-secondary)" }}>F1 score</td>
                <td className="mono" style={{ padding: "8px 0", textAlign: "right", color: "var(--accent)", fontWeight: 700 }}>{m2.f1.toFixed(2)}</td>
              </tr>
              <tr>
                <td style={{ padding: "8px 0", color: "var(--text-secondary)" }}>IoU</td>
                <td className="mono" style={{ padding: "8px 0", textAlign: "right", color: "var(--accent)", fontWeight: 700 }}>{m2.iou.toFixed(2)}</td>
              </tr>
            </tbody>
          </table>
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 12 }}>
            Evaluated against GIS threshold baseline. Post-deployment requires only one after-flood SAR image.
          </p>
        </div>
      </div>
    </div>
  );
}
