// M4 pre-flood prediction model (prototype).
//
// The chain: catchment rainfall (10-day, local + upstream) -> river stage (m)
//   -> flood probability (logistic) -> risk level -> SLDI.
//
// This is a UI prototype: there is no trained model. The numbers already in
// mockData.js (m4.floodProbability, m4.historicalVulnerability, ...) are treated
// as ground truth, and this module *inverts* the logistic curve to reconstruct a
// self-consistent river stage and rainfall history that would produce them, so
// every screen agrees on one probability.
//
// River danger / alert / minor-flood levels are representative prototype values,
// loosely following DMC river-gauge conventions and the sample columns in
// data/m1_data/ (rainfall_chirps.csv, dmc_flood_records.csv). They are NOT
// gauge-accurate.

// Per-river danger level (m) and the mountain catchment that feeds it. Alert and
// minor-flood levels are derived as fixed fractions of the danger level
// (see ALERT_FRAC / MINOR_FLOOD_FRAC in getRiverForDistrict).
export const RIVERS = {
  "Kelani River":     { dangerLevelM: 7.0, catchment: "Kelani Upper Catchment (Nuwara Eliya / Kegalle hills)" },
  "Kalu River":       { dangerLevelM: 6.5, catchment: "Kalu Upper Catchment (Adam's Peak range / Sinharaja)" },
  "Gin River":        { dangerLevelM: 4.2, catchment: "Gin Ganga Catchment (Deniyaya / Sinharaja)" },
  "Nilwala River":    { dangerLevelM: 4.5, catchment: "Nilwala Catchment (Matara hills)" },
  "Mahaweli River":   { dangerLevelM: 8.0, catchment: "Mahaweli Upper Catchment (Central Highlands)" },
  "Malwathu Oya":     { dangerLevelM: 5.0, catchment: "Malwathu Oya Catchment (North Central plains)" },
  "Deduru Oya":       { dangerLevelM: 5.5, catchment: "Deduru Oya Catchment (Kurunegala)" },
  "Maha Oya":         { dangerLevelM: 5.0, catchment: "Maha Oya Catchment (Kegalle / Kurunegala hills)" },
  "Attanagalu Oya":   { dangerLevelM: 4.0, catchment: "Attanagalu Oya Catchment (Gampaha)" },
  "Gal Oya":          { dangerLevelM: 6.0, catchment: "Gal Oya Catchment (Ampara / Senanayake Samudraya)" },
  "Maduru Oya":       { dangerLevelM: 5.5, catchment: "Maduru Oya Catchment (Batticaloa basin)" },
  "Kirindi Oya":      { dangerLevelM: 4.5, catchment: "Kirindi Oya Catchment (Hambantota dry zone)" },
  "Menik Ganga":      { dangerLevelM: 4.0, catchment: "Menik Ganga Catchment (Monaragala / Yala)" },
  "Yan Oya":          { dangerLevelM: 4.5, catchment: "Yan Oya Catchment (Vavuniya / Trincomalee)" },
  "Kanakarayan Aru":  { dangerLevelM: 4.0, catchment: "Kanakarayan Aru Catchment (Kilinochchi / Vanni)" },
  "Coastal / lagoon": { dangerLevelM: 2.6, catchment: "Jaffna Peninsula lagoon & tidal flats (no major river)" },
};

const ALERT_FRAC = 0.8;       // alert level = 80% of danger level
const MINOR_FLOOD_FRAC = 0.9; // minor-flood level = 90% of danger level

export const DEFAULT_RIVER = "Maha Oya";

export const DISTRICT_RIVER = {
  colombo: "Kelani River",
  gampaha: "Attanagalu Oya",
  kalutara: "Kalu River",
  kandy: "Mahaweli River",
  matale: "Mahaweli River",
  nuwara_eliya: "Mahaweli River",
  galle: "Gin River",
  matara: "Nilwala River",
  hambantota: "Kirindi Oya",
  jaffna: "Coastal / lagoon",
  kilinochchi: "Kanakarayan Aru",
  mannar: "Malwathu Oya",
  vavuniya: "Malwathu Oya",
  mullaitivu: "Yan Oya",
  batticaloa: "Maduru Oya",
  ampara: "Gal Oya",
  trincomalee: "Mahaweli River",
  kurunegala: "Deduru Oya",
  puttalam: "Deduru Oya",
  anuradhapura: "Malwathu Oya",
  polonnaruwa: "Mahaweli River",
  badulla: "Mahaweli River",
  monaragala: "Menik Ganga",
  ratnapura: "Kalu River",
  kegalle: "Kelani River",
};

// --- logistic model constants ----------------------------------------------
const K = 3.2;   // logistic slope
const R0 = 0.82; // stage ratio (level / danger) at which p = 0.5, before the vulnerability shift

// --- deterministic helpers -------------------------------------------------
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
const round = (x, d = 0) => {
  const p = 10 ** d;
  return Math.round(x * p) / p;
};

function hash01(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 4294967296;
}
const jitter = (id, i, amp = 0.1) => 1 + (hash01(`${id}|${i}`) * 2 - 1) * amp;

const vulnShift = (historicalVulnerability) => (historicalVulnerability - 60) / 200;

// upstream rainfall is weighted 1.4x; upstream = combinedIndex / 2.6, local = the remainder
const RAIN_SPLIT = 2.6;
const LOCAL_FRAC = 1 - 1.4 / RAIN_SPLIT; // ~0.4615

// --- forward model --------------------------------------------------------
export function getRiverForDistrict(districtId) {
  const name = DISTRICT_RIVER[districtId] || DEFAULT_RIVER;
  const base = RIVERS[name];
  return {
    name,
    ...base,
    alertLevelM: round(base.dangerLevelM * ALERT_FRAC, 1),
    minorFloodM: round(base.dangerLevelM * MINOR_FLOOD_FRAC, 1),
  };
}

// combined 10-day rainfall index (local + weighted upstream, mm) -> river stage (m)
export function predictRiverLevel({ rainfall10dayMm, upstreamRainfall10dayMm, river }) {
  const D = river.dangerLevelM;
  const combinedIndex = rainfall10dayMm + 1.4 * upstreamRainfall10dayMm;
  return clamp(0.35 * D + 0.55 * D * (combinedIndex / 100), 0.3 * D, 1.5 * D);
}

// river stage (m) -> flood probability (0..1)
export function predictFloodProbability({ riverLevelM, dangerLevelM, historicalVulnerability }) {
  const r = riverLevelM / dangerLevelM;
  const p = 1 / (1 + Math.exp(-K * (r - R0 + vulnShift(historicalVulnerability))));
  return clamp(p, 0.02, 0.98);
}

export function riverStageStatus(levelM, river) {
  if (levelM >= river.dangerLevelM) return "DANGER";
  if (levelM >= river.minorFloodM) return "MINOR FLOOD";
  if (levelM >= river.alertLevelM) return "ALERT";
  return "NORMAL";
}

// --- inverse: reconstruct the chain from the authored m4 numbers ----------
function combinedIndexForLevel(levelM, D) {
  return clamp(((levelM - 0.35 * D) / (0.55 * D)) * 100, 4, 520);
}

export function deriveM4Chain(district) {
  const { id, m4 } = district;
  const river = getRiverForDistrict(id);
  const D = river.dangerLevelM;
  const hv = m4.historicalVulnerability;
  const p = clamp(m4.floodProbability, 0.02, 0.98);

  // invert predictFloodProbability -> stage ratio -> river stage
  const logit = Math.log(p / (1 - p));
  const r = clamp(R0 - vulnShift(hv) + logit / K, 0.35, 1.45);
  const riverLevelM = round(r * D, 2);

  const predictedPeakLevelM = round(Math.min(riverLevelM * (1.06 + 0.12 * p), 1.5 * D), 2);

  // rainfall that explains the current stage
  const combined = combinedIndexForLevel(riverLevelM, D);
  const rainfall10dayMm = round(combined * LOCAL_FRAC);
  const upstreamRainfall10dayMm = round(combined / RAIN_SPLIT);

  // 7-step build-up, one step per 10 days; the river line ends exactly on riverLevelM
  const shape = [0.4, 0.52, 0.47, 0.64, 0.8, 0.93, 1];
  const trend = shape.map((f, i) => {
    const last = i === shape.length - 1;
    const levelStep = last
      ? riverLevelM
      : round(clamp(riverLevelM * f * jitter(id, i, 0.06), 0.3 * D, 1.5 * D), 2);
    const stepCombined = combinedIndexForLevel(levelStep, D);
    return {
      label: `T-${(shape.length - 1 - i) * 10}d`,
      rainfallMm: round(stepCombined * LOCAL_FRAC),
      riverLevelM: levelStep,
    };
  });

  const modelFloodProbability = round(
    predictFloodProbability({ riverLevelM, dangerLevelM: D, historicalVulnerability: hv }),
    2,
  );

  return {
    riverName: river.name,
    catchment: river.catchment,
    rainfall10dayMm,
    upstreamRainfall10dayMm,
    riverLevelM,
    riverDangerLevelM: D,
    riverAlertLevelM: river.alertLevelM,
    riverMinorFloodLevelM: river.minorFloodM,
    predictedPeakLevelM,
    modelFloodProbability,
    riverStageStatus: riverStageStatus(riverLevelM, river),
    trend,
  };
}

// --- forward: roll the chain ahead under a rainfall scenario -----------------
// Given a district's current chain and a "what if N more mm fall upstream"
// scenario, run the FORWARD model 72h ahead. The extra rain reaches the river
// progressively (ramp), so each 24h step re-evaluates predictRiverLevel ->
// predictFloodProbability. At extraUpstream10dayMm = 0 this round-trips the
// inverse chain, so the forecast sits flat at the current level.
export function projectForecast(district, extraUpstream10dayMm = 0) {
  const { m4 } = district;
  const river = getRiverForDistrict(district.id);
  const D = river.dangerLevelM;
  const hv = m4.historicalVulnerability;
  const ramp = [0.45, 0.8, 1.0];

  // Anchor on the district's actual current stage; the scenario only adds the
  // *incremental* rise the extra rain would cause. So extra = 0 -> flat at the
  // current level (no round-trip rounding drift).
  const baseForwardLevel = predictRiverLevel({
    rainfall10dayMm: m4.rainfall10dayMm,
    upstreamRainfall10dayMm: m4.upstreamRainfall10dayMm,
    river,
  });

  const points = ramp.map((f, i) => {
    const upstream = m4.upstreamRainfall10dayMm + extraUpstream10dayMm * f;
    const scenarioForwardLevel = predictRiverLevel({
      rainfall10dayMm: m4.rainfall10dayMm,
      upstreamRainfall10dayMm: upstream,
      river,
    });
    const riverLevelM = round(
      clamp(m4.riverLevelM + (scenarioForwardLevel - baseForwardLevel), 0.3 * D, 1.5 * D),
      2,
    );
    const floodProbability = round(
      predictFloodProbability({ riverLevelM, dangerLevelM: D, historicalVulnerability: hv }),
      2,
    );
    return {
      label: `+${(i + 1) * 24}h`,
      rainfallMm: round(m4.rainfall10dayMm + extraUpstream10dayMm * f * LOCAL_FRAC),
      riverLevelM,
      floodProbability,
    };
  });

  const peak = points[points.length - 1];
  return {
    points,
    peakLevelM: peak.riverLevelM,
    peakProbability: peak.floodProbability,
    peakStatus: riverStageStatus(peak.riverLevelM, river),
    baseLevelM: m4.riverLevelM,
    baseProbability: m4.modelFloodProbability,
  };
}

// --- decision support: chain output -> operational posture ------------------
// Deterministic lookup. `override` lets a scenario ask "what posture would the
// PROJECTED state trigger?" by supplying { riskLevel, riverStageStatus }.
export function recommendResponse(district, override = {}) {
  const { m4 } = district;
  const risk = override.riskLevel || m4.riskLevel;
  const stage = override.riverStageStatus || m4.riverStageStatus;
  const exposure = m4.populationExposure;
  const access = m4.infrastructureAccessibility;

  let posture;
  let tone;
  let headline;
  if (stage === "DANGER" || (risk === "HIGH" && exposure >= 80)) {
    posture = "EVACUATE";
    tone = "severe";
    headline = "Order evacuation of low-lying wards now; flooding imminent or underway.";
  } else if (stage === "MINOR FLOOD" || risk === "HIGH" || (risk === "MEDIUM" && exposure >= 70)) {
    posture = "PREPARE";
    tone = "high";
    headline = "Pre-position resources and issue public warnings; conditions deteriorating.";
  } else if (stage === "ALERT" || risk === "MEDIUM") {
    posture = "MONITOR";
    tone = "medium";
    headline = "Heighten gauge monitoring and brief Divisional Secretariat officers.";
  } else {
    posture = "ROUTINE";
    tone = "low";
    headline = "No action beyond standard monitoring.";
  }

  const actions = [];
  if (posture === "EVACUATE") {
    actions.push("Activate district EOC; open designated safe locations / shelters.");
    actions.push("Deploy rescue teams and boats to riverside GN divisions.");
    actions.push("Broadcast evacuation routes via DMC alert channels + SMS.");
  } else if (posture === "PREPARE") {
    actions.push("Stage relief stocks (dry rations, tarpaulins, water) at DS offices.");
    actions.push("Put rescue teams and boats on standby; verify shelter readiness.");
    actions.push("Issue public 'be ready to move' advisory.");
  } else if (posture === "MONITOR") {
    actions.push("Increase river-gauge reads to 3-hourly; watch upstream rainfall.");
    actions.push("Confirm contact tree for at-risk GN divisions.");
  } else {
    actions.push("Continue daily gauge and rainfall monitoring.");
  }
  if (posture !== "ROUTINE" && access < 60) {
    actions.push("Plan boat / airlift access — roads to this district are likely cut.");
  }

  return { posture, tone, headline, actions, allocationPriority: m4.sldi };
}

// classify a bare probability into the same tiers M4 uses
export function riskLevelForProbability(p) {
  if (p >= 0.66) return "HIGH";
  if (p >= 0.4) return "MEDIUM";
  return "LOW";
}
