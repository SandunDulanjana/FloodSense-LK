import { districts } from "../data/mockData";

export default function DistrictSelector({ selectedId, onChange }) {
  return (
    <select
      value={selectedId}
      onChange={(e) => onChange(e.target.value)}
      style={{
        background: "var(--bg-input)",
        color: "var(--text-primary)",
        border: "1px solid var(--border-strong)",
        borderRadius: "var(--radius)",
        padding: "8px 12px",
        fontSize: 14,
        minWidth: 180,
      }}
    >
      {districts.map((d) => (
        <option key={d.id} value={d.id}>
          {d.name}
        </option>
      ))}
    </select>
  );
}
