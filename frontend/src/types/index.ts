export type TrafficState = "normal" | "moderate" | "severe" | "incident" | "recurring" | "anomalous";
export type ValidationState = "VALIDATED" | "REJECTED" | "FALLBACK" | "UNCLASSIFIED" | "INSUFFICIENT EVIDENCE";

export interface Segment {
  id: string;
  name: string;
  corridor: string;
  speed: number;
  freeFlow: number;
  speedRatio: number;
  anomalyScore: number;
  state: TrafficState;
  timestamp: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Incident {
  id: string;
  timestamp: string;
  segment: string;
  type: string;
  severity: "low" | "medium" | "high";
  confidence: number;
  evidence: string[];
  status: "active" | "classified" | "unclassified" | "resolved";
  validation: ValidationState;
}

export interface ForecastPoint {
  time: string;
  actual?: number;
  baseline?: number;
  llm?: number;
}

export interface Forecast {
  horizon: number;
  value: number;
  confidence: number;
  baseline: number;
  state: "stable" | "moderate" | "severe";
}

export interface Advisory {
  id: string;
  title: string;
  timestamp: string;
  segments: string[];
  reason: string;
  evidence: string[];
  action: string;
  confidence: number;
  validation: ValidationState;
}

export interface Bottleneck {
  id: string;
  segment: string;
  corridor: string;
  occurrences: number;
  duration: number;
  severity: number;
  delay: number;
  trend: number;
}

export interface Proposal {
  id: string;
  bottleneck: string;
  intervention: string;
  rationale: string;
  segment: string;
  beforeDelay: number;
  afterDelay: number;
  improvement: number;
  assumptions: string[];
}

export interface BacktestMetric {
  horizon: number;
  llmMae: number;
  baselineMae: number;
  llmRmse: number;
  baselineRmse: number;
  samples: number;
}
