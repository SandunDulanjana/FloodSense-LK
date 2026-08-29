import { NavLink } from "react-router-dom";

const modules = [
  { to: "/m1", label: "Building damage", key: "M1", color: "var(--m1)" },
  { to: "/m2", label: "Road accessibility", key: "M2", color: "var(--m2)" },
  { to: "/m3", label: "Agricultural impact", key: "M3", color: "var(--m3)" },
  { to: "/m4", label: "Flood risk", key: "M4", color: "var(--m4)" },
];

function SectionLabel({ children }) {
  return (
    <p
      style={{
        fontSize: 10.5,
        fontWeight: 700,
        letterSpacing: "0.08em",
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
        width: 232,
        flexShrink: 0,
        background: "var(--bg-panel)",
        borderRight: "1px solid var(--border)",
        padding: "20px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 2,
      }}
    >
      <div style={{ padding: "0 10px 12px", display: "flex", alignItems: "center", gap: 8 }}>
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: "var(--brand)",
          }}
        />
        <div>
          <p style={{ fontFamily: "var(--font-display)", fontSize: 15, fontWeight: 700, margin: 0 }}>SLDI</p>
          <p style={{ fontSize: 10.5, color: "var(--text-muted)", margin: 0 }}>Disaster ops center</p>
        </div>
      </div>

      <SectionLabel>Main</SectionLabel>
      <NavLink
        to="/"
        end
        style={({ isActive }) => ({
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "9px 12px",
          borderRadius: "var(--radius)",
          fontSize: 13.5,
          fontWeight: 500,
          textDecoration: "none",
          color: isActive ? "#fff" : "var(--text-secondary)",
          background: isActive ? "var(--brand)" : "transparent",
        })}
      >
        Dashboard
      </NavLink>

      <SectionLabel>Modules</SectionLabel>
      {modules.map((m) => (
        <NavLink
          key={m.to}
          to={m.to}
          style={({ isActive }) => ({
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "9px 12px",
            borderRadius: "var(--radius)",
            fontSize: 13.5,
            textDecoration: "none",
            color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
            background: isActive ? "var(--bg-panel-raised)" : "transparent",
            fontWeight: isActive ? 500 : 400,
          })}
        >
          <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: 999, background: m.color, flexShrink: 0 }} />
            {m.label}
          </span>
          <span className="mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>{m.key}</span>
        </NavLink>
      ))}

      <div style={{ marginTop: "auto", padding: "14px 10px 0" }}>
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: 12, fontSize: 11.5, color: "var(--text-muted)" }}>
          DMC Sri Lanka · prototype
        </div>
      </div>
    </aside>
  );
}
