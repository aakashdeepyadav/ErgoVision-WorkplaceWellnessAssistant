import { useMemo, useState } from "react";
import { Download } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const RANGE_OPTIONS = [
  {
    id: "60",
    label: "Last 60",
    samples: 60,
  },
  {
    id: "180",
    label: "Last 180",
    samples: 180,
  },
  {
    id: "360",
    label: "Last 360",
    samples: 360,
  },
  {
    id: "all",
    label: "All",
    samples: null,
  },
];

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
  {
    title: "Head Tilt",
    dataKey: "headTilt",
    color: "#7c3aed",
    gradientId: "analyticsTilt",
    domain: [0, "auto"],
    unit: "°",
  },
];

function formatMetric(value) {
  return Number(value || 0).toFixed(1);
}

function summarizeChart(data, dataKey) {
  const values = data.map((item) => Number(item[dataKey]) || 0);

  if (!values.length) {
    return {
      latest: 0,
      avg: 0,
      min: 0,
      max: 0,
    };
  }

  const latest = values[values.length - 1];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length;

  return {
    latest,
    avg,
    min,
    max,
  };
}

function escapeCsvCell(value) {
  const text = String(value ?? "");
  if (/[,"\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function buildCsv(historyRows) {
  const headers = [
    "time",
    "ear",
    "blinkRate",
    "posture",
    "distance",
    "fatigue",
  ];
  const rows = historyRows.map((row) =>
    headers.map((header) => escapeCsvCell(row[header])).join(","),
  );

  return [headers.join(","), ...rows].join("\n");
}

function downloadCsv(historyRows) {
  if (!historyRows.length) {
    return;
  }

  const csv = buildCsv(historyRows);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");

  link.href = objectUrl;
  link.download = `ergovision-analytics-${timestamp}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(objectUrl);
}

function AnalyticsChartCard({
  title,
  data,
  dataKey,
  color,
  gradientId,
  domain,
  unit,
}) {
  const stats = summarizeChart(data, dataKey);

  return (
    <article className="analytics-chart-card">
      <div className="analytics-chart-card__header">
        <h3 className="analytics-chart-card__title">{title}</h3>
        <div className="analytics-chart-card__stats">
          <span>Latest {formatMetric(stats.latest)}</span>
          <span>Avg {formatMetric(stats.avg)}</span>
          <span>Min {formatMetric(stats.min)}</span>
          <span>Max {formatMetric(stats.max)}</span>
        </div>
      </div>
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
            formatter={(value) => [`${formatMetric(value)} ${unit}`, title]}
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
  const [rangeId, setRangeId] = useState("180");

  const selectedRange =
    RANGE_OPTIONS.find((option) => option.id === rangeId) || RANGE_OPTIONS[1];

  const visibleHistory = useMemo(() => {
    if (!selectedRange.samples) {
      return history;
    }

    return history.slice(-selectedRange.samples);
  }, [history, selectedRange.samples]);

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

        <div className="analytics-panel__toolbar">
          <div className="analytics-panel__ranges">
            {RANGE_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                className={`analytics-range-btn ${rangeId === option.id ? "analytics-range-btn--active" : ""}`}
                onClick={() => setRangeId(option.id)}
              >
                {option.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            className="btn btn--ghost btn--sm"
            onClick={() => downloadCsv(visibleHistory)}
            disabled={visibleHistory.length === 0}
          >
            <Download size={14} /> Export CSV
          </button>
        </div>
        <div className="analytics-panel__meta">
          {visibleHistory.length} samples in view
        </div>

        {visibleHistory.length < 5 ? (
          <div className="alert-feed__empty analytics-panel__empty">
            More runtime samples are required before analytics can be rendered.
          </div>
        ) : (
          CHARTS.map((chart) => (
            <AnalyticsChartCard
              key={chart.dataKey}
              title={chart.title}
              data={visibleHistory}
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
