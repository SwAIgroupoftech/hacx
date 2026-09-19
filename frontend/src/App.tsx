import { Routes, Route } from "react-router-dom";
import { AppShell } from "./components/layout";
import { Overview, Network, Replay, Incidents, Forecasts, Advisories, Bottlenecks, Proposals, Backtest, Ask } from "./pages";
import { FloatingTrafficChat } from "./components/FloatingTrafficChat";

export default function App() {
  return (
    <>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Overview />} />
          <Route path="/network" element={<Network />} />
          <Route path="/replay" element={<Replay />} />
          <Route path="/incidents" element={<Incidents />} />
          <Route path="/forecasts" element={<Forecasts />} />
          <Route path="/advisories" element={<Advisories />} />
          <Route path="/bottlenecks" element={<Bottlenecks />} />
          <Route path="/proposals" element={<Proposals />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/ask" element={<Ask />} />
        </Route>
      </Routes>

      <FloatingTrafficChat />
    </>
  );
}