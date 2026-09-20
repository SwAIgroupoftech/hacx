# TrafficSense

> Local pandas/numpy analysis produces compact evidence JSON. Groq (`openai/gpt-oss-120b`) evaluates that evidence: 15–60 minute forecasts, incident classes, diversions, and simulated infrastructure proposals.

**All outputs are advisory and simulated.** TrafficSense does not control signals, cameras, GPS, roadside sensors, or municipal infrastructure.

- **Hackathon:** NeuraX 3.0 · **Team:** HACX
- **Members:** G. Nachiketh, S. Somesh, S. Sai Satya, D. Kushal Sandeep

## Pipeline

```
data/raw  →  load_clean.py  →  FeatureBuilder (no look-ahead)
        →  anomaly / incident flags
        →  local forecasts (situation router: GBM / persistence / historical avg)
        →  diversions + bottleneck rank + BPR impact
        →  data/processed/evidence_*.json
        →  Groq (or template fallback)
        →  data/processed/report_*.json
        →  dashboard (map, forecast, advisories)
```

The LLM never sees raw tables. One call per scenario, cached under `outputs/llm_cache/`.

## Setup

```
pip install -r requirements.txt
cp .env.example .env    # set GROQ_API_KEY
python scripts/check_setup.py
```

```
# evidence + report without calling Groq
python -m src.pipeline.scenario --split validation --as-of "2026-01-16 16:40" --no-llm

# same, then Groq on the evidence packet
python -m src.pipeline.scenario --split validation --as-of "2026-01-16 16:40"

streamlit run src/app/dashboard.py
```

JSON reports land in `data/processed/`. The Advisories tab reads the latest file for the selected dataset.

## Local vs LLM forecasts

LightGBM is trained locally and used on **calm** roads. If a road is already congested, the packet uses **persistence**. If a labelled incident is active, it leans on the **historical average**. Groq may adjust those numbers only when the evidence supports it; failed or missing API calls fall back to the same local numbers.

## Safeguards

- Replay clock: analysis at time *t* uses data ≤ *t*.
- Structured Groq JSON + local validation (segment IDs, speed ≤ free-flow).
- Template fallback if the key is missing, the schema fails, or Groq returns 429.
- Advisories labelled **ADVISORY ONLY - SIMULATED**.
- Infrastructure labelled **SIMULATED ESTIMATE - NOT A CONSTRUCTION RECOMMENDATION**.
