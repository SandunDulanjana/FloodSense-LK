import { useState, useRef, useMemo } from "react";
import { sriLankaDistrictsGeo, SRI_LANKA_VIEWBOX } from "../data/sriLankaDistrictsGeo";
import { districts } from "../data/mockData";

// River-stage status -> colour. SVG needs literal hex, so these mirror the
// --risk-* design tokens (severe / high / medium / low).
const STAGE_STYLE = {
  DANGER: { fill: "#991b1b", stroke: "#7f1d1d", label: "Danger" },
  "MINOR FLOOD": { fill: "#dc2626", stroke: "#b91c1c", label: "Minor flood" },
  ALERT: { fill: "#d97706", stroke: "#b45309", label: "Alert" },
  NORMAL: { fill: "#16a34a", stroke: "#15803d", label: "Normal" },
};
const STAGE_ORDER = ["DANGER", "MINOR FLOOD", "ALERT", "NORMAL"];

export default function FloodRiskMap({ selectedId, onSelectDistrict }) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hovered, setHovered] = useState(null);
  const [tipPos, setTipPos] = useState({ x: 0, y: 0 });
  const containerRef = useRef(null);

  const dataById = useMemo(() => {
    const map = new Map();
    districts.forEach((d) => map.set(d.id, d));
    return map;
  }, []);

  const stageCounts = useMemo(() => {
    const counts = { DANGER: 0, "MINOR FLOOD": 0, ALERT: 0, NORMAL: 0 };
    districts.forEach((d) => {
      const s = d.m4.riverStageStatus;
      if (counts[s] !== undefined) counts[s] += 1;
    });
    return counts;
  }, []);

  const clampZoom = (z) => Math.max(0.85, Math.min(4, Number(z.toFixed(2))));
  const handleZoomIn = () => setZoom((z) => clampZoom(z + 0.35));
  const handleZoomOut = () =>
    setZoom((z) => {
      const next = clampZoom(z - 0.35);
      if (next <= 1) setPan({ x: 0, y: 0 });
      return next;
    });
  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleWheel = (e) => {
    e.preventDefault();
    setZoom((z) => {
      const next = clampZoom(z + (e.deltaY < 0 ? 0.2 : -0.2));
      if (next <= 1) setPan({ x: 0, y: 0 });
      return next;
    });
  };
  const handleMouseDown = (e) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };
  const handleMouseMove = (e) => {
    if (isDragging) setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setTipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    }
  };
  const handleMouseUp = () => setIsDragging(false);

  return (
    <div
      className="panel"
      ref={containerRef}
      style={{
        position: "relative",
        padding: "16px 18px",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        minHeight: 480,
        userSelect: "none",
      }}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        setIsDragging(false);
        setHovered(null);
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
        <div>
          <p className="panel-title" style={{ margin: 0 }}>
            District flood-stage map
          </p>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "3px 0 0" }}>
            Coloured by current river stage vs danger level. Click a district to inspect it.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "var(--bg-panel-raised)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: 2,
            }}
          >
            <button onClick={handleZoomIn} title="Zoom in" style={zoomBtn}>
              +
            </button>
            <span className="mono" style={{ fontSize: 11, padding: "0 6px", color: "var(--text-muted)", minWidth: 40, textAlign: "center" }}>
              {Math.round(zoom * 100)}%
            </span>
            <button onClick={handleZoomOut} title="Zoom out" style={zoomBtn}>
              −
            </button>
          </div>
          <button onClick={handleReset} title="Reset view" style={{ ...zoomBtn, width: "auto", padding: "0 10px", height: 30, border: "1px solid var(--border)", background: "var(--bg-panel-raised)", fontSize: 12, fontWeight: 500 }}>
            ⟲
          </button>
        </div>
      </div>

      <div
        style={{
          position: "relative",
          flex: 1,
          minHeight: 420,
          background: "linear-gradient(180deg, #f8fafd 0%, #eef3f9 100%)",
          borderRadius: 8,
          border: "1px solid var(--border)",
          overflow: "hidden",
          cursor: isDragging ? "grabbing" : "grab",
        }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
      >
        <svg
          viewBox={SRI_LANKA_VIEWBOX}
          style={{
            width: "100%",
            height: "100%",
            maxHeight: 520,
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
            transition: isDragging ? "none" : "transform 0.12s cubic-bezier(0.1, 0.9, 0.2, 1)",
            filter: "drop-shadow(0 4px 12px rgba(15, 27, 51, 0.08))",
          }}
        >
          {sriLankaDistrictsGeo.map((geo) => {
            const d = dataById.get(geo.id);
            const stage = d?.m4.riverStageStatus || "NORMAL";
            const style = STAGE_STYLE[stage] || STAGE_STYLE.NORMAL;
            const isSelected = selectedId === geo.id;
            const isHovered = hovered?.id === geo.id;
            return (
              <g key={geo.id}>
                <path
                  d={geo.path}
                  fill={style.fill}
                  fillOpacity={isSelected ? 0.95 : isHovered ? 0.9 : 0.78}
                  stroke={isSelected ? "#0f1b33" : style.stroke}
                  strokeWidth={isSelected ? 3 : isHovered ? 2.2 : 1.2}
                  strokeLinejoin="round"
                  style={{ cursor: "pointer", transition: "fill-opacity 0.2s, stroke 0.2s, stroke-width 0.2s" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectDistrict(geo.id);
                  }}
                  onMouseEnter={() => d && setHovered({ ...geo, data: d })}
                  onMouseLeave={() => setHovered(null)}
                />
                <text
                  x={geo.center[0]}
                  y={geo.center[1]}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill={isSelected ? "#ffffff" : "#0f1b33"}
                  stroke={isSelected ? "#000000" : "#ffffff"}
                  strokeWidth={isSelected ? "1.5px" : "1.8px"}
                  paintOrder="stroke fill"
                  fontSize={zoom > 1.8 ? 9 : zoom > 1.2 ? 7.5 : 6.8}
                  fontWeight={isSelected ? "800" : "600"}
                  fontFamily="var(--font-sans)"
                  style={{ pointerEvents: "none", userSelect: "none" }}
                >
                  {geo.name}
                </text>
              </g>
            );
          })}
        </svg>

        {hovered && (
          <div
            style={{
              position: "absolute",
              left: Math.min(tipPos.x + 14, (containerRef.current?.clientWidth || 500) - 240),
              top: Math.max(tipPos.y - 90, 10),
              background: "rgba(15, 27, 51, 0.95)",
              backdropFilter: "blur(6px)",
              color: "#ffffff",
              borderRadius: 8,
              padding: "10px 14px",
              fontSize: 12,
              pointerEvents: "none",
              zIndex: 30,
              boxShadow: "0 8px 24px rgba(0,0,0,0.22)",
              border: "1px solid rgba(255,255,255,0.15)",
              minWidth: 200,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontWeight: 700, fontSize: 13 }}>{hovered.data.name}</span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  padding: "2px 6px",
                  borderRadius: 4,
                  background: (STAGE_STYLE[hovered.data.m4.riverStageStatus] || STAGE_STYLE.NORMAL).fill,
                }}
              >
                {hovered.data.m4.riverStageStatus}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "#d1d5db", lineHeight: 1.6 }}>
              <div>{hovered.data.m4.riverName}</div>
              <div>
                Stage: <strong style={{ color: "#fff" }}>{hovered.data.m4.riverLevelM} m</strong> / danger{" "}
                {hovered.data.m4.riverDangerLevelM} m
              </div>
              <div>
                Flood probability:{" "}
                <strong style={{ color: "#fff" }}>{Math.round(hovered.data.m4.floodProbability * 100)}%</strong>
              </div>
            </div>
            <div style={{ fontSize: 10, color: "#9ca3af", marginTop: 5, borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 4 }}>
              {hovered.data.province} Province • Click to select
            </div>
          </div>
        )}

        <div
          style={{
            position: "absolute",
            bottom: 12,
            left: 12,
            background: "rgba(255, 255, 255, 0.92)",
            backdropFilter: "blur(8px)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "10px 12px",
            boxShadow: "0 2px 8px rgba(15, 27, 51, 0.08)",
            fontSize: 11,
            zIndex: 10,
          }}
        >
          <p style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-secondary)", margin: "0 0 6px" }}>
            River stage
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {STAGE_ORDER.map((stage) => (
              <div key={stage} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 10, height: 10, borderRadius: 3, background: STAGE_STYLE[stage].fill }} />
                <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{STAGE_STYLE[stage].label}</span>
                <span className="mono" style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-muted)", fontWeight: 600 }}>
                  {stageCounts[stage]}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div
          style={{
            position: "absolute",
            bottom: 12,
            right: 12,
            fontSize: 11,
            color: "var(--text-muted)",
            background: "rgba(255, 255, 255, 0.85)",
            backdropFilter: "blur(4px)",
            padding: "4px 8px",
            borderRadius: 6,
            border: "1px solid var(--border)",
            pointerEvents: "none",
          }}
        >
          Scroll to zoom • Drag to pan
        </div>
      </div>
    </div>
  );
}

const zoomBtn = {
  width: 28,
  height: 28,
  border: "none",
  background: "transparent",
  borderRadius: 6,
  cursor: "pointer",
  fontWeight: 700,
  fontSize: 15,
  color: "var(--text-primary)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};
