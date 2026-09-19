# TrafficSense: Research Document

**Team HACX** | NeuraX 3.0 | Checkpoint 1 | Version 0.2

**Members:** G. Nachiketh, S. Somesh, S. Sai Satya, D. Kushal Sandeep

> Sections marked **TODO (after data inspection)** cannot be completed until we have examined the organizer datasets. They are left visible on purpose so this document shows what is known and what is still an assumption.

---

## 1. Problem statement (as given)

Build a software-only AI system that analyzes organizer-provided traffic and road-network datasets to create a continuously updated view of network conditions. The system should identify congestion and abnormal traffic behaviour, detect or classify incidents where the available data supports it, forecast traffic states 15-60 minutes ahead, generate evidence-based operational/diversion advisories, and propose data-driven infrastructure or road-network modifications for recurring bottlenecks together with estimated before/after traffic impact.

All actions, diversion plans and construction/network suggestions must remain simulated or advisory. No live signal control, camera access, GPS-device integration, roadside sensor integration, municipal infrastructure access or actual construction work is required or permitted for judging.

## 2. Our interpretation

### 2.1 Requirement decomposition

| # | Requirement | Our interpretation | Output |
|---|---|---|---|
| R1 | Continuously updated view | Replay the dataset in time order; at each step recompute the network state using only data seen so far | Per-segment state table that updates with a time slider |
| R2 | Congestion and abnormal behaviour | Congestion = low speed relative to the segment's own free-flow speed. Abnormal = deviating from that segment's normal pattern for that time of week | Congestion flags and anomaly scores |
| R3 | Incident detection/classification "where the data supports it" | Classify only when signals are sufficient; otherwise output "unclassified anomaly" or "insufficient evidence" | Incident records with type, confidence and rationale |
| R4 | Forecast 15-60 min ahead | Produce a forecast at +15, +30, +45, +60 min per segment, with confidence | Forecast table and accuracy per horizon |
| R5 | Evidence-based advisories | Each advisory cites the data that triggered it and states confidence and validity window | Advisory cards |
| R6 | Infrastructure modifications for *recurring* bottlenecks with before/after impact | Identify bottlenecks that recur, propose a modification, and estimate delay before vs after | Ranked proposals with impact ranges and assumptions |

### 2.2 Phrases we treat as evaluation hints

| Phrase | What we do about it |
|---|---|
| "continuously updated" | Replay with a time slider, not a one-shot analysis |
| "where the available data supports it" | Confidence values and an explicit abstain option |
| "evidence-based" | Every advisory lists the segments, values and timestamps behind it |
| "recurring bottlenecks" | Separate recurring from non-recurring congestion before proposing infrastructure changes |
| "simulated or advisory" | Labels on all outputs; no code path performs an action |

### 2.3 What we are deliberately not doing

- Not connecting to any live source or controlling any real system.
- Not training custom machine-learning models (see Section 4 for why).
- Not claiming real-world construction accuracy; impact estimates are model-based ranges.

## 3. Data (TODO after data inspection)

Complete this section once the datasets are in `data/raw/`.

| Item | Finding |
|---|---|
| Files provided | TODO |
| Time span and resolution | TODO |
| Number of road segments / nodes / edges | TODO |
| Columns (speed, flow, occupancy, etc.) | TODO |
| Road-network file with capacity, length, connectivity | TODO |
| Geometry / coordinates available | TODO |
| Incident labels present | TODO |
| Missing values, outliers, duplicates | TODO |
| Signs of injected anomalies (synthetic data often has them) | TODO |

### 3.1 Feasibility per requirement (fill in after inspection)

| Requirement | Supported by data? | Notes |
|---|---|---|
| R1 State view | TODO | |
| R2 Congestion/anomaly | TODO | |
| R3 Incident classification | TODO | Which incident types can actually be distinguished? |
| R4 Forecasting | TODO | Enough history to show typical daily patterns? |
| R5 Diversion advisories | TODO | Are there alternate routes in the graph? |
| R6 Network modification | TODO | Is capacity available, or must we assume it? |

### 3.2 Open questions for the organizers

1. What is the exact schema, time resolution and time span?
2. Are ground-truth incident labels included?
3. Is there a road-network file with capacities and connectivity?
4. Are external LLM APIs permitted, and may summaries of the dataset be sent to one?
5. What is the judging rubric and required submission format?

## 4. Approach and rationale

### 4.1 Why an LLM-driven design

We have 24 hours and limited experience building and tuning machine-learning models. Training, tuning and validating custom models is the riskiest use of that time. An LLM accessed through an API can reason over structured evidence immediately, can produce forecasts, classifications and readable advisories from the same input, and lets us spend our time on the parts judges see: the pipeline, the evidence trail, the dashboard and the impact analysis.

### 4.2 Division of work: code computes facts, LLM reasons

| Part | Responsibility | Why |
|---|---|---|
| Local Python code (pandas) | Cleaning, speed ratios, congestion flags, hour-of-week baselines, anomaly scores, bottleneck ranking, baseline forecasts, route candidates, BPR impact arithmetic | Deterministic, checkable, no API cost |
| External LLM | Forecast per horizon, incident classification with rationale, advisory writing, modification proposals, natural-language Q&A | Flexible reasoning and language over structured evidence |

The LLM never receives raw data. It receives compact evidence packets prepared by our code (Section 5.3), which keeps requests small, cheap and grounded.

### 4.3 Known limitations of LLM forecasting, and how we handle them

Research on LLM-based forecasting is mixed. Gruver et al. (2023) showed that LLMs can forecast time series zero-shot with competitive accuracy in some settings, and Jin et al. (2024) adapted LLMs for time-series forecasting. However, Tan et al. (2024) found that in several benchmarks language models add little over simpler methods. Our own risk is therefore not "will it work at all" but "will it beat simple baselines, and can we show it". We handle this with:

| Limitation | Mitigation |
|---|---|
| Non-deterministic output | Low temperature, response caching, fixed prompts |
| Numeric errors or implausible values | Range checks (non-negative, not above free-flow speed) |
| Hallucinated segments or numbers (Ji et al., 2023) | Every cited ID and number must exist in the evidence packet |
| May not beat a simple baseline | Give the LLM the baseline forecasts as an anchor, measure it in a backtest, report honestly |
| API failure, latency or rate limits | Cache, call only for flagged events, template fallback |
| Cost | Hard cap on calls per run, small evidence packets |

Grounding the model in retrieved or supplied evidence is the same principle as retrieval-augmented generation (Lewis et al., 2020): the model reasons over facts we provide rather than relying on memory.

## 5. Methodology

### 5.1 Ingestion and replay

- Validate schema, timestamps and value ranges; interpolate short gaps and flag long ones.
- Detect suspect sensors (flat-lined or impossible readings) so they are not mistaken for traffic events.
- A replay clock advances one interval at a time. Analysis uses only data at or before the current time, which prevents data leakage and mimics a live system.

### 5.2 Local analysis (deterministic)

- **Speed ratio** = current speed / segment free-flow speed, where free-flow speed is a high percentile of that segment's own observations.
- **Congestion flag:** speed ratio below a threshold for several consecutive intervals, to reduce noise. Level-of-service style bands are inspired by the Highway Capacity Manual (TRB) but use our own data-driven cut-offs.
- **Baseline:** median and MAD (median absolute deviation) per segment and time-of-week bucket, which are robust to outliers.
- **Anomaly score:** robust (modified) z-score against that baseline; values beyond about 3.5 are a common outlier convention (Iglewicz & Hoaglin, 1993). General background: Chandola et al. (2009).
- **Recurring vs non-recurring:** congestion that matches the baseline is *recurring* (rush hour); congestion that deviates is *non-recurring* (candidate incident).
- **Incident signals:** sudden speed drop, downstream flow drop, upstream slowdown, and flat-lined readings, each computed as a numeric signal.
- **Baseline forecasts:** persistence (last value carried forward) and historical average for that time of week.
- **Spillback:** using the road graph, check whether upstream segments slow down after a downstream segment becomes congested.

### 5.3 Evidence packets

One compact JSON object per segment, event or bottleneck. Illustrative example (final fields depend on the dataset):

```json
{
  "as_of": "2026-08-26T14:30:00",
  "segment_id": "S3",
  "free_flow_speed_kmh": 45.0,
  "current_speed_kmh": 15.8,
  "speed_ratio": 0.35,
  "last_60min_speeds_kmh": [44.1, 43.0, 41.5, 15.4, 15.9, 15.8],
  "typical_speed_now_kmh": 44.4,
  "anomaly": {"robust_z": -19.6, "duration_min": 20, "type": "non_recurring"},
  "signals": {
    "sudden_drop": true,
    "upstream_slowdown": {"segment_id": "S2", "speed_ratio": 0.62},
    "downstream_flow_drop": null,
    "flat_line_sensor_suspect": false
  },
  "baseline_forecast_kmh": {"15": 15.8, "30": 15.8, "45": 15.8, "60": 15.8},
  "historical_average_forecast_kmh": {"15": 44.0, "30": 43.5, "45": 42.0, "60": 40.5},
  "neighbours": ["S2", "S4"]
}
```

### 5.4 LLM tasks

| Task | Input | Required output (JSON) |
|---|---|---|
| Forecast | Evidence packet | Per horizon (15/30/45/60): predicted speed, congestion state, confidence |
| Incident classification | Evidence packet with signals | Type (blockage/crash, event surge, weather effect, sensor fault, unclassified), confidence, rationale citing signals |
| Advisory | Forecast + incident + route candidates | Trigger, evidence, affected segments, action, expected saving, confidence, valid-until, label |
| Modification proposal | Bottleneck evidence | Candidate intervention, reasoning, assumptions |
| Q&A | Recent evidence packets | Answer citing segment IDs and values |

Prompt design principles: fixed JSON schema in the instructions, a small number of worked examples, an explicit instruction to abstain ("insufficient evidence") when signals are weak, and a requirement to cite segment IDs and values from the packet.

### 5.5 Validation layer

Every LLM response is checked before use:

1. Valid JSON that matches the schema.
2. Values in a plausible range.
3. Every segment ID and number cited exists in the evidence packet.
4. On failure or API error: retry once, then fall back to the baseline forecast and a template advisory.

### 5.6 Diversion routing

- Model the network as a weighted directed graph (`networkx`) with edge weights based on expected travel time.
- Find k alternate paths with Yen's algorithm (Yen, 1971).
- Exclude alternates that are already near capacity, so the advisory does not simply move the jam.
- The LLM turns the ranked alternates into a written advisory; the route and time-saving numbers come from code.

### 5.7 Recurring-bottleneck analysis and impact estimate

1. Rank bottlenecks by frequency, duration and severity, expressed as vehicle-hours of delay where flow data allows.
2. The LLM proposes candidate interventions the data can justify (add lane, turn bay, signal retiming, bypass link, movement restriction).
3. **Impact is computed in code** with the BPR volume-delay function from the U.S. Bureau of Public Roads (1964): `t = t0 * (1 + 0.15 * (v/c)^4)`. We modify capacity or add a link, recompute travel time and delay, and compare before vs after.
4. Adding capacity can sometimes worsen network-wide performance (Braess, 1968), so we compare network-wide delay, not only the improved segment.
5. Results are reported as ranges with a sensitivity check on demand and capacity assumptions, and labelled simulated.

## 6. Evaluation plan

| Module | Metric | Compared against |
|---|---|---|
| LLM forecasts | MAE per horizon (15/30/45/60) on a sample of past timestamps, replayed with no look-ahead | Persistence, historical average |
| Anomaly detection | Precision/recall against labels or injected anomalies; false alarms per day | Fixed-threshold rule |
| Incident classification | Agreement with labels where available; abstain rate | Rules-only |
| LLM reliability | Valid-JSON rate, validation-pass rate, fallback rate, latency, calls per run | Targets set during development |
| Advisories | Share with complete evidence and valid citations; simulated time saved | No-advisory case |
| Network modification | Delay reduction range under sensitivity scenarios | Do-nothing scenario |

If the LLM does not beat a baseline at some horizon, we report that plainly and use the better method for that horizon. Reporting this honestly is part of the result.

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Data does not support some requirement (for example, no labels) | State it clearly; use rule-based signals and explicit confidence |
| LLM forecasts are worse than baselines | Anchor on baselines, measure in backtest, use fallback per horizon |
| LLM hallucination | Structured inputs, citation requirement, automated cross-checks |
| API outage, rate limits or slow responses during demo | Response cache, template fallback, recorded backup demo |
| API cost | Call only for flagged events and top bottlenecks; cap calls per run |
| Impact estimates look arbitrary | Computed in code with a stated formula, assumptions and sensitivity ranges |
| Data sharing rules | Confirm with organizers; send only compact summaries, never raw files |
| Scope too large for 24 hours | Follow the priority order in Section 8 |

## 8. Plan and priorities

Priority order if time runs short:
1. Ingestion, cleaning and replay clock
2. Congestion and anomaly detection (recurring vs non-recurring)
3. Evidence packets and LLM advisories with validation and fallback
4. LLM forecasts with baseline comparison
5. Dashboard with time slider and alert feed
6. Bottleneck proposals with BPR before/after estimate
7. Q&A chat and polish

| Hours | Focus | Suggested owner |
|---|---|---|
| 0-3 | Inspect datasets, document schema, update config | All |
| 3-8 | Local analysis: cleaning, congestion, baselines, anomalies | S. Sai Satya |
| 3-8 | Road graph, routing candidates, bottleneck ranking | D. Kushal Sandeep |
| 8-13 | LLM layer: evidence packets, prompts, validation, cache, fallback | G. Nachiketh |
| 8-18 | Dashboard: replay slider, alerts, advisory cards, report, chat | S. Somesh |
| 13-18 | BPR before/after estimates | D. Kushal Sandeep |
| 18-22 | Backtest, bug fixes, integration testing | All |
| 22-24 | Freeze features, finalize docs, rehearse demo, backup recording | All |

*Owners are suggestions; adjust to your actual split.*

## 9. Ethics and constraints

- Advisory and simulated only; there is no code path that executes actions on real infrastructure (`ADVISORY_ONLY=true`).
- No personal or device-level data is used or required.
- LLM outputs are validated, labelled as advisory, and never trigger actions.
- Limitations of the synthetic data and of each estimate are stated in the outputs.

## 10. Decision log

| Decision | Reason | Trade-off accepted |
|---|---|---|
| Use an external LLM for forecasting, classification, advisories and Q&A | 24-hour limit and limited ML experience; fastest route to a complete system | Non-deterministic, may not beat baselines, depends on the API |
| Local code computes all facts and feeds the LLM evidence packets | Keeps answers grounded and cheap; makes numbers checkable | Extra engineering for the evidence layer |
| Give the LLM baseline forecasts as an anchor | Gives a floor on quality and something to compare against | Slightly constrains the LLM's answers |
| Validate every LLM answer and fall back to baselines/templates | Demo must not fail if the API or an answer is bad | More code, and fallback answers are less rich |
| Compute impact with BPR in code | Transparent, defensible numbers | Simplified traffic model; results reported as ranges |
