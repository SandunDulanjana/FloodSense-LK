import { useState, useRef, useEffect, useMemo } from "react";
import { sriLankaDistrictsGeo, SRI_LANKA_VIEWBOX, MAP_DIMENSIONS } from "../data/sriLankaDistrictsGeo";
import { districts, getDamageTier, getDamageColor, DAMAGE_COLORS } from "../data/mockData";

export default function SriLankaMap({ selectedId, onSelectDistrict }) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredDistrict, setHoveredDistrict] = useState(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [activeTierFilter, setActiveTierFilter] = useState(null); // null or "High" | "Medium" | "Low"

  const containerRef = useRef(null);
  const svgRef = useRef(null);

  // Map mockData to geo features for fast lookup
  const districtDataMap = useMemo(() => {
    const map = new Map();
    districts.forEach((d) => {
      const tier = getDamageTier(d.m3.damagePct);
      const colorInfo = getDamageColor(tier);
      map.set(d.id, {
        ...d,
        damageTier: tier,
        colorInfo,
      });
    });
    return map;
  }, []);

  // Counts by tier
  const tierCounts = useMemo(() => {
    const counts = { High: 0, Medium: 0, Low: 0 };
    districts.forEach((d) => {
      const tier = getDamageTier(d.m3.damagePct);
      if (counts[tier] !== undefined) counts[tier]++;
    });
    return counts;
  }, []);

  // Zoom handlers
  const handleZoomIn = () => {
    setZoom((z) => Math.min(Number((z + 0.35).toFixed(2)), 4.0));
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
    setActiveTierFilter(null);
  };

  // Center on selected district when selectedId changes externally
  useEffect(() => {
    if (!selectedId) return;
    const geo = sriLankaDistrictsGeo.find((g) => g.id === selectedId);
    if (geo && zoom > 1.2) {
      // Smoothly nudge pan towards district centroid if zoomed in
      const [cx, cy] = geo.center;
      const targetPanX = (MAP_DIMENSIONS.width / 2 - cx) * (zoom - 1) * 0.5;
      const targetPanY = (MAP_DIMENSIONS.height / 2 - cy) * (zoom - 1) * 0.5;
      setPan({ x: targetPanX, y: targetPanY });
    }
  }, [selectedId]);

  // Mouse wheel zoom
  const handleWheel = (e) => {
    e.preventDefault();
    const zoomDelta = e.deltaY < 0 ? 0.2 : -0.2;
    setZoom((prev) => {
      const next = Math.max(0.85, Math.min(4.0, Number((prev + zoomDelta).toFixed(2))));
      if (next <= 1) setPan({ x: 0, y: 0 });
      return next;
    });
  };

  // Pan dragging
  const handleMouseDown = (e) => {
    // Only drag with left click
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
        minHeight: 520,
        userSelect: "none",
      }}
      onMouseUp={handleMouseUp}
      onMouseLeave={() => {
        setIsDragging(false);
        setHoveredDistrict(null);
      }}
    >
      {/* Header with Title & Live Filter */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <p className="panel-title" style={{ margin: 0 }}>
              Sri Lanka District Damage Map
            </p>
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 12,
                background: "var(--brand-dim)",
                color: "var(--brand)",
                fontWeight: 600,
              }}
            >
              25 Districts
            </span>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: "4px 0 0" }}>
            Select any district on map to view detailed agricultural impact and crop breakdowns
          </p>
        </div>

        {/* Zoom Controls & Level Badge */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "var(--bg-panel-raised)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "2px",
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
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
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => (e.target.style.background = "var(--border)")}
              onMouseLeave={(e) => (e.target.style.background = "transparent")}
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
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => (e.target.style.background = "var(--border)")}
              onMouseLeave={(e) => (e.target.style.background = "transparent")}
            >
              −
            </button>
          </div>

          <button
            onClick={handleReset}
            title="Reset View"
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

      {/* Map Canvas Container */}
      <div
        style={{
          position: "relative",
          flex: 1,
          minHeight: 460,
          background: "linear-gradient(180deg, #f8fafd 0%, #eef3f9 100%)",
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
        {/* Ambient Map Grid Background */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: "radial-gradient(var(--border) 1px, transparent 1px)",
            backgroundSize: "20px 20px",
            opacity: 0.6,
            pointerEvents: "none",
          }}
        />

        {/* Compass Rose / Ocean Badge */}
        <div
          style={{
            position: "absolute",
            top: 14,
            left: 14,
            background: "rgba(255, 255, 255, 0.85)",
            backdropFilter: "blur(4px)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: "4px 10px",
            fontSize: 11,
            fontWeight: 600,
            color: "var(--text-secondary)",
            pointerEvents: "none",
            boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
          }}
        >
          INDIAN OCEAN
        </div>

        {/* Interactive SVG */}
        <svg
          ref={svgRef}
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
          <defs>
            <filter id="glow-selected" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor="#2f5eff" floodOpacity="0.8" />
            </filter>
            <filter id="glow-high" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#ef4444" floodOpacity="0.6" />
            </filter>
            <filter id="glow-hover" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="0" stdDeviation="3" floodColor="#0f1b33" floodOpacity="0.3" />
            </filter>
          </defs>

          {/* District Polygons */}
          {sriLankaDistrictsGeo.map((geo) => {
            const data = districtDataMap.get(geo.id);
            const isSelected = selectedId === geo.id;
            const isHovered = hoveredDistrict?.id === geo.id;
            const tier = data?.damageTier || "Medium";
            const colorConfig = DAMAGE_COLORS[tier];

            // Opacity handling when filtering by tier
            const isDimmed = activeTierFilter && activeTierFilter !== tier;

            // Colors based on user spec: High=Red, Medium=Green, Low=Yellow
            let fillColor = colorConfig.fill;
            let strokeColor = isSelected ? "#0f1b33" : colorConfig.border;
            let strokeWidth = isSelected ? 3 : isHovered ? 2.2 : 1.2;

            return (
              <g key={geo.id}>
                <path
                  d={geo.path}
                  fill={fillColor}
                  fillOpacity={isDimmed ? 0.25 : isSelected ? 0.95 : isHovered ? 0.9 : 0.78}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  style={{
                    cursor: "pointer",
                    transition: "fill-opacity 0.2s, stroke 0.2s, stroke-width 0.2s",
                    filter: isSelected
                      ? "url(#glow-selected)"
                      : isHovered
                      ? "url(#glow-hover)"
                      : undefined,
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelectDistrict(geo.id);
                  }}
                  onMouseEnter={() => {
                    if (data) setHoveredDistrict({ ...geo, ...data });
                  }}
                  onMouseLeave={() => {
                    setHoveredDistrict(null);
                  }}
                />

                {/* District Name Label */}
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
                  style={{
                    pointerEvents: "none",
                    userSelect: "none",
                    opacity: isDimmed ? 0.3 : 1,
                  }}
                >
                  {geo.name}
                </text>

                {/* Selected Indicator Ring */}
                {isSelected && (
                  <circle
                    cx={geo.center[0]}
                    cy={geo.center[1] + 8}
                    r={3}
                    fill="#ffffff"
                    stroke="#0f1b33"
                    strokeWidth={1.5}
                    style={{ pointerEvents: "none" }}
                  />
                )}
              </g>
            );
          })}
        </svg>

        {/* Floating Tooltip */}
        {hoveredDistrict && (
          <div
            style={{
              position: "absolute",
              left: Math.min(tooltipPos.x + 14, (containerRef.current?.clientWidth || 500) - 230),
              top: Math.max(tooltipPos.y - 85, 10),
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
              minWidth: 190,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontWeight: 700, fontSize: 13, color: "#ffffff" }}>{hoveredDistrict.name}</span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  padding: "2px 6px",
                  borderRadius: 4,
                  background: hoveredDistrict.colorInfo.fill,
                  color: "#ffffff",
                }}
              >
                {hoveredDistrict.damageTier}
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 11, color: "#d1d5db" }}>
              <div>
                <span>Crop Damage: </span>
                <strong style={{ color: "#ffffff" }}>{hoveredDistrict.m3.damagePct}%</strong>
              </div>
              <div>
                <span>Farmers: </span>
                <strong style={{ color: "#ffffff" }}>{hoveredDistrict.m3.affectedFarmers.toLocaleString()}</strong>
              </div>
            </div>
            <div style={{ fontSize: 10, color: "#9ca3af", marginTop: 5, borderTop: "1px solid rgba(255,255,255,0.1)", paddingTop: 4 }}>
              Province: {hoveredDistrict.province} • Click to select
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
            padding: "10px 12px",
            boxShadow: "0 2px 8px rgba(15, 27, 51, 0.08)",
            fontSize: 11,
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
            Damage Severity (Crop Loss)
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {[
              { tier: "High", color: DAMAGE_COLORS.High.fill, label: "High Damage (> 35%)", count: tierCounts.High },
              { tier: "Medium", color: DAMAGE_COLORS.Medium.fill, label: "Medium Damage (20% - 35%)", count: tierCounts.Medium },
              { tier: "Low", color: DAMAGE_COLORS.Low.fill, label: "Low Damage (< 20%)", count: tierCounts.Low },
            ].map((item) => {
              const isActive = activeTierFilter === item.tier;
              return (
                <div
                  key={item.tier}
                  onClick={() => setActiveTierFilter(isActive ? null : item.tier)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    cursor: "pointer",
                    padding: "2px 6px",
                    borderRadius: 4,
                    background: isActive ? "var(--border)" : "transparent",
                    transition: "background 0.15s",
                  }}
                  title={`Click to filter ${item.tier} damage districts`}
                >
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 3,
                      background: item.color,
                      boxShadow: `0 0 4px ${item.color}`,
                    }}
                  />
                  <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{item.label}</span>
                  <span
                    className="mono"
                    style={{
                      marginLeft: "auto",
                      fontSize: 10,
                      color: "var(--text-muted)",
                      fontWeight: 600,
                    }}
                  >
                    {item.count}
                  </span>
                </div>
              );
            })}
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
          Scroll to Zoom • Drag to Pan
        </div>
      </div>
    </div>
  );
}
