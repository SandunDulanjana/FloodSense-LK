import { NavLink } from "react-router-dom";

const modules = [
  { to: "/m1", label: "Building damage", key: "M1", color: "var(--m1)", bg: "var(--m1-bg)", border: "var(--m1-border)", desc: "AI Damage Estimation" },
  { to: "/m2", label: "Road accessibility", key: "M2", color: "var(--m2)", bg: "var(--m2-bg)", border: "var(--m2-border)", desc: "SAR Inundation Map" },
  { to: "/m3", label: "Agricultural impact", key: "M3", color: "var(--m3)", bg: "var(--m3-bg)", border: "var(--m3-border)", desc: "Crop Damage & GIS" },
  { to: "/m4", label: "Flood forecast", key: "M4", color: "var(--m4)", bg: "var(--m4-bg)", border: "var(--m4-border)", desc: "SLDI Prioritization" },
];

function SectionLabel({ children }) {
  return (
    <p
      style={{
        fontSize: 10.5,
        fontWeight: 800,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color: "var(--text-muted)",
        margin: "18px 10px 6px",
      }}
    >
      {children}
    </p>
  );
}

export default function Sidebar() {
  return (
    <aside
      style={{
        width: 246,
        flexShrink: 0,
        background: "rgba(255, 255, 255, 0.88)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        borderRight: "1px solid var(--border)",
        padding: "20px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 4,
        boxShadow: "2px 0 16px rgba(15, 23, 42, 0.02)",
      }}
    >
      {/* Brand Header */}
      <div style={{ padding: "0 8px 14px", display: "flex", alignItems: "center", gap: 10 }}>
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: 10,
            background: "linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#ffffff",
            fontWeight: 800,
            fontSize: 15,
            boxShadow: "0 4px 12px rgba(37, 99, 235, 0.3)",
            position: "relative",
          }}
        >
          <span>🌊</span>
          <span
            style={{
              position: "absolute",
              top: -2,
              right: -2,
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: "#22c55e",
              border: "2px solid #ffffff",
            }}
          />
        </div>
        <div>
          <p style={{ fontFamily: "var(--font-display)", fontSize: 16, fontWeight: 800, margin: 0, letterSpacing: "-0.02em", color: "var(--text-primary)" }}>
            FloodSense-LK
          </p>
          <p style={{ fontSize: 11, color: "var(--text-muted)", margin: 0, fontWeight: 500 }}>
            Disaster Ops Command
          </p>
        </div>
      </div>

      <SectionLabel>Main Navigation</SectionLabel>
      <NavLink
        to="/"
        end
        style={({ isActive }) => ({
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "10px 12px",
          borderRadius: "var(--radius-sm)",
          fontSize: 13.5,
          fontWeight: 600,
          textDecoration: "none",
          color: isActive ? "#ffffff" : "var(--text-secondary)",
          background: isActive ? "linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)" : "transparent",
          boxShadow: isActive ? "0 4px 14px rgba(37, 99, 235, 0.3)" : "none",
          transition: "all 0.15s ease",
        })}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <span>📊</span>
          <span>Overview Dashboard</span>
        </span>
      </NavLink>

      <SectionLabel>Assessment Modules</SectionLabel>
      {modules.map((m) => (
        <NavLink
          key={m.to}
          to={m.to}
          style={({ isActive }) => ({
            display: "flex",
            flexDirection: "column",
            gap: 2,
            padding: "8px 12px",
            borderRadius: "var(--radius-sm)",
            fontSize: 13,
            textDecoration: "none",
            color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
            background: isActive ? m.bg : "transparent",
            border: isActive ? `1px solid ${m.border}` : "1px solid transparent",
            fontWeight: isActive ? 600 : 500,
            transition: "all 0.15s ease",
          })}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: m.color,
                  boxShadow: `0 0 6px ${m.color}`,
                  flexShrink: 0,
                }}
              />
              {m.label}
            </span>
            <span
              className="mono"
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: m.color,
                background: m.bg,
                padding: "1px 5px",
                borderRadius: 4,
                border: `1px solid ${m.border}`,
              }}
            >
              {m.key}
            </span>
          </div>
          <span style={{ fontSize: 10.5, color: "var(--text-muted)", marginLeft: 16 }}>
            {m.desc}
          </span>
        </NavLink>
      ))}

      {/* Live System Feed Status Widget at bottom */}
      <div style={{ marginTop: "auto", padding: "10px 4px 0" }}>
        <div
          style={{
            background: "linear-gradient(135deg, rgba(240, 253, 250, 0.8) 0%, rgba(239, 246, 255, 0.8) 100%)",
            border: "1px solid #c7d2fe",
            borderRadius: "var(--radius-sm)",
            padding: "10px 12px",
            fontSize: 11,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "#16a34a",
                boxShadow: "0 0 6px #16a34a",
              }}
            />
            <span style={{ fontWeight: 700, color: "#1e3a8a", fontSize: 10.5, textTransform: "uppercase" }}>
              Live Telemetry
            </span>
          </div>
          <p style={{ margin: 0, color: "var(--text-secondary)", fontSize: 11, lineHeight: 1.4 }}>
            Sentinel-1 SAR & Rainfall feeds operational for 25 districts.
          </p>
        </div>
        <div style={{ paddingTop: 8, fontSize: 11, color: "var(--text-muted)", textAlign: "center" }}>
          DMC Sri Lanka • Prototype v2.0
        </div>
      </div>
    </aside>
  );
}
