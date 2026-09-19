import React from "react";

type RoadStatus = "normal" | "congested" | "incident";

type Road = {
  id: string;
  name: string;
  status: RoadStatus;
  path: string;
  speed: string;
  freeFlow: string;
  ratio: string;
  anomaly: string;
};

const roads: Road[] = [
  {
    id: "F09",
    name: "West Bypass",
    status: "normal",
    path: "M 80 370 C 190 350, 260 300, 370 315 S 610 365, 900 250",
    speed: "54 km/h",
    freeFlow: "60 km/h",
    ratio: "0.90",
    anomaly: "0.4",
  },
  {
    id: "A12",
    name: "Gotham Avenue",
    status: "congested",
    path: "M 130 150 C 280 175, 390 190, 520 175 S 760 125, 900 145",
    speed: "31 km/h",
    freeFlow: "55 km/h",
    ratio: "0.56",
    anomaly: "2.8",
  },
  {
    id: "B07",
    name: "Central Boulevard",
    status: "incident",
    path: "M 450 60 C 455 150, 465 230, 500 310 S 550 450, 565 540",
    speed: "18 km/h",
    freeFlow: "58 km/h",
    ratio: "0.31",
    anomaly: "4.9",
  },
  {
    id: "C21",
    name: "East Connector",
    status: "congested",
    path: "M 610 80 C 620 160, 650 220, 690 300 S 760 430, 850 510",
    speed: "29 km/h",
    freeFlow: "52 km/h",
    ratio: "0.55",
    anomaly: "2.1",
  },
  {
    id: "D14",
    name: "Market Street",
    status: "normal",
    path: "M 90 465 C 250 440, 380 445, 520 455 S 770 470, 930 450",
    speed: "49 km/h",
    freeFlow: "54 km/h",
    ratio: "0.91",
    anomaly: "0.3",
  },
  {
    id: "E03",
    name: "North Loop",
    status: "normal",
    path: "M 230 70 C 240 150, 250 230, 280 300 S 330 430, 360 525",
    speed: "51 km/h",
    freeFlow: "56 km/h",
    ratio: "0.91",
    anomaly: "0.2",
  },
];

const statusColor: Record<RoadStatus, string> = {
  normal: "#9ca3af",
  congested: "#b38a3c",
  incident: "#b83232",
};

const statusLabel: Record<RoadStatus, string> = {
  normal: "NORMAL",
  congested: "CONGESTED",
  incident: "INCIDENT",
};

function RoadLayer({
  road,
  selected,
  onSelect,
}: {
  road: Road;
  selected: boolean;
  onSelect: () => void;
}) {
  const color = statusColor[road.status];

  return (
    <g
      onClick={onSelect}
      className="cursor-pointer"
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onSelect();
      }}
    >
      {/* Road shadow */}
      <path
        d={road.path}
        fill="none"
        stroke="rgba(0,0,0,0.65)"
        strokeWidth={selected ? 28 : 24}
        strokeLinecap="round"
      />

      {/* Asphalt */}
      <path
        d={road.path}
        fill="none"
        stroke="#343434"
        strokeWidth={selected ? 22 : 19}
        strokeLinecap="round"
      />

      {/* Road edge */}
      <path
        d={road.path}
        fill="none"
        stroke="#575757"
        strokeWidth="1.5"
        strokeLinecap="round"
      />

      {/* Lane divider */}
      <path
        d={road.path}
        fill="none"
        stroke="#777"
        strokeWidth="1"
        strokeDasharray="9 9"
        opacity="0.7"
      />

      {/* Traffic condition */}
      <path
        d={road.path}
        fill="none"
        stroke={color}
        strokeWidth={selected ? 7 : 5}
        strokeLinecap="round"
        opacity="0.95"
      />

      {/* Direction arrows */}
      <circle
        cx="50%"
        cy="50%"
        r="0"
        fill="none"
      />
    </g>
  );
}

function Building({
  x,
  y,
  width,
  height,
}: {
  x: number;
  y: number;
  width: number;
  height: number;
}) {
  return (
    <g opacity="0.9">
      <rect
        x={x + 4}
        y={y + 4}
        width={width}
        height={height}
        rx="2"
        fill="#080808"
        opacity="0.7"
      />

      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        rx="2"
        fill="#1d1d1d"
        stroke="#343434"
        strokeWidth="1"
      />

      <path
        d={`M ${x + 8} ${y + 10} H ${x + width - 8}`}
        stroke="#343434"
        strokeWidth="1"
      />

      <path
        d={`M ${x + 8} ${y + 18} H ${x + width - 8}`}
        stroke="#2b2b2b"
        strokeWidth="1"
      />
    </g>
  );
}

function Intersection({ x, y }: { x: number; y: number }) {
  return (
    <g>
      <circle cx={x} cy={y} r="10" fill="#101010" stroke="#777" />
      <circle cx={x} cy={y} r="4" fill="#c4c4c4" />
    </g>
  );
}

export function TrafficNetworkMap() {
  const [selected, setSelected] = React.useState("F09");

  const selectedRoad =
    roads.find((road) => road.id === selected) ?? roads[0];

  return (
    <div className="relative h-full min-h-[620px] overflow-hidden border border-white/10 bg-[#111111]">
      {/* City grid */}
      <svg
        viewBox="0 0 1000 600"
        preserveAspectRatio="xMidYMid slice"
        className="absolute inset-0 h-full w-full"
      >
        <defs>
          <pattern
            id="city-grid"
            width="50"
            height="50"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 50 0 L 0 0 0 50"
              fill="none"
              stroke="#262626"
              strokeWidth="1"
            />
          </pattern>

          <radialGradient id="mapFade">
            <stop offset="0%" stopColor="#202020" />
            <stop offset="100%" stopColor="#0d0d0d" />
          </radialGradient>
        </defs>

        <rect width="1000" height="600" fill="url(#mapFade)" />
        <rect width="1000" height="600" fill="url(#city-grid)" />

        {/* City blocks */}
        <Building x={45} y={65} width={120} height={65} />
        <Building x={320} y={45} width={100} height={85} />
        <Building x={700} y={55} width={130} height={70} />

        <Building x={55} y={205} width={130} height={80} />
        <Building x={300} y={210} width={105} height={60} />
        <Building x={760} y={210} width={150} height={85} />

        <Building x={60} y={365} width={120} height={65} />
        <Building x={320} y={370} width={115} height={75} />
        <Building x={735} y={360} width={135} height={70} />

        <Building x={75} y={500} width={150} height={55} />
        <Building x={670} y={485} width={120} height={65} />
        <Building x={820} y={490} width={100} height={60} />

        {/* Roads */}
        {roads.map((road) => (
          <RoadLayer
            key={road.id}
            road={road}
            selected={road.id === selected}
            onSelect={() => setSelected(road.id)}
          />
        ))}

        {/* Intersections */}
        <Intersection x={470} y={177} />
        <Intersection x={625} y={190} />
        <Intersection x={505} y={315} />
        <Intersection x={680} y={300} />
        <Intersection x={530} y={455} />

        {/* Incident marker */}
        <g>
          <circle
            cx="680"
            cy="300"
            r="18"
            fill="none"
            stroke="#b83232"
            strokeWidth="2"
            opacity="0.45"
          />
          <circle
            cx="680"
            cy="300"
            r="7"
            fill="#b83232"
          />
        </g>

        {/* Road labels */}
        <g
          fontFamily="Inter, sans-serif"
          fontSize="10"
          letterSpacing="2"
          fill="#aaa"
        >
          <text x="160" y="337">WEST BYPASS</text>
          <text x="720" y="238">GOTHAM AVE</text>
          <text x="515" y="105" transform="rotate(83 515 105)">
            CENTRAL BLVD
          </text>
          <text x="780" y="465">EAST CONNECTOR</text>
          <text x="395" y="438">MARKET STREET</text>
        </g>
      </svg>

      {/* Header */}
      <div className="absolute left-4 top-4 border border-white/10 bg-black/75 px-4 py-3 backdrop-blur-md">
        <div className="text-[10px] font-medium tracking-[0.22em] text-neutral-500">
          NETWORK STATE
        </div>

        <div className="mt-1 text-sm font-semibold text-white">
          LIVE SIMULATION
          <span className="ml-2 text-neutral-500">14:35</span>
        </div>
      </div>

      {/* Map controls */}
      <div className="absolute right-4 top-4 flex gap-1">
        <button className="border border-white/10 bg-black/75 px-3 py-2 text-xs text-neutral-300 backdrop-blur-md hover:bg-white/10">
          +
        </button>

        <button className="border border-white/10 bg-black/75 px-3 py-2 text-xs text-neutral-300 backdrop-blur-md hover:bg-white/10">
          −
        </button>

        <button className="border border-white/10 bg-black/75 px-3 py-2 text-xs text-neutral-300 backdrop-blur-md hover:bg-white/10">
          ⌖
        </button>
      </div>

      {/* Selected road card */}
      <div className="absolute bottom-5 right-5 w-[285px] border border-white/10 bg-[#0d0d0d]/95 p-5 shadow-2xl backdrop-blur-xl">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-lg font-semibold text-white">
              {selectedRoad.id}
            </div>

            <div className="mt-1 text-xs text-neutral-500">
              {selectedRoad.name}
            </div>
          </div>

          <span
            className="border px-2 py-1 text-[9px] tracking-wider"
            style={{
              color: statusColor[selectedRoad.status],
              borderColor: `${statusColor[selectedRoad.status]}55`,
            }}
          >
            {statusLabel[selectedRoad.status]}
          </span>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-x-6 gap-y-4">
          <Metric label="SPEED" value={selectedRoad.speed} />
          <Metric label="FREE FLOW" value={selectedRoad.freeFlow} />
          <Metric label="RATIO" value={selectedRoad.ratio} />
          <Metric label="ANOMALY" value={selectedRoad.anomaly} />
        </div>

        <div className="mt-5 border-t border-white/10 pt-3 text-[11px] text-neutral-500">
          Click another road to inspect
        </div>
      </div>

      {/* Legend */}
      <div className="absolute bottom-5 left-5 flex items-center gap-5 border border-white/10 bg-black/75 px-4 py-3 text-[10px] text-neutral-400 backdrop-blur-md">
        <Legend color="#9ca3af" label="NORMAL" />
        <Legend color="#b38a3c" label="CONGESTED" />
        <Legend color="#b83232" label="INCIDENT" />
      </div>

      {/* North indicator */}
      <div className="absolute bottom-24 left-5 flex h-12 w-12 items-center justify-center border border-white/10 bg-black/70 text-xs text-neutral-400">
        N
      </div>
    </div>
  );
}

function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <div className="text-[9px] tracking-wider text-neutral-600">
        {label}
      </div>
      <div className="mt-1 text-sm font-semibold text-white">
        {value}
      </div>
    </div>
  );
}

function Legend({
  color,
  label,
}: {
  color: string;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="h-2 w-2 rounded-full"
        style={{ backgroundColor: color }}
      />
      {label}
    </div>
  );
}