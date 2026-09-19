import {
  advisories, backtest, bottlenecks, forecasts, forecastPoints, incidents, proposals, segments,
} from "../data/mock";

export const trafficService = {
  async getSegments() { return segments; },
  async getIncidents() { return incidents; },
  async getForecasts() { return forecasts; },
  async getForecastSeries() { return forecastPoints; },
  async getAdvisories() { return advisories; },
  async getBottlenecks() { return bottlenecks; },
  async getProposals() { return proposals; },
  async getBacktest() { return backtest; },
};
