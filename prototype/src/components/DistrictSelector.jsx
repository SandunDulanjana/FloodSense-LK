import { districts } from "../data/mockData";

export default function DistrictSelector({ selectedId, onChange }) {
  const sorted = [...districts].sort((a, b) => a.name.localeCompare(b.name));

  return (
    <select
      value={selectedId}
      onChange={(e) => onChange(e.target.value)}
      style={{
        background: "var(--bg-input)",
        color: "var(--text-primary)",
        border: "1px solid var(--border-strong)",
        borderRadius: "var(--radius)",
        padding: "8px 14px",
        fontSize: 13.5,
        fontWeight: 500,
        minWidth: 200,
        cursor: "pointer",
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
      }}
    >
      {sorted.map((d) => (
        <option key={d.id} value={d.id}>
          {d.name} {d.province ? `(${d.province})` : ""}
        </option>
      ))}
    </select>
  );
}
