# TrafficSense Frontend

Frontend-only React + TypeScript implementation of the TrafficSense AI traffic intelligence command center.

## Stack

- React
- TypeScript
- Vite
- Tailwind CSS
- React Router
- Recharts
- Lucide React

## Run

```bash
npm install
npm run dev
```

Build:

```bash
npm run build
```

## Backend integration

The UI currently uses `src/services/index.ts` as the boundary between pages/components and mock data.

Replace the service implementations there with calls to the TrafficSense FastAPI backend.

Do not move API calls into individual visual components.

## Main routes

- `/` Overview
- `/network` Live Network
- `/replay` Replay
- `/incidents` Incidents
- `/forecasts` Forecasts
- `/advisories` Advisories
- `/bottlenecks` Bottlenecks
- `/proposals` Network Proposals
- `/backtest` Accuracy / Backtest
- `/ask` Ask TrafficSense

## Notes

All displayed values are demo/simulated values. The interface intentionally labels results as advisory and simulated.
