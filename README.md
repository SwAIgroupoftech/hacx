# TrafficSense

> An AI-powered traffic intelligence system. Local analysis code turns road-network data into compact statistical evidence, and an LLM uses that evidence to forecast traffic 15-60 minutes ahead, classify incidents, and write evidence-based advisories and network-improvement proposals.

**All outputs are advisory and simulated.** TrafficSense does not control signals, access cameras, GPS devices, roadside sensors, or municipal infrastructure, and it does not trigger any real-world action.

- **Hackathon:** NeuraX 3.0
- **Team:** HACX
- **Members:** G. Nachiketh, S. Somesh, S. Sai Satya, D. Kushal Sandeep
- **Status:** Checkpoint 1: planning, repository structure, configuration and research complete. Implementation in progress.

---

## 1. Problem

Build a software-only AI system that analyzes organizer-provided traffic and road-network datasets to:

| # | Requirement |
|---|---|
| 1 | Maintain a continuously updated view of network conditions |
| 2 | Identify congestion and abnormal traffic behaviour |
| 3 | Detect or classify incidents where the data supports it |
| 4 | Forecast traffic states 15-60 minutes ahead |
| 5 | Generate evidence-based operational/diversion advisories |
| 6 | Propose data-driven infrastructure/network changes for recurring bottlenecks, with estimated before/after impact |

## 2. Our approach

Given a 24-hour build window, we use an **LLM-driven architecture**: we do not train custom machine-learning models. Instead, the work is split between two parts:

| Part | Responsibility |
|---|---|
| **Local analysis code** (Python, pandas) | Cleans the data and computes the facts: speed ratios, congestion flags, normal-pattern baselines, anomaly scores, bottleneck rankings, simple baseline forecasts, candidate alternate routes |
| **External LLM** (API) | Reasons over those facts: forecasts 15/30/45/60 min ahead, classifies incidents, writes advisories, proposes network changes, and answers questions in plain language |

The LLM never sees raw data dumps. It receives small **evidence packets** (compact JSON) prepared by our code, so its answers stay grounded in real numbers.

```
Datasets
   |
   v
Load & clean (pandas)
   |
   v
Local statistical analysis
  - speed ratio, congestion flags
  - hour-of-week baselines, anomaly scores
  - recurring vs non-recurring congestion
  - bottleneck ranking
  - baseline forecasts (persistence, historical average)
  - alternate-route candidates
   |
   v
Evidence packets (compact JSON, one per segment / event / bottleneck)
   |
   v
LLM (external API)
  - forecast 15/30/45/60 min + confidence
  - incident classification (or "unclassified")
  - advisories and diversion suggestions
  - network-modification proposals
  - natural-language Q&A
   |
   v
Validation layer (schema, value ranges, real segment IDs, fallback to baselines)
   |
   v
Dashboard (replay slider, alert feed, advisory cards, bottleneck report, chat)
```

### Key design decisions

- **Replay clock with no look-ahead.** At simulated time *t* the system only sees data up to *t*, which gives the "continuously updated" view.
- **Recurring vs non-recurring congestion** are separated using per-segment hour-of-week baselines. Non-recurring congestion becomes an incident alert; recurring congestion feeds the infrastructure proposals.
- **The LLM is called on demand,** for flagged windows and top bottlenecks only, not for every row. Responses are cached so the demo is fast and repeatable.
- **Impact estimates are computed in code** with a simple, transparent formula (BPR volume-delay function), so before/after numbers are traceable. The LLM proposes the intervention and explains the result.
- **Honest confidence.** Every forecast and classification carries a confidence value, and "unclassified anomaly / insufficient evidence" is a valid output.

## 3. How each requirement is met

| # | Requirement | How we address it |
|---|---|---|
| 1 | Continuously updated view | Replay clock steps through the data in time order; analysis is recomputed for data up to the current time; dashboard slider moves through time |
| 2 | Congestion and abnormal behaviour | Local code: speed relative to each road's free-flow speed, plus robust z-score against the normal pattern for that time of week |
| 3 | Incident detection/classification | Local code computes signals (sudden speed drop, upstream slowdown, flat-lined sensor); the LLM classifies from them and may answer "unclassified" |
| 4 | Forecast 15-60 min ahead | The LLM receives recent trend, typical pattern, and baseline forecasts, and returns a forecast per horizon with a confidence value |
| 5 | Evidence-based advisories | The LLM writes structured advisories that cite the triggering segments, values and timestamps; alternate routes come from the road graph when a network file is available |
| 6 | Network modifications with before/after impact | Bottlenecks ranked by frequency, duration and severity; the LLM proposes candidate changes; code computes before/after delay with BPR; results shown as ranges with assumptions |

## 4. Safeguards for LLM outputs

Because LLM output can be inconsistent, every response passes through checks before it reaches the dashboard:

1. **Structured output.** The LLM must return JSON matching a fixed schema; anything else is rejected.
2. **Range checks.** Forecast values must be physically plausible (for example, non-negative and not above the segment's free-flow speed).
3. **Reference checks.** Every segment ID and number cited must exist in the evidence packet.
4. **Fallback.** If a check fails or the API is unavailable, the system falls back to the baseline forecast and template-based advisories.
5. **Measured accuracy.** We replay a sample of historical timestamps (using only data up to each time), compare LLM forecasts against actual values and against the simple baselines, and report the results honestly, including where the LLM does not beat the baseline.
6. **Low temperature and caching** for consistent, repeatable results.

## 5. Tech stack

| Area | Tools |
|---|---|
| Language | Python 3.14+ |
| Data analysis | pandas, numpy, scipy |
| Graph / routing | networkx |
| LLM | External LLM API, JSON in / JSON out |
| Backend | FastAPI |
| Dashboard | Streamlit + Plotly |
| Config | YAML (`config/config.yaml`) + `.env` |

## 6. Project structure

```
traffic-ai/
├── README.md
├── .env.example           
├── .gitignore
├── requirements.txt
├── config/
│   └── config.yaml         # thresholds and settings
├── docs/
│   └── RESEARCH.md         # research document
├── data/
│   ├── raw/                # organizer datasets go here (not committed)
│   └── processed/          # cleaned/derived data (not committed)
├── src/
│   ├── ingestion/          # loading, cleaning, replay clock
│   ├── state/              # speed ratio, rolling windows
│   ├── detection/          # congestion, anomalies, incident signals
│   ├── forecasting/        # baseline forecasts, LLM forecast, backtest
│   ├── advisory/           # evidence packets, diversion routing, advisories
│   ├── network_mod/        # bottleneck ranking, BPR before/after calculation
│   ├── llm/                # prompts, API client, caching, validation, fallbacks
│   └── app/                # FastAPI backend and Streamlit dashboard
├── scripts/
│   ├── check_setup.py      # verifies your environment
│   └── make_practice_data.py   # synthetic practice data
├── notebooks/              # data exploration
├── tests/
└── outputs/                # generated results and LLM cache (not committed)
```

## 7. Setup

### Prerequisites

- Python 3.10 or newer
- Git
- An LLM API key (without one, the system uses template-based advisories and baseline forecasts)

### Configuration

| File | Contains | Committed? |
|---|---|---|
| `.env` | API key, paths, ports, safety flag | **No**, never |
| `.env.example` | Template with placeholder values | Yes |
| `config/config.yaml` | Thresholds, horizons, LLM and simulation settings | Yes |

Change thresholds in `config.yaml`, not in code, so results stay reproducible.

## 8. Roadmap

- [x] Problem analysis and requirement mapping
- [x] Repository structure, configuration, environment template
- [x] Research document
- [ ] Dataset inspection and schema documentation
- [ ] Ingestion, cleaning and replay clock
- [ ] Congestion and anomaly detection (recurring vs non-recurring)
- [ ] Evidence packets and LLM prompt/response schema
- [ ] LLM forecasting, incident classification and advisories
- [ ] Validation layer, caching and template fallback
- [ ] Backtest: LLM forecasts vs baselines
- [ ] Bottleneck ranking and BPR before/after impact
- [ ] Dashboard and Q&A chat
- [ ] Demo script and backup recording

## 9. Constraints and responsible use

- Software-only: no live signal control, camera access, GPS integration, roadside sensor integration, municipal infrastructure access, or construction work.
- Every advisory carries the label **ADVISORY ONLY - SIMULATED**.
- Every infrastructure proposal carries the label **SIMULATED ESTIMATE - NOT A CONSTRUCTION RECOMMENDATION**.
- The `ADVISORY_ONLY=true` flag in `.env` must not be changed.
- Dataset content is provided by the organizers and is only sent to the LLM as compact summaries; it is not redistributed through this repository.
- LLM outputs can be imperfect; they are validated, labelled as advisory, and never trigger actions.

