import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const CHARTS = [
  {
    title: "Blink Rate",
    dataKey: "blinkRate",
    color: "#0f766e",
    gradientId: "analyticsBlink",
    domain: [0, "auto"],
    unit: "blinks/min",
  },
  {
    title: "Posture Deviation",
    dataKey: "posture",
    color: "#0369a1",
    gradientId: "analyticsPosture",
    domain: [0, "auto"],
    unit: "px",
  },
  {
    title: "Screen Distance",
    dataKey: "distance",
    color: "#c2410c",
    gradientId: "analyticsDistance",
    domain: [0, "auto"],
    unit: "cm",
  },
  {
    title: "Fatigue Score",
    dataKey: "fatigue",
    color: "#b91c1c",
    gradientId: "analyticsFatigue",
    domain: [0, 100],
    unit: "/100",
  },
];

function AnalyticsChartCard({
  title,
  data,
  dataKey,
  color,
  gradientId,
  domain,
  unit,
}) {
  return (
    <article className="analytics-chart-card">
      <h3 className="analytics-chart-card__title">{title}</h3>
      <ResponsiveContainer width="100%" height={210}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.35} />
              <stop offset="95%" stopColor={color} stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <CartesianGrid
            strokeDasharray="4 4"
            stroke="rgba(15, 23, 42, 0.09)"
          />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 11, fill: "#475569" }}
            minTickGap={18}
          />
          <YAxis tick={{ fontSize: 11, fill: "#475569" }} domain={domain} />
          <Tooltip
            contentStyle={{
              borderRadius: 12,
              border: "1px solid rgba(15, 23, 42, 0.14)",
              background: "#ffffff",
            }}
            formatter={(value) => [
              `${Number(value).toFixed(1)} ${unit}`,
              title,
            ]}
          />
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            fill={`url(#${gradientId})`}
            strokeWidth={2.2}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </article>
  );
}

export default function AnalyticsModal({ open, onClose, history }) {
  if (!open) {
    return null;
  }

  return (
    <div className="analytics-overlay" onClick={onClose}>
      <div
        className="analytics-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="analytics-panel__header">
          <h2 className="analytics-panel__title">Session Analytics</h2>
          <button className="btn btn--ghost btn--icon" onClick={onClose}>
            Close
          </button>
        </div>

        {history.length < 5 ? (
          <div className="alert-feed__empty analytics-panel__empty">
            More runtime samples are required before analytics can be rendered.
          </div>
        ) : (
          CHARTS.map((chart) => (
            <AnalyticsChartCard
              key={chart.dataKey}
              title={chart.title}
              data={history}
              dataKey={chart.dataKey}
              color={chart.color}
              gradientId={chart.gradientId}
              domain={chart.domain}
              unit={chart.unit}
            />
          ))
        )}
      </div>
    </div>
  );
}
