import { useState, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
} from "recharts";
import DistrictSelector from "../components/DistrictSelector";
import MetricCard from "../components/MetricCard";
import RiskBadge from "../components/RiskBadge";
import FloodRiskMap from "../components/FloodRiskMap";
import { districts, getDistrictById } from "../data/mockData";
import { projectForecast, recommendResponse, riskLevelForProbability } from "../data/floodRiskModel";

const stageToneMap = { NORMAL: "low", ALERT: "medium", "MINOR FLOOD": "high", DANGER: "severe" };
const postureToneMap = { ROUTINE: "low", MONITOR: "medium", PREPARE: "high", EVACUATE: "severe" };

function Arrow() {
  return (
    <span style={{ fontSize: 18, color: "var(--text-muted)", textAlign: "center" }} aria-hidden>
      &rarr;
    </span>
  );
}

function Stage({ label, value, sub, tone }) {
  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-sm)",
        background: tone ? `var(--risk-${tone}-bg)` : "var(--bg-panel-raised)",
        padding: "12px 14px",
        minHeight: 96,
      }}
    >
      <p
        style={{
          fontSize: 10,
          letterSpacing: "0.05em",
          textTransform: "uppercase",
          fontWeight: 700,
          color: "var(--text-secondary)",
          margin: "0 0 6px",
        }}
      >
        {label}
      </p>
      <div
        className="mono"
        style={{ fontSize: 20, fontWeight: 800, lineHeight: 1.1, color: tone ? `var(--risk-${tone})` : "var(--text-primary)" }}
      >
        {value}
      </div>
      <p style={{ fontSize: 10.5, color: "var(--text-muted)", margin: "6px 0 0", lineHeight: 1.35 }}>{sub}</p>
    </div>
  );
}

function DeltaChip({ value, unit }) {
  const positive = value > 0;
  const neutral = value === 0;
  const color = neutral ? "var(--text-muted)" : positive ? "var(--risk-high)" : "var(--risk-low)";
  const sign = positive ? "+" : "";
  return (
    <span className="mono" style={{ fontSize: 10.5, color, fontWeight: 700 }}>
      {neutral ? "no change" : `${sign}${value}${unit}`}
    </span>
  );
}

function exportCsv() {
  const head = [
    "District",
    "Province",
    "River",
    "Rainfall_10day_mm",
    "Upstream_10day_mm",
    "River_level_m",
    "Danger_level_m",
    "Stage_status",
    "Flood_probability_pct",
    "Risk_level",
    "SLDI",
  ];
  const rows = [...districts]
    .sort((a, b) => b.m4.sldi - a.m4.sldi)
    .map((d) => [
      d.name,
      d.province,
      d.m4.riverName,
      d.m4.rainfall10dayMm,
      d.m4.upstreamRainfall10dayMm,
      d.m4.riverLevelM,
      d.m4.riverDangerLevelM,
      d.m4.riverStageStatus,
      Math.round(d.m4.floodProbability * 100),
      d.m4.riskLevel,
      d.m4.sldi,
    ]);
  const csv = [head, ...rows].map((r) => r.map((x) => `"${x}"`).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "floodsense-m4-priority.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export default function M4View() {
  const [searchParams, setSearchParams] = useSearchParams();
  const districtId = searchParams.get("district") || "colombo";
  const district = getDistrictById(districtId);
  const setDistrict = (id) => setSearchParams(id === "colombo" ? {} : { district: id });
  const { m4 } = district;

  const [extraRain, setExtraRain] = useState(0);
  useEffect(() => setExtraRain(0), [districtId]);

  const forecast = useMemo(() => projectForecast(district, extraRain), [district, extraRain]);
  const response = useMemo(() => recommendResponse(district), [district]);
  const nationalSldiTotal = useMemo(() => districts.reduce((s, d) => s + d.m4.sldi, 0), []);
  const reliefShare = Math.round((m4.sldi / nationalSldiTotal) * 100);

  const projRisk = riskLevelForProbability(forecast.peakProbability);
  const projPosture = recommendResponse(district, {
    riskLevel: projRisk,
    riverStageStatus: forecast.peakStatus,
  }).posture;
  const dLevel = Number((forecast.peakLevelM - m4.riverLevelM).toFixed(2));
  const dProb = Math.round((forecast.peakProbability - m4.floodProbability) * 100);

  const riskTone = m4.riskLevel === "HIGH" ? "high" : m4.riskLevel === "MEDIUM" ? "medium" : "low";
  const stageTone = stageToneMap[m4.riverStageStatus] || "low";
  const sldiTone = m4.sldi > 80 ? "severe" : riskTone;
  const pct = Math.round(m4.floodProbability * 100);
  const titleRisk = m4.riskLevel === "HIGH" ? "High" : m4.riskLevel === "MEDIUM" ? "Medium" : "Low";

  const factors = [
    { label: "Flood probability", value: pct },
    { label: "Population exposure", value: m4.populationExposure },
    { label: "Infrastructure accessibility", value: m4.infrastructureAccessibility },
    { label: "Historical vulnerability", value: m4.historicalVulnerability },
  ];

  const detailRows = [
    ["River", m4.riverName],
    ["Catchment", m4.catchment],
    ["Alert level", `${m4.riverAlertLevelM} m`],
    ["Minor-flood level", `${m4.riverMinorFloodLevelM} m`],
    ["Danger level", `${m4.riverDangerLevelM} m`],
    ["Current stage", `${m4.riverLevelM} m (${m4.riverStageStatus})`],
    ["Predicted peak", `${m4.predictedPeakLevelM} m`],
  ];

  const chartData = [
    ...m4.trend.map((p, i) => ({
      label: p.label,
      rainfallMm: p.rainfallMm,
      histLevel: p.riverLevelM,
      ...(i === m4.trend.length - 1 ? { fcstLevel: p.riverLevelM } : {}),
    })),
    ...forecast.points.map((p) => ({ label: p.label, rainfallMm: p.rainfallMm, fcstLevel: p.riverLevelM })),
  ];
  const levelAxisMax = Math.ceil(Math.max(m4.riverDangerLevelM, forecast.peakLevelM) * 1.3);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: "var(--m4)", background: "var(--m4-bg)", padding: "3px 8px", borderRadius: 6 }}>M4</span>
            <h1 style={{ fontFamily: "var(--font-display)", fontSize: 18, fontWeight: 700, margin: 0 }}>Flood forecast &amp; early warning</h1>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
            Pre-flood chain &mdash; catchment rainfall &rarr; river stage &rarr; flood probability &rarr; risk level &rarr; SLDI
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={exportCsv}
            style={{
              background: "var(--bg-panel)",
              color: "var(--text-primary)",
              border: "1px solid var(--border-strong)",
              borderRadius: "var(--radius-sm)",
              padding: "8px 14px",
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            &#8595; Export CSV
          </button>
          <DistrictSelector selectedId={districtId} onChange={setDistrict} />
        </div>
      </div>

      {/* Prediction chain strip */}
      <div className="panel" style={{ padding: 18, marginBottom: 20 }}>
        <p className="panel-title">Prediction chain</p>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr auto 1fr auto 1fr auto 1fr auto 1fr",
            alignItems: "center",
            gap: 10,
          }}
        >
          <Stage
            label="Rainfall · 10-day"
            value={`${m4.rainfall10dayMm} mm`}
            sub={`+${m4.upstreamRainfall10dayMm} mm upstream · ${m4.catchment}`}
          />
          <Arrow />
          <Stage
            label="River stage"
            value={`${m4.riverLevelM} m`}
            sub={`${m4.riverName} · danger ${m4.riverDangerLevelM} m · ${m4.riverStageStatus}`}
            tone={stageTone}
          />
          <Arrow />
          <Stage label="Flood probability" value={`${pct}%`} sub="logistic(stage / danger, historical vulnerability)" tone={riskTone} />
          <Arrow />
          <Stage label="Risk level" value={<RiskBadge tier={titleRisk} />} sub="classification threshold" tone={riskTone} />
          <Arrow />
          <Stage label="SLDI" value={m4.sldi} sub="fused prioritization index" tone={sldiTone} />
        </div>
      </div>

      {/* Headline metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        <MetricCard label="Flood probability" value={pct} unit="%" tone={riskTone} />
        <MetricCard label="River level vs danger" value={`${m4.riverLevelM} / ${m4.riverDangerLevelM}`} unit="m" tone={stageTone} />
        <MetricCard label="Predicted peak stage" value={m4.predictedPeakLevelM} unit="m" tone={stageTone} />
        <MetricCard label="SLDI composite score" value={m4.sldi} tone={sldiTone} />
      </div>

      {/* Rainfall what-if scenario */}
      <div className="panel" style={{ padding: 18, marginBottom: 20 }}>
        <p className="panel-title">Rainfall scenario &mdash; what if more rain falls upstream?</p>
        <div style={{ display: "flex", alignItems: "center", gap: 16, margin: "4px 0 16px" }}>
          <input
            type="range"
            min={0}
            max={300}
            step={10}
            value={extraRain}
            onChange={(e) => setExtraRain(Number(e.target.value))}
            style={{ flex: 1, accentColor: "var(--m4)" }}
          />
          <span className="mono" style={{ fontSize: 15, fontWeight: 800, color: "var(--m4)", minWidth: 78, textAlign: "right" }}>
            +{extraRain} mm
          </span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
          <Stage
            label="Projected river stage"
            value={`${forecast.peakLevelM} m`}
            sub={<DeltaChip value={dLevel} unit=" m" />}
            tone={stageToneMap[forecast.peakStatus] || "low"}
          />
          <Stage
            label="Projected flood probability"
            value={`${Math.round(forecast.peakProbability * 100)}%`}
            sub={<DeltaChip value={dProb} unit=" pts" />}
            tone={projRisk === "HIGH" ? "high" : projRisk === "MEDIUM" ? "medium" : "low"}
          />
          <Stage
            label="Projected stage status"
            value={forecast.peakStatus}
            sub="within 72 h"
            tone={stageToneMap[forecast.peakStatus] || "low"}
          />
          <Stage
            label="Projected posture"
            value={projPosture}
            sub="recommended response"
            tone={postureToneMap[projPosture] || "low"}
          />
        </div>
        <p style={{ fontSize: 11.5, color: "var(--text-muted)", margin: "14px 0 0", lineHeight: 1.5 }}>
          Adds up to 300 mm to the 10-day upstream total for the {m4.catchment}, rolled forward 72 h through the forward model
          (predictRiverLevel &rarr; predictFloodProbability). Baseline scenario = 0 mm.
        </p>
      </div>

      {/* Trend + map */}
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16, marginBottom: 20 }}>
        <div className="panel" style={{ padding: 18 }}>
          <p className="panel-title">Catchment rainfall &amp; river stage &mdash; 60-day history + 72 h forecast</p>
          <ResponsiveContainer width="100%" height={240}>
            <ComposedChart data={chartData}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="label" stroke="var(--text-muted)" fontSize={12} />
              <YAxis yAxisId="rain" stroke="var(--text-muted)" fontSize={12} />
              <YAxis
                yAxisId="level"
                orientation="right"
                stroke="var(--text-muted)"
                fontSize={12}
                domain={[0, levelAxisMax]}
              />
              <Tooltip
                contentStyle={{ background: "var(--bg-panel-raised)", border: "1px solid var(--border-strong)", borderRadius: 8 }}
                labelStyle={{ color: "var(--text-primary)" }}
              />
              <Legend />
              <Bar yAxisId="rain" dataKey="rainfallMm" name="Rainfall (10-day, mm)" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              <Line yAxisId="level" dataKey="histLevel" name="River level (m)" stroke="var(--m4)" strokeWidth={2} dot={{ r: 3 }} />
              <Line
                yAxisId="level"
                dataKey="fcstLevel"
                name="Forecast level (m)"
                stroke="var(--m4)"
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={{ r: 3 }}
                connectNulls
              />
              <ReferenceLine
                yAxisId="level"
                y={m4.riverDangerLevelM}
                stroke="var(--risk-high)"
                strokeDasharray="4 4"
                label={{ value: "Danger", fontSize: 10, fill: "var(--risk-high)", position: "insideTopRight" }}
              />
              <ReferenceLine
                yAxisId="level"
                y={m4.riverAlertLevelM}
                stroke="var(--risk-medium)"
                strokeDasharray="3 3"
                label={{ value: "Alert", fontSize: 10, fill: "var(--risk-medium)", position: "insideBottomRight" }}
              />
              <ReferenceLine
                yAxisId="level"
                x="T-0d"
                stroke="var(--text-muted)"
                label={{ value: "now", fontSize: 10, fill: "var(--text-muted)", position: "top" }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>

        <FloodRiskMap selectedId={districtId} onSelectDistrict={setDistrict} />
      </div>

      {/* SLDI breakdown + recommended response */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        <div className="panel" style={{ padding: 18 }}>
          <p className="panel-title">SLDI factor breakdown</p>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "0 0 16px" }}>
            Flood probability, population exposure, infrastructure accessibility and historical vulnerability combine into one
            resource-prioritization score.
          </p>
          {factors.map((f) => (
            <div key={f.label} style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
                <span style={{ color: "var(--text-secondary)" }}>{f.label}</span>
                <span className="mono" style={{ color: "var(--text-primary)" }}>{f.value}</span>
              </div>
              <div style={{ height: 7, borderRadius: 4, background: "var(--bg-input)", overflow: "hidden" }}>
                <div style={{ width: `${f.value}%`, height: "100%", background: "var(--accent)" }} />
              </div>
            </div>
          ))}
          <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 12 }}>
            Composite SLDI = <span style={{ color: "var(--text-primary)" }}>{m4.sldi}</span>
          </p>
        </div>

        <div className="panel" style={{ padding: 18 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <p className="panel-title" style={{ margin: 0 }}>Recommended response</p>
            <span
              style={{
                fontSize: 11,
                fontWeight: 800,
                letterSpacing: "0.04em",
                padding: "3px 10px",
                borderRadius: 999,
                color: `var(--risk-${response.tone})`,
                background: `var(--risk-${response.tone}-bg)`,
              }}
            >
              {response.posture}
            </span>
          </div>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.55, margin: "0 0 12px" }}>
            {response.headline}
          </p>
          <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 8 }}>
            {response.actions.map((a) => (
              <li key={a} style={{ display: "flex", gap: 8, fontSize: 12.5, color: "var(--text-primary)", lineHeight: 1.45 }}>
                <span style={{ color: "var(--m4)", fontWeight: 700 }}>&#9642;</span>
                <span>{a}</span>
              </li>
            ))}
          </ul>
          <p style={{ fontSize: 12, color: "var(--text-muted)", margin: "14px 0 0", borderTop: "1px solid var(--border)", paddingTop: 10 }}>
            Suggested relief-allocation share: <strong style={{ color: "var(--text-primary)" }}>{reliefShare}%</strong> of national
            response ({m4.sldi} SLDI &divide; {nationalSldiTotal} national total).
          </p>
        </div>
      </div>

      {/* Narrative + river detail */}
      <div className="panel" style={{ padding: 18 }}>
        <p className="panel-title">How the pipeline reads {district.name}</p>
        <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 18 }}>
          <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.6, margin: 0 }}>
            Over the last 10 days <strong>{district.name}</strong> recorded <strong>{m4.rainfall10dayMm} mm</strong> locally and{" "}
            <strong>{m4.upstreamRainfall10dayMm} mm</strong> across the {m4.catchment}. That drives <strong>{m4.riverName}</strong> to an
            estimated <strong>{m4.riverLevelM} m</strong> against a <strong>{m4.riverDangerLevelM} m</strong> danger level (
            <strong>{m4.riverStageStatus}</strong>), with a forecast crest of <strong>{m4.predictedPeakLevelM} m</strong>. The
            flood-probability model returns <strong>{pct}%</strong>, classified <strong>{m4.riskLevel}</strong>. Combined with population
            exposure ({m4.populationExposure}), infrastructure accessibility ({m4.infrastructureAccessibility}) and historical
            vulnerability ({m4.historicalVulnerability}), the Sri Lanka Disaster Index is <strong>{m4.sldi}</strong>. Under a{" "}
            <strong>+{extraRain} mm</strong> upstream scenario the model projects <strong>{forecast.peakLevelM} m</strong> (
            <strong>{forecast.peakStatus}</strong>) within 72 h.
          </p>
          <table style={{ width: "100%", fontSize: 12.5, borderCollapse: "collapse" }}>
            <tbody>
              {detailRows.map(([k, v]) => (
                <tr key={k} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "7px 0", color: "var(--text-secondary)" }}>{k}</td>
                  <td style={{ padding: "7px 0", textAlign: "right", color: "var(--text-primary)" }}>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
