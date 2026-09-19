import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, Loader2 } from "lucide-react";

export function Card({ children, className = "", title, action }: { children: ReactNode; className?: string; title?: string; action?: ReactNode }) {
  return (
    <section className={`panel ${className}`}>
      {(title || action) && (
        <div className="panel-head">
          {title ? <h2 className="panel-title">{title}</h2> : <span />}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "danger" | "success" | "warning" | "info" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function MetricCard({ label, value, detail, trend, critical = false }: { label: string; value: string; detail: string; trend?: string; critical?: boolean }) {
  return (
    <div className={`metric-card ${critical ? "metric-critical" : ""}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-foot">
        <span>{detail}</span>
        {trend && <span className={trend.startsWith("+") ? "text-danger" : "text-success"}>{trend}</span>}
      </div>
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="state-box"><Info size={18} /><div><strong>{title}</strong><p>{description}</p></div></div>;
}

export function ErrorState({ message = "Traffic intelligence data could not be loaded." }: { message?: string }) {
  return <div className="state-box danger-box"><AlertTriangle size={18} /><div><strong>Data unavailable</strong><p>{message}</p></div></div>;
}

export function LoadingState() {
  return <div className="state-box"><Loader2 className="spin" size={18} /><div><strong>Loading analysis</strong><p>Preparing the current traffic evidence.</p></div></div>;
}

export function ValidationBadge({ state }: { state: string }) {
  const tone = state === "VALIDATED" ? "success" : state === "FALLBACK" ? "warning" : state === "REJECTED" ? "danger" : "neutral";
  return <Badge tone={tone}>{state}</Badge>;
}

export function SimulatedLabel({ construction = false }: { construction?: boolean }) {
  return (
    <div className="simulated-label">
      <CheckCircle2 size={13} />
      {construction ? "SIMULATED ESTIMATE — NOT A CONSTRUCTION RECOMMENDATION" : "ADVISORY ONLY — SIMULATED"}
    </div>
  );
}
