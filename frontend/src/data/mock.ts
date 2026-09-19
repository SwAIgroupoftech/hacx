import type {
  Advisory, BacktestMetric, Bottleneck, Forecast, ForecastPoint, Incident, Proposal, Segment,
} from "../types";

export const segments: Segment[] = [
  { id: "A17", name: "North Corridor", corridor: "North Ring", speed: 34, freeFlow: 58, speedRatio: .59, anomalyScore: 2.8, state: "severe", timestamp: "14:31", x1: 40, y1: 25, x2: 82, y2: 46 },
  { id: "B04", name: "Civic Link", corridor: "Central Grid", speed: 46, freeFlow: 55, speedRatio: .84, anomalyScore: 1.1, state: "moderate", timestamp: "14:30", x1: 22, y1: 62, x2: 61, y2: 62 },
  { id: "C08", name: "East Connector", corridor: "East Arc", speed: 27, freeFlow: 60, speedRatio: .45, anomalyScore: 3.4, state: "incident", timestamp: "14:26", x1: 66, y1: 25, x2: 72, y2: 72 },
  { id: "D12", name: "South Link", corridor: "South Ring", speed: 51, freeFlow: 57, speedRatio: .89, anomalyScore: .6, state: "normal", timestamp: "14:29", x1: 25, y1: 74, x2: 78, y2: 80 },
  { id: "E21", name: "Market Spine", corridor: "Central Grid", speed: 31, freeFlow: 52, speedRatio: .60, anomalyScore: 2.4, state: "recurring", timestamp: "14:28", x1: 48, y1: 12, x2: 50, y2: 90 },
  { id: "F09", name: "West Bypass", corridor: "West Arc", speed: 54, freeFlow: 60, speedRatio: .90, anomalyScore: .4, state: "normal", timestamp: "14:31", x1: 15, y1: 40, x2: 83, y2: 26 },
  { id: "G03", name: "Harbor Approach", corridor: "South East", speed: 38, freeFlow: 56, speedRatio: .68, anomalyScore: 1.9, state: "anomalous", timestamp: "14:27", x1: 58, y1: 52, x2: 89, y2: 76 },
];

export const incidents: Incident[] = [
  { id: "INC-041", timestamp: "14:26", segment: "C08", type: "Possible incident", severity: "high", confidence: 82, evidence: ["Speed 61 → 34 km/h", "11 min duration", "Upstream slowdown detected", "Historical baseline: 58 km/h"], status: "classified", validation: "VALIDATED" },
  { id: "INC-039", timestamp: "14:31", segment: "A17", type: "Non-recurring congestion", severity: "medium", confidence: 91, evidence: ["Speed ratio: 0.59", "Anomaly score: 2.8", "Pattern differs from hour-of-week baseline"], status: "active", validation: "VALIDATED" },
  { id: "INC-037", timestamp: "14:18", segment: "E21", type: "Recurring congestion", severity: "low", confidence: 95, evidence: ["Recurring across 14 historical windows", "Average duration: 27 min"], status: "classified", validation: "VALIDATED" },
  { id: "INC-032", timestamp: "13:54", segment: "G03", type: "Unclassified anomaly", severity: "medium", confidence: 48, evidence: ["Speed ratio: 0.68", "Insufficient incident evidence"], status: "unclassified", validation: "INSUFFICIENT EVIDENCE" },
];

export const forecastPoints: ForecastPoint[] = [
  { time: "13:30", actual: 49, baseline: 48, llm: 50 },
  { time: "13:45", actual: 46, baseline: 47, llm: 45 },
  { time: "14:00", actual: 43, baseline: 45, llm: 44 },
  { time: "14:15", actual: 39, baseline: 43, llm: 40 },
  { time: "14:30", actual: 35, baseline: 41, llm: 36 },
  { time: "14:45", baseline: 39, llm: 34 },
  { time: "15:00", baseline: 38, llm: 32 },
  { time: "15:15", baseline: 37, llm: 33 },
];

export const forecasts: Forecast[] = [
  { horizon: 15, value: 34, confidence: 88, baseline: 39, state: "severe" },
  { horizon: 30, value: 32, confidence: 82, baseline: 38, state: "severe" },
  { horizon: 45, value: 33, confidence: 76, baseline: 37, state: "severe" },
  { horizon: 60, value: 36, confidence: 69, baseline: 37, state: "moderate" },
];

export const advisories: Advisory[] = [
  { id: "ADV-018", title: "North Corridor congestion", timestamp: "14:32", segments: ["A17", "E21"], reason: "Sustained speed reduction over the last 12 minutes.", evidence: ["A17 · 14:21–14:33 · speed ratio 0.58", "E21 · recurring pattern detected"], action: "Consider alternate route via Civic Link.", confidence: 84, validation: "VALIDATED" },
  { id: "ADV-016", title: "East Connector incident watch", timestamp: "14:27", segments: ["C08"], reason: "Sudden speed reduction with upstream slowdown.", evidence: ["C08 · 61 → 34 km/h", "11 minute duration"], action: "Monitor East Connector and consider diversion if deterioration continues.", confidence: 82, validation: "VALIDATED" },
  { id: "ADV-012", title: "Harbor Approach anomaly", timestamp: "14:19", segments: ["G03"], reason: "Abnormal speed ratio but insufficient evidence for classification.", evidence: ["G03 · speed ratio 0.68", "anomaly score 1.9"], action: "No diversion recommendation; continue observation.", confidence: 48, validation: "INSUFFICIENT EVIDENCE" },
];

export const bottlenecks: Bottleneck[] = [
  { id: "BN-01", segment: "E21", corridor: "Central Grid", occurrences: 22, duration: 27, severity: 78, delay: 18.4, trend: 8.2 },
  { id: "BN-02", segment: "A17", corridor: "North Ring", occurrences: 18, duration: 21, severity: 73, delay: 15.7, trend: 4.1 },
  { id: "BN-03", segment: "B04", corridor: "Central Grid", occurrences: 14, duration: 19, severity: 51, delay: 10.2, trend: -2.3 },
  { id: "BN-04", segment: "G03", corridor: "South East", occurrences: 11, duration: 16, severity: 44, delay: 8.7, trend: 1.7 },
];

export const proposals: Proposal[] = [
  { id: "PROP-01", bottleneck: "E21 · Market Spine", intervention: "Additional through-capacity on the recurring constrained segment", rationale: "Recurring congestion is concentrated during the same hour-of-week windows.", segment: "E21", beforeDelay: 18.4, afterDelay: 13.1, improvement: 28.8, assumptions: ["Demand remains within the modeled range", "BPR parameters remain unchanged", "No downstream bottleneck is introduced"] },
  { id: "PROP-02", bottleneck: "A17 · North Corridor", intervention: "Redistribute demand toward Civic Link during recurring peak", rationale: "A17 has repeated high-severity congestion while an adjacent corridor retains spare capacity.", segment: "A17", beforeDelay: 15.7, afterDelay: 11.9, improvement: 24.2, assumptions: ["Alternate-route capacity is available", "Diversion behavior follows the modeled share", "Travel demand is otherwise stable"] },
];

export const backtest: BacktestMetric[] = [
  { horizon: 15, llmMae: 3.1, baselineMae: 3.7, llmRmse: 4.2, baselineRmse: 4.9, samples: 184 },
  { horizon: 30, llmMae: 4.5, baselineMae: 4.2, llmRmse: 5.9, baselineRmse: 5.5, samples: 184 },
  { horizon: 45, llmMae: 5.8, baselineMae: 5.4, llmRmse: 7.1, baselineRmse: 6.8, samples: 172 },
  { horizon: 60, llmMae: 6.4, baselineMae: 6.1, llmRmse: 7.8, baselineRmse: 7.4, samples: 160 },
];

export const healthTrend = [
  { time: "11:00", health: 82 }, { time: "11:30", health: 79 }, { time: "12:00", health: 84 },
  { time: "12:30", health: 77 }, { time: "13:00", health: 74 }, { time: "13:30", health: 69 },
  { time: "14:00", health: 63 }, { time: "14:30", health: 58 },
];

export const chatReplies = [
  { q: "Why is the North Corridor congested?", a: "A17 is at 59% of its free-flow speed and has an anomaly score of 2.8. The current signal is classified as non-recurring congestion, with a 91% confidence value.", evidence: ["A17", "14:21–14:33", "speed ratio 0.59"] },
  { q: "What is expected over the next 30 minutes?", a: "The current forecast expects the monitored corridor to remain in a severe state over the next 30 minutes. The LLM estimate is 32 km/h versus a 38 km/h baseline, with 82% confidence.", evidence: ["+30 min", "32 km/h", "82% confidence"] },
];
