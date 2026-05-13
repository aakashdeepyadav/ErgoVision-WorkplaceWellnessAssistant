import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

const TREND_META = {
  up: {
    icon: ArrowUpRight,
    fallbackLabel: "Improving",
  },
  down: {
    icon: ArrowDownRight,
    fallbackLabel: "Drifting",
  },
  steady: {
    icon: Minus,
    fallbackLabel: "Stable",
  },
};

export default function MetricCard({
  title,
  icon,
  value,
  unit,
  detail,
  accent,
  status = "good",
  trend,
}) {
  const cardClassName =
    status === "alert" ? "metric-card metric-card--alert" : "metric-card";

  const trendDirection = TREND_META[trend?.direction]
    ? trend.direction
    : "steady";
  const TrendIcon = TREND_META[trendDirection].icon;
  const trendLabel = trend?.label || TREND_META[trendDirection].fallbackLabel;

  return (
    <article className={cardClassName} style={{ "--card-accent": accent }}>
      <header className="metric-card__header">
        <span className="metric-card__label">
          <span className="metric-card__icon" style={{ color: accent }}>
            {icon}
          </span>
          {title}
        </span>
        <span
          className={`metric-card__status-dot metric-card__status-dot--${status}`}
        />
      </header>
      <div className="metric-card__value">
        {value}
        {unit ? <span className="metric-card__unit">{unit}</span> : null}
      </div>
      <div className="metric-card__detail">{detail}</div>
      {trend ? (
        <div
          className={`metric-card__trend metric-card__trend--${trendDirection}`}
        >
          <TrendIcon size={12} />
          <span>{trendLabel}</span>
        </div>
      ) : null}
    </article>
  );
}
