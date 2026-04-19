export default function MetricCard({
  title,
  icon,
  value,
  unit,
  detail,
  accent,
  status = "good",
}) {
  const cardClassName =
    status === "alert" ? "metric-card metric-card--alert" : "metric-card";

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
    </article>
  );
}
