import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Activity, AlertTriangle, BarChart3, Bot, BrainCircuit, Building2, Clock3, Gauge,
  LayoutDashboard, Menu, Moon, Network, PanelLeftClose, Radio, Route, Sun, TrafficCone, X,
} from "lucide-react";
import { useTheme } from "../hooks/useTheme";
import { SimulatedLabel } from "./ui";

const nav = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/network", label: "Live Network", icon: Network },
  { to: "/replay", label: "Replay", icon: Clock3 },
  { to: "/incidents", label: "Incidents", icon: AlertTriangle },
  { to: "/forecasts", label: "Forecasts", icon: Gauge },
  { to: "/advisories", label: "Advisories", icon: Radio },
  { to: "/bottlenecks", label: "Bottlenecks", icon: TrafficCone },
  { to: "/proposals", label: "Network Proposals", icon: Building2 },
  { to: "/backtest", label: "Accuracy / Backtest", icon: BarChart3 },
];

export function AppShell() {
  const { theme, toggleTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const page = nav.find((n) => n.to === location.pathname)?.label ?? "TrafficSense";

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileOpen ? "mobile-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Route size={18} /></div>
          <div><div className="brand-name">TrafficSense</div><div className="brand-sub">AI TRAFFIC INTELLIGENCE</div></div>
          <button className="icon-btn mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        </div>

        <nav className="nav">
          <div className="nav-caption">MONITOR</div>
          {nav.slice(0, 4).map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={() => setMobileOpen(false)} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              <Icon size={17} /><span>{label}</span>
            </NavLink>
          ))}
          <div className="nav-caption nav-gap">INTELLIGENCE</div>
          {nav.slice(4).map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={() => setMobileOpen(false)} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              <Icon size={17} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="system-status"><span className="status-dot" /> <span>ANALYSIS READY</span><span className="status-pulse" /></div>
          <SimulatedLabel />
          <button className="theme-btn" onClick={toggleTheme}>
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            {theme === "dark" ? "Light theme" : "Dark theme"}
          </button>
          <div className="version">NEURAX 3.0 · HACX · DEMO 0.1</div>
        </div>
      </aside>

      {mobileOpen && <div className="mobile-backdrop" onClick={() => setMobileOpen(false)} />}

      <main className="main">
        <header className="topbar">
          <div className="top-left">
            <button className="icon-btn mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu size={19} /></button>
            <div>
              <div className="top-title">{page}</div>
              <div className="top-context">NETWORK INTELLIGENCE · SIMULATION</div>
            </div>
          </div>
          <div className="top-right">
            <div className="time-block"><span>SIMULATION TIME</span><strong>14:35:00</strong></div>
          </div>
        </header>
        <div className="page">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
