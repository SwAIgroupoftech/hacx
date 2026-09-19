import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ChevronRight, Pause, Play, RotateCcw, Search, Send, SkipBack, SkipForward, TrendingDown, TrendingUp } from "lucide-react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, ReferenceLine } from "recharts";
import { advisories, backtest, bottlenecks, chatReplies, forecastPoints, forecasts, healthTrend, incidents, proposals, segments } from "./data/mock";
import { Badge, Card, EmptyState, MetricCard, SimulatedLabel, ValidationBadge } from "./components/ui";
import { TrafficNetworkMap } from "./components/TrafficNetworkMap";

const stateTone = (s: string) => ["severe", "incident"].includes(s) ? "danger" : ["moderate", "recurring", "anomalous"].includes(s) ? "warning" : "success";

export function Overview() {
  return (
    <div className="space-y-6">
      <section className="hero">
        <div className="hero-grid" />
        <div className="hero-copy">
          <div className="eyebrow">CITY NETWORK / CURRENT WINDOW</div>
          <h1>Network overview<span>.</span></h1>
          <p>Observe congestion, anomalies, incidents and forecasted traffic states across the simulated network.</p>
          <div className="hero-meta"><span><i className="status-dot" /> DATASET READY</span><span>NO LOOK-AHEAD</span><span>WINDOW · 14:20—14:35</span></div>
        </div>
        <div className="hero-time"><span>SIMULATED TIME</span><strong>14:35</strong><small>Saturday · replay</small></div>
      </section>

      <div className="metric-grid">
        <MetricCard label="Network health" value="58 / 100" detail="−6.4 vs 30 min" trend="-6.4" critical />
        <MetricCard label="Congested segments" value="12" detail="of 84 monitored" trend="+3" />
        <MetricCard label="Active incidents" value="2" detail="1 classified · 1 watch" />
        <MetricCard label="Average speed" value="41 km/h" detail="−8.7% vs baseline" trend="+8.7" />
        <MetricCard label="Critical bottlenecks" value="4" detail="recurring patterns" />
      </div>

      <div className="dashboard-grid">
        <Card title="City network" action={<Link to="/network" className="panel-link">Open network <ArrowRight size={14} /></Link>} className="network-panel">
          <TrafficNetworkMap segments={segments} />
        </Card>
        <Card title="Alert feed" action={<Link to="/incidents" className="panel-link">All incidents <ArrowRight size={14} /></Link>}>
          <div className="alert-list">
            {incidents.map((i) => (
              <div className="alert-row" key={i.id}>
                <div className={`alert-marker ${i.severity}`} />
                <div className="alert-content">
                  <div className="alert-top"><span>{i.timestamp}</span><Badge tone={i.severity === "high" ? "danger" : i.severity === "medium" ? "warning" : "neutral"}>{i.type}</Badge></div>
                  <strong>{i.segment}</strong>
                  <p>{i.evidence[0]}</p>
                </div>
                <span className="confidence">{i.confidence}%</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="two-col">
        <Card title="Forecast · corridor speed" action={<Link to="/forecasts" className="panel-link">Open forecast <ArrowRight size={14} /></Link>}>
          <div className="chart-legend"><span><i className="legend-line actual" /> Historical</span><span><i className="legend-line baseline" /> Baseline</span><span><i className="legend-line llm" /> LLM forecast</span></div>
          <div className="chart"><ResponsiveContainer width="100%" height={260}><LineChart data={forecastPoints}><CartesianGrid stroke="var(--chart-grid)" vertical={false} /><XAxis dataKey="time" stroke="var(--chart-text)" tickLine={false} axisLine={false} /><YAxis stroke="var(--chart-text)" tickLine={false} axisLine={false} unit=" km/h" width={65} /><Tooltip contentStyle={{ background: "var(--surface-elevated)", border: "1px solid var(--border)", borderRadius: 4 }} /><Line type="monotone" dataKey="actual" stroke="var(--text)" strokeWidth={2} dot={false} /><Line type="monotone" dataKey="baseline" stroke="var(--chart-muted)" strokeWidth={1.5} strokeDasharray="5 5" dot={false} /><Line type="monotone" dataKey="llm" stroke="var(--danger)" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div>
        </Card>
        <Card title="Network health" action={<span className="micro-label">LAST 4 HOURS</span>}>
          <div className="chart"><ResponsiveContainer width="100%" height={260}><LineChart data={healthTrend}><CartesianGrid stroke="var(--chart-grid)" vertical={false} /><XAxis dataKey="time" stroke="var(--chart-text)" tickLine={false} axisLine={false} /><YAxis domain={[40, 100]} stroke="var(--chart-text)" tickLine={false} axisLine={false} width={30} /><Tooltip contentStyle={{ background: "var(--surface-elevated)", border: "1px solid var(--border)", borderRadius: 4 }} /><Line type="monotone" dataKey="health" stroke="var(--text)" strokeWidth={2} dot={false} /></LineChart></ResponsiveContainer></div>
        </Card>
      </div>

      <div className="two-col">
        <Card title="Top bottlenecks" action={<Link to="/bottlenecks" className="panel-link">View report <ArrowRight size={14} /></Link>}>
          <div className="compact-list">
            {bottlenecks.slice(0, 3).map((b, idx) => <div className="compact-row" key={b.id}><span className="rank">0{idx + 1}</span><div><strong>{b.segment} · {b.corridor}</strong><span>{b.occurrences} occurrences · {b.duration} min avg</span></div><strong>{b.delay} min</strong></div>)}
          </div>
        </Card>
        <Card title="Recent advisories" action={<Link to="/advisories" className="panel-link">View all <ArrowRight size={14} /></Link>}>
          <div className="compact-list">{advisories.slice(0, 3).map((a) => <div className="compact-row" key={a.id}><span className="severity-bar" /><div><strong>{a.title}</strong><span>{a.timestamp} · {a.segments.join(", ")}</span></div><span className="confidence">{a.confidence}%</span></div>)}</div>
        </Card>
      </div>
    </div>
  );
}

export function Network() {
  const [filter, setFilter] = useState("All");
  const filtered = segments.filter((s) => filter === "All" || s.state === filter.toLowerCase());
  return <div className="space-y-6">
    <PageIntro eyebrow="LIVE NETWORK" title="Observe the road network." description="Inspect segment-level conditions, anomaly scores and the evidence behind the current state." />
    <div className="network-layout">
      <Card title="Network state" className="network-large"><TrafficNetworkMap segments={segments} height={540} /></Card>
      <Card title="Segment monitor" action={<div className="filter-pills">{["All", "Normal", "Moderate", "Severe", "Incident", "Recurring"].map(f => <button key={f} className={filter === f ? "selected" : ""} onClick={() => setFilter(f)}>{f}</button>)}</div>}>
        <div className="table-wrap"><table><thead><tr><th>Segment</th><th>State</th><th>Speed</th><th>Ratio</th><th>Anomaly</th><th>Time</th></tr></thead><tbody>{filtered.map(s => <tr key={s.id}><td><strong>{s.id}</strong><span className="table-sub">{s.name}</span></td><td><Badge tone={stateTone(s.state)}>{s.state}</Badge></td><td>{s.speed} km/h</td><td>{s.speedRatio.toFixed(2)}</td><td>{s.anomalyScore.toFixed(1)}</td><td>{s.timestamp}</td></tr>)}</tbody></table></div>
      </Card>
    </div>
  </div>;
}

export function Replay() {
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(58);
  return <div className="space-y-6">
    <PageIntro eyebrow="REPLAY CLOCK" title="Move through the city timeline." description="Replay historical windows without look-ahead. Analysis only uses observations available at the selected simulated time." />
    <Card className="replay-card">
      <div className="replay-head"><div><div className="eyebrow">SIMULATED TIME</div><div className="replay-time">14:{String(Math.round(time)).padStart(2, "0")}:00</div></div><Badge tone="info">NO LOOK-AHEAD</Badge></div>
      <div className="timeline-wrap"><div className="timeline-labels"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:59</span></div><input aria-label="Replay time" type="range" min="0" max="59" value={time} onChange={e => setTime(Number(e.target.value))} /><div className="timeline-window"><span>CURRENT WINDOW</span><strong>14:20 → 14:{String(Math.round(time)).padStart(2, "0")}</strong></div></div>
      <div className="replay-controls"><button className="control-btn" onClick={() => setTime(0)}><RotateCcw size={16} /> Reset</button><button className="control-btn"><SkipBack size={16} /> Previous</button><button className="play-btn" onClick={() => setPlaying(!playing)}>{playing ? <Pause size={17} /> : <Play size={17} />}{playing ? "Pause" : "Play"}</button><button className="control-btn"><SkipForward size={16} /> Next</button><div className="speed-control"><span>Playback</span>{["0.5x", "1x", "2x", "5x"].map((x, i) => <button key={x} className={i === 1 ? "selected" : ""}>{x}</button>)}</div></div>
    </Card>
    <div className="two-col"><Card title="Replay snapshot"><div className="metric-grid compact"><MetricCard label="Congested segments" value="12" detail="current window" /><MetricCard label="Active incidents" value="2" detail="validated + watch" /></div></Card><Card title="Replay principle"><div className="principle"><div className="principle-line" /><div><strong>No look-ahead</strong><p>At simulated time T, only data available up to T is used. Forecasts are displayed separately from observed traffic.</p></div></div></Card></div>
  </div>;
}

export function Incidents() {
  const [selected, setSelected] = useState(incidents[0]);
  return <div className="space-y-6"><PageIntro eyebrow="INCIDENT INTELLIGENCE" title="Find the abnormal signals." description="Review incident classifications, unclassified anomalies and the evidence that supports each result." />
    <div className="two-col incident-grid"><Card title="Event feed"><div className="incident-list">{incidents.map(i => <button key={i.id} onClick={() => setSelected(i)} className={`incident-item ${selected.id === i.id ? "selected" : ""}`}><div className={`incident-dot ${i.severity}`} /><div><div className="incident-meta">{i.timestamp} · {i.segment}</div><strong>{i.type}</strong><p>{i.evidence[0]}</p></div><span>{i.confidence}%</span></button>)}</div></Card>
    <Card title="Evidence panel"><div className="evidence-head"><div><div className="eyebrow">{selected.id}</div><h2>{selected.type}</h2></div><ValidationBadge state={selected.validation} /></div><div className="evidence-grid"><div><span>Segment</span><strong>{selected.segment}</strong></div><div><span>Confidence</span><strong>{selected.confidence}%</strong></div><div><span>Severity</span><strong>{selected.severity}</strong></div><div><span>Status</span><strong>{selected.status}</strong></div></div><div className="evidence-list">{selected.evidence.map((e, i) => <div key={i}><span>{String(i + 1).padStart(2, "0")}</span><p>{e}</p></div>)}</div><SimulatedLabel /></Card></div>
  </div>;
}

export function Forecasts() {
  return <div className="space-y-6"><PageIntro eyebrow="FORECASTING" title="What happens next?" description="Compare the LLM forecast against transparent baselines across 15–60 minute horizons." />
    <div className="forecast-grid">{forecasts.map(f => <div className="forecast-card" key={f.horizon}><span>+{f.horizon} MIN</span><strong>{f.value} <small>km/h</small></strong><div className="forecast-baseline">baseline {f.baseline} km/h</div><div className="confidence-bar"><i style={{ width: `${f.confidence}%` }} /></div><div className="forecast-foot"><span>{f.confidence}% confidence</span><Badge tone={f.state === "severe" ? "danger" : "warning"}>{f.state}</Badge></div></div>)}</div>
    <Card title="Forecast trajectory"><div className="chart"><ResponsiveContainer width="100%" height={360}><LineChart data={forecastPoints}><CartesianGrid stroke="var(--chart-grid)" vertical={false} /><XAxis dataKey="time" stroke="var(--chart-text)" tickLine={false} axisLine={false} /><YAxis stroke="var(--chart-text)" tickLine={false} axisLine={false} unit=" km/h" /><Tooltip contentStyle={{ background: "var(--surface-elevated)", border: "1px solid var(--border)" }} /><Line dataKey="actual" name="Historical" stroke="var(--text)" strokeWidth={2} dot={false} /><Line dataKey="baseline" name="Baseline" stroke="var(--chart-muted)" strokeDasharray="5 5" dot={false} /><Line dataKey="llm" name="LLM Forecast" stroke="var(--danger)" strokeWidth={2.5} dot={false} /></LineChart></ResponsiveContainer></div></Card>
    <Card title="Forecast validation"><div className="validation-summary"><div><span>Validation mode</span><strong>Historical replay</strong></div><div><span>Horizons</span><strong>15 / 30 / 45 / 60 min</strong></div><div><span>Fallback</span><strong>Baseline forecast</strong></div><div><span>Evidence</span><strong>Compact JSON packets</strong></div></div><p className="note">Demo values are illustrative. The product should report cases where the LLM does not outperform a baseline.</p></Card>
  </div>;
}

export function Advisories() {
  return <div className="space-y-6"><PageIntro eyebrow="ADVISORY CENTER" title="Evidence before action." description="Structured, simulated advisories grounded in segment values, timestamps and confidence." />
    <div className="advisory-grid">{advisories.map(a => <Card key={a.id} className="advisory-card"><div className="advisory-top"><div><div className="eyebrow">{a.id} · {a.timestamp}</div><h2>{a.title}</h2></div><ValidationBadge state={a.validation} /></div><div className="advisory-section"><span>REASON</span><p>{a.reason}</p></div><div className="advisory-section"><span>EVIDENCE</span>{a.evidence.map((e,i)=><p className="evidence-row" key={i}>{e}</p>)}</div><div className="advisory-action"><span>RECOMMENDED DIVERSION / ACTION</span><strong>{a.action}</strong></div><div className="advisory-bottom">
  <div className="advisory-confidence">
    <div className="advisory-confidence-head">
      <span>CONFIDENCE</span>
      <strong>{a.confidence}%</strong>
    </div>

    <div className="advisory-confidence-bar">
      <i style={{ width: `${a.confidence}%` }} />
    </div>
  </div>

  <SimulatedLabel />
</div></Card>)}</div>
  </div>;
}

export function Bottlenecks() {
  return <div className="space-y-6"><PageIntro eyebrow="BOTTLENECK ANALYSIS" title="Where does congestion repeat?" description="Recurring bottlenecks are ranked by frequency, duration and severity." />
    <Card title="Recurring bottlenecks"><div className="table-wrap"><table><thead><tr><th>Rank</th><th>Segment</th><th>Corridor</th><th>Occurrences</th><th>Avg duration</th><th>Severity</th><th>Delay</th><th>Trend</th></tr></thead><tbody>{bottlenecks.map((b,i)=><tr key={b.id}><td className="rank">0{i+1}</td><td><strong>{b.segment}</strong></td><td>{b.corridor}</td><td>{b.occurrences}</td><td>{b.duration} min</td><td><div className="severity-meter"><i style={{width:`${b.severity}%`}} /></div></td><td>{b.delay} min</td><td className={b.trend > 0 ? "text-danger" : "text-success"}>{b.trend > 0 ? "+" : ""}{b.trend}%</td></tr>)}</tbody></table></div></Card>
    <div className="two-col"><Card title="Bottleneck methodology"><div className="method-flow"><span>Frequency</span><i>+</i><span>Duration</span><i>+</i><span>Severity</span><i>→</i><strong>Recurring ranking</strong></div><p className="note">Recurring congestion is separated from non-recurring events using hour-of-week baselines.</p></Card><Card title="Interpretation"><p className="large-note">High recurrence does not automatically imply an infrastructure intervention. Proposals remain simulated estimates and expose their assumptions.</p></Card></div>
  </div>;
}

export function Proposals() {
  return <div className="space-y-6"><PageIntro eyebrow="NETWORK IMPROVEMENT" title="Model the before / after." description="Simulated network-change proposals with transparent BPR impact estimates and assumptions." />
    <div className="proposal-grid">{proposals.map(p => <Card key={p.id} className="proposal-card"><div className="proposal-head"><div><div className="eyebrow">{p.id} · {p.segment}</div><h2>{p.intervention}</h2></div><Badge tone="warning">SIMULATED</Badge></div><p>{p.rationale}</p><div className="impact-grid"><div><span>Current delay</span><strong>{p.beforeDelay} min</strong></div><div><span>Simulated after</span><strong>{p.afterDelay} min</strong></div><div className="impact"><span>Estimated difference</span><strong>−{p.improvement}%</strong></div></div><div className="assumptions"><span>ASSUMPTIONS</span>{p.assumptions.map((a,i)=><div key={i}>— {a}</div>)}</div><SimulatedLabel construction /></Card>)}</div>
  </div>;
}

export function Backtest() {
  const chartData = backtest.map(b => ({ horizon: `+${b.horizon}m`, LLM: b.llmMae, Baseline: b.baselineMae }));
  return <div className="space-y-6"><PageIntro eyebrow="ACCURACY / BACKTEST" title="Measure it honestly." description="Historical replay compares LLM forecasts with persistence and historical-average baselines." />
    <Card title="Mean absolute error"><div className="chart"><ResponsiveContainer width="100%" height={330}><BarChart data={chartData}><CartesianGrid stroke="var(--chart-grid)" vertical={false} /><XAxis dataKey="horizon" stroke="var(--chart-text)" tickLine={false} axisLine={false} /><YAxis stroke="var(--chart-text)" tickLine={false} axisLine={false} /><Tooltip contentStyle={{ background: "var(--surface-elevated)", border: "1px solid var(--border)" }} /><Bar dataKey="LLM" fill="var(--danger)" radius={[2,2,0,0]} /><Bar dataKey="Baseline" fill="var(--chart-muted)" radius={[2,2,0,0]} /></BarChart></ResponsiveContainer></div></Card>
    <Card title="Evaluation detail"><div className="table-wrap"><table><thead><tr><th>Horizon</th><th>LLM MAE</th><th>Baseline MAE</th><th>LLM RMSE</th><th>Baseline RMSE</th><th>Samples</th></tr></thead><tbody>{backtest.map(b=><tr key={b.horizon}><td><strong>+{b.horizon} min</strong></td><td>{b.llmMae}</td><td>{b.baselineMae}</td><td>{b.llmRmse}</td><td>{b.baselineRmse}</td><td>{b.samples}</td></tr>)}</tbody></table></div><p className="note">TrafficSense compares LLM forecasts against simple baselines to measure whether the additional reasoning improves forecasting performance. These values are demo data.</p></Card>
  </div>;
}

export function Ask() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<{q:string; a:string; evidence:string[]}[]>([]);
  const send = () => {
    if (!query.trim()) return;
    const match = chatReplies.find(x => query.toLowerCase().includes(x.q.toLowerCase().slice(0, 18)));
    setMessages([...messages, match ?? { q: query, a: "The current evidence packet does not contain enough validated information to answer that question. Try asking about congestion, forecasts, recurring bottlenecks or incident evidence.", evidence: ["INSUFFICIENT EVIDENCE"] }]);
    setQuery("");
  };
  return <div className="space-y-6"><PageIntro eyebrow="ASK TRAFFICSENSE" title="Query the evidence." description="Ask natural-language questions about the simulated traffic state. Responses should remain grounded in the available evidence." />
    <div className="chat-layout"><Card className="chat-card"><div className="suggestions">{["Why is the North Corridor congested?", "What is expected over the next 30 minutes?", "Which bottlenecks are recurring?", "Show evidence for the current incident classification."].map(q=><button key={q} onClick={()=>setQuery(q)}>{q}<ChevronRight size={14}/></button>)}</div><div className="chat-messages">{messages.length===0 ? <EmptyState title="No questions yet" description="Choose a suggested question or write your own below." /> : messages.map((m,i)=><div className="chat-thread" key={i}><div className="chat-q"><span>YOU</span>{m.q}</div><div className="chat-a"><div className="bot-icon"><BrainCircuit size={15}/></div><div><p>{m.a}</p><div className="evidence-chips">{m.evidence.map(e=><span key={e}>{e}</span>)}</div></div></div></div>)}</div><div className="chat-input"><input value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>e.key==="Enter"&&send()} placeholder="Ask about the current traffic evidence…" /><button onClick={send} aria-label="Send"><Send size={17}/></button></div></Card></div>
  </div>;
}

function PageIntro({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <section className="page-intro"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div><div className="intro-side"><span>14:35</span><small>SIMULATED TIME</small></div></section>;
}
