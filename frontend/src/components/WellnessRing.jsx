import { useMemo } from "react";

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function scoreColor(score) {
  if (score >= 75) return "var(--success)";
  if (score >= 50) return "var(--accent-teal)";
  if (score >= 30) return "var(--warning)";
  return "var(--danger)";
}

export default function WellnessRing({ score = 0, size = 140 }) {
  const clampedScore = Math.max(0, Math.min(100, score));
  const offset = useMemo(
    () => CIRCUMFERENCE - (clampedScore / 100) * CIRCUMFERENCE,
    [clampedScore],
  );
  const color = scoreColor(clampedScore);

  return (
    <div className="wellness-ring">
      <svg width={size} height={size} viewBox="0 0 120 120">
        <circle className="wellness-ring__track" cx="60" cy="60" r={RADIUS} />
        <circle
          className="wellness-ring__fill"
          cx="60"
          cy="60"
          r={RADIUS}
          stroke={color}
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="wellness-ring__label">
        <div className="wellness-ring__score">{Math.round(clampedScore)}</div>
        <div className="wellness-ring__caption">Wellness</div>
      </div>
    </div>
  );
}
