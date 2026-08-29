// Mock data layer.
// In the real system, each field here is produced by a trained model (M1-M4)
// or a live data feed. For the prototype, everything is a hardcoded value so
// the UI can be demoed without a backend. Swapping this file for real API
// calls later requires no changes to any component below.

export const districts = [
  {
    id: "colombo",
    name: "Colombo",
    m1: {
      housesDamaged: 3240,
      affectedFamilies: 2110,
      slfdi: 78,
      riskTier: "High",
      modelScores: { linear: 0.71, randomForest: 0.84, xgboost: 0.91, lightgbm: 0.89 },
      bestModel: "xgboost",
    },
    m2: {
      totalRoadsKm: 412,
      floodedKm: 96,
      passableKm: 316,
      passablePct: 77,
      f1: 0.88,
      iou: 0.79,
    },
    m3: {
      cropBreakdown: { paddy: 22, tea: 4, vegetables: 31, other: 43 },
      damagePct: 41,
      livelihoodImpact: "High",
      affectedFarmers: 5400,
    },
    m4: {
      floodProbability: 0.87,
      riskLevel: "HIGH",
      populationExposure: 91,
      infrastructureAccessibility: 68,
      historicalVulnerability: 84,
      sldi: 92,
    },
  },
  {
    id: "ratnapura",
    name: "Ratnapura",
    m1: {
      housesDamaged: 4870,
      affectedFamilies: 3320,
      slfdi: 88,
      riskTier: "Severe",
      modelScores: { linear: 0.68, randomForest: 0.82, xgboost: 0.9, lightgbm: 0.87 },
      bestModel: "xgboost",
    },
    m2: {
      totalRoadsKm: 350,
      floodedKm: 158,
      passableKm: 192,
      passablePct: 55,
      f1: 0.85,
      iou: 0.74,
    },
    m3: {
      cropBreakdown: { paddy: 38, tea: 26, vegetables: 12, other: 24 },
      damagePct: 57,
      livelihoodImpact: "Severe",
      affectedFarmers: 8100,
    },
    m4: {
      floodProbability: 0.93,
      riskLevel: "HIGH",
      populationExposure: 77,
      infrastructureAccessibility: 41,
      historicalVulnerability: 90,
      sldi: 97,
    },
  },
  {
    id: "kegalle",
    name: "Kegalle",
    m1: {
      housesDamaged: 1150,
      affectedFamilies: 780,
      slfdi: 42,
      riskTier: "Medium",
      modelScores: { linear: 0.65, randomForest: 0.79, xgboost: 0.86, lightgbm: 0.83 },
      bestModel: "xgboost",
    },
    m2: {
      totalRoadsKm: 268,
      floodedKm: 41,
      passableKm: 227,
      passablePct: 85,
      f1: 0.87,
      iou: 0.77,
    },
    m3: {
      cropBreakdown: { paddy: 18, tea: 34, vegetables: 9, other: 39 },
      damagePct: 24,
      livelihoodImpact: "Medium",
      affectedFarmers: 2200,
    },
    m4: {
      floodProbability: 0.54,
      riskLevel: "MEDIUM",
      populationExposure: 48,
      infrastructureAccessibility: 82,
      historicalVulnerability: 55,
      sldi: 58,
    },
  },
  {
    id: "batticaloa",
    name: "Batticaloa",
    m1: {
      housesDamaged: 2460,
      affectedFamilies: 1690,
      slfdi: 64,
      riskTier: "High",
      modelScores: { linear: 0.69, randomForest: 0.81, xgboost: 0.89, lightgbm: 0.86 },
      bestModel: "xgboost",
    },
    m2: {
      totalRoadsKm: 305,
      floodedKm: 77,
      passableKm: 228,
      passablePct: 75,
      f1: 0.86,
      iou: 0.76,
    },
    m3: {
      cropBreakdown: { paddy: 46, tea: 0, vegetables: 14, other: 40 },
      damagePct: 38,
      livelihoodImpact: "High",
      affectedFarmers: 4700,
    },
    m4: {
      floodProbability: 0.71,
      riskLevel: "HIGH",
      populationExposure: 63,
      infrastructureAccessibility: 70,
      historicalVulnerability: 66,
      sldi: 74,
    },
  },
];

export const getDistrictById = (id) => districts.find((d) => d.id === id);

export const riskTierColor = {
  Low: "low",
  Medium: "medium",
  High: "high",
  Severe: "severe",
};
