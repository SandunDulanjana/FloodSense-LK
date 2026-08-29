import { useState, useRef, useEffect, useMemo } from "react";
import { sriLankaDistrictsGeo, SRI_LANKA_VIEWBOX, MAP_DIMENSIONS } from "../data/sriLankaDistrictsGeo";
import { districts } from "../data/mockData";
import { districtRoadNetworks, nationalCorridors } from "../data/sriLankaRoadNetworks";

export default function SriLankaRoadMap({ selectedId, onSelectDistrict, selectedRoadId, onSelectRoad }) {
  const [zoom, setZoom] = useState(1.4);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredRoad, setHoveredRoad] = useState(null);
  const [hoveredDistrict, setHoveredDistrict] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [roadFilter, setRoadFilter] = useState("all"); // "all" | "flooded" | "passable"

  const containerRef = useRef(null);
  const svgRef = useRef(null);

  const selectedDistrictData = useMemo(() => {
    return districts.find((d) => d.id === selectedId) || districts[0];
  }, [selectedId]);

  const selectedDistrictGeo = useMemo(() => {
    return sriLankaDistrictsGeo.find((d) => d.id === selectedId) || sriLankaDistrictsGeo[0];
  }, [selectedId]);

  const currentRoads = useMemo(() => {
    return districtRoadNetworks[selectedId] || [];
  }, [selectedId]);

  // Center & zoom onto the selected district
  const focusOnDistrict = (districtId = selectedId, targetZoom = 2.4) => {
    const geo = sriLankaDistrictsGeo.find((d) => d.id === districtId);
    if (geo) {
      const [cx, cy] = geo.center;
      const targetPanX = (MAP_DIMENSIONS.width / 2 - cx) * targetZoom;
      const targetPanY = (MAP_DIMENSIONS.height / 2 - cy) * targetZoom;
      setZoom(targetZoom);
      setPan({ x: targetPanX, y: targetPanY });
    }
  };

  // Focus automatically when selectedId changes
  useEffect(() => {
    focusOnDistrict(selectedId, 2.3);
  }, [selectedId]);

  // Zoom handlers
  const handleZoomIn = () => {
    setZoom((z) => Math.min(Number((z + 0.35).toFixed(2)), 4.5));
  };

  const handleZoomOut = () => {
    setZoom((z) => {
      const nextZ = Math.max(Number((z - 0.35).toFixed(2)), 0.85);
      if (nextZ <= 1) setPan({ x: 0, y: 0 });
      return nextZ;
    });
  };

  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setRoadFilter("all");
  };

  // Mouse wheel zoom
  const handleWheel = (e) => {
    e.preventDefault();
    const zoomDelta = e.deltaY < 0 ? 0.2 : -0.2;
    setZoom((prev) => {
      const next = Math.max(0.85, Math.min(4.5, Number((prev + zoomDelta).toFixed(2))));
      if (next <= 1) setPan({ x: 0, y: 0 });
      return next;
    });
  };

  // Pan dragging
  const handleMouseDown = (e) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e) => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
    }

    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setTooltipPos({
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Convert array of [x, y] to SVG path string
  const pointsToPath = (pts) => {
    return pts.map((pt, i) => `${i === 0 ? "M" : "L"}${pt[0]},${pt[1]}`).join(" ");
  };

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
        minHeight: 540,
        userSelect: "none",
      }}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        setIsDragging(false);
        setHoveredRoad(null);
        setHoveredDistrict(null);
      }}
    >
      {/* Header with Title, Filter Pills, and Zoom Controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <p className="panel-title" style={{ margin: 0 }}>
              Sri Lanka Road Network & Flood Inundation GIS
            </p>
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 12,
                background: "var(--m2-bg)",
                color: "var(--m2)",
                fontWeight: 600,
              }}
            >
              Focus: {selectedDistrictData.name}
            </span>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "4px 0 0" }}>
            Flooded roads colored in <strong style={{ color: "#ef4444" }}>RED (Inundated / Impassable)</strong> and passable roads in <strong style={{ color: "#16a34a" }}>GREEN</strong>
          </p>
        </div>

        {/* Filter Pills & Zoom Toolbar */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {/* Road Status Filters */}
          <div style={{ display: "flex", background: "var(--bg-input)", border: "1px solid var(--border)", borderRadius: 8, padding: 2 }}>
            {[
              { id: "all", label: "All Roads" },
              { id: "flooded", label: "🔴 Flooded" },
              { id: "passable", label: "🟢 Passable" },
            ].map((f) => {
              const active = roadFilter === f.id;
              return (
                <button
                  key={f.id}
                  onClick={() => setRoadFilter(f.id)}
                  style={{
                    border: "none",
                    background: active ? "var(--bg-panel-raised)" : "transparent",
                    color: active ? "var(--text-primary)" : "var(--text-secondary)",
                    fontWeight: active ? 700 : 500,
                    fontSize: 11.5,
                    padding: "4px 10px",
                    borderRadius: 6,
                    cursor: "pointer",
                    boxShadow: active ? "0 1px 3px rgba(0,0,0,0.06)" : "none",
                  }}
                >
                  {f.label}
                </button>
              );
            })}
          </div>

          {/* Zoom Buttons */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "var(--bg-panel-raised)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "2px",
            }}
          >
            <button
              onClick={handleZoomIn}
              title="Zoom In (+)"
              style={{
                width: 28,
                height: 28,
                border: "none",
                background: "transparent",
                borderRadius: 6,
                cursor: "pointer",
                fontWeight: 700,
                fontSize: 16,
                color: "var(--text-primary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              +
            </button>
            <span
              className="mono"
              style={{
                fontSize: 11,
                padding: "0 6px",
                color: "var(--text-muted)",
                minWidth: 42,
                textAlign: "center",
              }}
            >
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={handleZoomOut}
              title="Zoom Out (-)"
              style={{
                width: 28,
                height: 28,
                border: "none",
                background: "transparent",
                borderRadius: 6,
                cursor: "pointer",
                fontWeight: 700,
                fontSize: 16,
                color: "var(--text-primary)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              −
            </button>
          </div>

          {/* Focus District & Reset Buttons */}
          <button
            onClick={() => focusOnDistrict(selectedId, 2.5)}
            title="Focus on Selected District"
            style={{
              height: 32,
              padding: "0 10px",
              border: "1px solid var(--border)",
              background: "var(--bg-panel-raised)",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span>🎯</span> Focus
          </button>

          <button
            onClick={handleReset}
            title="Reset to Full Sri Lanka View"
            style={{
              height: 32,
              padding: "0 10px",
              border: "1px solid var(--border)",
              background: "var(--bg-panel-raised)",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 12,
              fontWeight: 500,
              color: "var(--text-secondary)",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span>⟲</span> Reset
          </button>
        </div>
      </div>

      {/* Map SVG Canvas */}
      <div
        style={{
          position: "relative",
          flex: 1,
          minHeight: 480,
          background: "linear-gradient(180deg, #f5f8fc 0%, #ebf1f8 100%)",
          borderRadius: 8,
          border: "1px solid var(--border)",
          overflow: "hidden",
          cursor: isDragging ? "grabbing" : "grab",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
      >
        {/* Ocean Grids */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: "radial-gradient(#d3dde8 1px, transparent 1px)",
            backgroundSize: "24px 24px",
            opacity: 0.7,
            pointerEvents: "none",
          }}
        />

        {/* Ocean Water Label */}
        <div
          style={{
            position: "absolute",
            top: 14,
            left: 14,
            background: "rgba(255, 255, 255, 0.9)",
            backdropFilter: "blur(4px)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "4px 10px",
            fontSize: 11,
            fontWeight: 600,
            color: "var(--text-secondary)",
            pointerEvents: "none",
          }}
        >
          BAY OF BENGAL / INDIAN OCEAN
        </div>

        {/* Main SVG Vector Layer */}
        <svg
          ref={svgRef}
          viewBox={SRI_LANKA_VIEWBOX}
          style={{
            width: "100%",
            height: "100%",
            maxHeight: 540,
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: "center center",
            transition: isDragging ? "none" : "transform 0.12s cubic-bezier(0.1, 0.9, 0.2, 1)",
            filter: "drop-shadow(0 4px 14px rgba(15, 27, 51, 0.08))",
          }}
        >
          <defs>
            <filter id="road-glow-red" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="2.5" floodColor="#ef4444" floodOpacity="0.8" />
            </filter>
            <filter id="road-glow-green" x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="2" floodColor="#16a34a" floodOpacity="0.6" />
            </filter>
            <filter id="selected-district-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3.5" floodColor="#0ea5a0" floodOpacity="0.7" />
            </filter>
          </defs>

          {/* 1. Base District Polygons */}
          {sriLankaDistrictsGeo.map((geo) => {
            const isSelected = selectedId === geo.id;
            const isHovered = hoveredDistrict?.id === geo.id;

            return (
              <g key={geo.id}>
                <path
                  d={geo.path}
                  fill={isSelected ? "#ffffff" : isHovered ? "#f1f5f9" : "#e8edf5"}
                  stroke={isSelected ? "#0ea5a0" : "#cad4e2"}
                  strokeWidth={isSelected ? 2.8 : 1.1}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  style={{
                    cursor: "pointer",
                    transition: "fill 0.2s, stroke 0.2s, stroke-width 0.2s",
                    filter: isSelected ? "url(#selected-district-glow)" : undefined,
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectDistrict(geo.id);
                  }}
                  onMouseEnter={() => setHoveredDistrict(geo)}
                  onMouseLeave={() => setHoveredDistrict(null)}
                />

                {/* District Name Label */}
                <text
                  x={geo.center[0]}
                  y={geo.center[1]}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fill={isSelected ? "#0f1b33" : "#64708a"}
                  stroke="#ffffff"
                  strokeWidth="2px"
                  paintOrder="stroke fill"
                  fontSize={zoom > 1.8 ? 9 : zoom > 1.2 ? 7.5 : 6.8}
                  fontWeight={isSelected ? "800" : "600"}
                  fontFamily="var(--font-sans)"
                  style={{
                    pointerEvents: "none",
                    userSelect: "none",
                    opacity: isSelected ? 1 : 0.75,
                  }}
                >
                  {geo.name}
                </text>
              </g>
            );
          })}

          {/* 2. National Connecting Trunk Highway Overlay (Subtle) */}
          {nationalCorridors.map((c) => (
            <path
              key={c.id}
              d={pointsToPath(c.path)}
              fill="none"
              stroke="#94a3b8"
              strokeWidth={zoom > 2 ? 1.2 : 0.9}
              strokeDasharray="4 3"
              opacity={0.65}
              style={{ pointerEvents: "none" }}
            />
          ))}

          {/* 3. All District Road Networks with Flooded (Red) and Passable (Green) */}
          {districts.map((d) => {
            const roads = districtRoadNetworks[d.id] || [];
            const isDistrictSelected = d.id === selectedId;

            return (
              <g key={`roads-${d.id}`} opacity={isDistrictSelected ? 1 : zoom > 1.8 ? 0.35 : 0.6}>
                {roads.map((road, idx) => {
                  const isFlooded = road.status === "flooded";
                  const matchesFilter =
                    roadFilter === "all" ||
                    (roadFilter === "flooded" && isFlooded) ||
                    (roadFilter === "passable" && !isFlooded);

                  if (!matchesFilter) return null;

                  const isRoadHovered = hoveredRoad?.name === road.name;
                  const isRoadActive = selectedRoadId === `${d.id}-${idx}`;

                  // Road colors: Flooded = RED, Passable = GREEN
                  const lineColor = isFlooded ? "#ef4444" : "#16a34a";
                  const lineWidth = isDistrictSelected
                    ? (isRoadHovered || isRoadActive ? 4.5 : isFlooded ? 3.2 : 2.5)
                    : 1.5;

                  return (
                    <g key={`road-${d.id}-${idx}`}>
                      {/* Under-glow for Flooded & Hovered roads */}
                      {(isFlooded || isRoadHovered || isRoadActive) && (
                        <path
                          d={pointsToPath(road.path)}
                          fill="none"
                          stroke={isFlooded ? "rgba(239, 68, 68, 0.4)" : "rgba(22, 163, 74, 0.4)"}
                          strokeWidth={lineWidth + 4}
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          style={{ pointerEvents: "none" }}
                        />
                      )}

                      {/* Main Road Line */}
                      <path
                        d={pointsToPath(road.path)}
                        fill="none"
                        stroke={lineColor}
                        strokeWidth={lineWidth}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeDasharray={isFlooded ? (zoom > 2 ? "6 3" : undefined) : undefined}
                        style={{
                          cursor: "pointer",
                          transition: "stroke-width 0.15s, stroke 0.15s",
                          filter: isFlooded ? "url(#road-glow-red)" : undefined,
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (!isDistrictSelected) {
                            onSelectDistrict(d.id);
                          }
                          if (onSelectRoad) {
                            onSelectRoad(`${d.id}-${idx}`, road);
                          }
                        }}
                        onMouseEnter={() => {
                          setHoveredRoad({ ...road, districtName: d.name });
                        }}
                        onMouseLeave={() => {
                          setHoveredRoad(null);
                        }}
                      />

                      {/* Warning Pulse Marker on Flooded Road Midpoints */}
                      {isFlooded && isDistrictSelected && road.path.length >= 2 && (
                        <g>
                          <circle
                            cx={(road.path[0][0] + road.path[1][0]) / 2}
                            cy={(road.path[0][1] + road.path[1][1]) / 2}
                            r={zoom > 2 ? 3.5 : 2.5}
                            fill="#dc2626"
                            stroke="#ffffff"
                            strokeWidth={1}
                            style={{ pointerEvents: "none" }}
                          />
                        </g>
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>

        {/* Floating Road Inspection Tooltip */}
        {hoveredRoad && (
          <div
            style={{
              position: "absolute",
              left: Math.min(tooltipPos.x + 14, (containerRef.current?.clientWidth || 500) - 270),
              top: Math.max(tooltipPos.y - 100, 12),
              background: "rgba(15, 27, 51, 0.96)",
              backdropFilter: "blur(8px)",
              color: "#ffffff",
              borderRadius: 8,
              padding: "10px 14px",
              fontSize: 12,
              pointerEvents: "none",
              zIndex: 30,
              boxShadow: "0 8px 24px rgba(0,0,0,0.25)",
              border: "1px solid rgba(255,255,255,0.15)",
              minWidth: 240,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontWeight: 700, fontSize: 13, color: "#ffffff" }}>{hoveredRoad.name}</span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  textTransform: "uppercase",
                  padding: "3px 8px",
                  borderRadius: 4,
                  background: hoveredRoad.status === "flooded" ? "#ef4444" : "#16a34a",
                  color: "#ffffff",
                  boxShadow: `0 0 6px ${hoveredRoad.status === "flooded" ? "#ef4444" : "#16a34a"}`,
                }}
              >
                {hoveredRoad.status === "flooded" ? "🔴 FLOODED — CANNOT USE" : "🟢 PASSABLE — OPEN"}
              </span>
              <span style={{ fontSize: 11, color: "#9ca3af" }}>{hoveredRoad.lengthKm} km</span>
            </div>

            <p style={{ fontSize: 11, color: "#e5e7eb", margin: "4px 0 0", lineHeight: 1.4 }}>
              {hoveredRoad.note}
            </p>
            <div style={{ fontSize: 10, color: "#9ca3af", marginTop: 6, borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 4 }}>
              District: {hoveredRoad.districtName} • Route Type: {hoveredRoad.type}
            </div>
          </div>
        )}

        {/* Legend Overlay at bottom-left */}
        <div
          style={{
            position: "absolute",
            bottom: 12,
            left: 12,
            background: "rgba(255, 255, 255, 0.92)",
            backdropFilter: "blur(8px)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "10px 14px",
            boxShadow: "0 2px 10px rgba(15, 27, 51, 0.08)",
            fontSize: 11.5,
            zIndex: 10,
          }}
        >
          <p
            style={{
              fontSize: 10,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "var(--text-secondary)",
              margin: "0 0 6px",
            }}
          >
            Road Network Status ({selectedDistrictData.name})
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  width: 14,
                  height: 4,
                  borderRadius: 2,
                  background: "#ef4444",
                  boxShadow: "0 0 6px #ef4444",
                }}
              />
              <span style={{ color: "#b91c1c", fontWeight: 700 }}>Flooded (Cannot Use):</span>
              <span className="mono" style={{ marginLeft: "auto", fontWeight: 700, color: "#ef4444" }}>
                {selectedDistrictData.m2.floodedKm} km
              </span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span
                style={{
                  width: 14,
                  height: 4,
                  borderRadius: 2,
                  background: "#16a34a",
                  boxShadow: "0 0 6px #16a34a",
                }}
              />
              <span style={{ color: "#15803d", fontWeight: 700 }}>Passable (Open):</span>
              <span className="mono" style={{ marginLeft: "auto", fontWeight: 700, color: "#16a34a" }}>
                {selectedDistrictData.m2.passableKm} km
              </span>
            </div>
          </div>
        </div>

        {/* Map Instructions hint at bottom-right */}
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
          Scroll to Zoom • Drag to Pan • Click Road to Inspect
        </div>
      </div>
    </div>
  );
}
