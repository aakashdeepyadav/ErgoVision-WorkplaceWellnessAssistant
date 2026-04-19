export default function CalibrationOverlay({
  phase,
  progress,
  message,
  onStart,
  onSkip,
}) {
  const isIdle = phase === "idle";

  return (
    <div className="calibration-overlay">
      <div className="calibration-card">
        <div className="calibration-card__eyebrow">Calibration</div>
        <h2 className="calibration-card__title">
          {isIdle ? "Baseline Setup Required" : "Calibrating Sensor Baselines"}
        </h2>
        <p className="calibration-card__desc">
          {isIdle
            ? "We need a one-time baseline to adapt posture and distance thresholds to your setup."
            : phase === "posture"
              ? "Sit naturally upright and keep your shoulders visible."
              : "Stay around an arm length from the display and look at the camera."}
        </p>

        {!isIdle ? (
          <>
            <div className="calibration-card__progress">
              <div
                className="calibration-card__progress-fill"
                style={{
                  width: `${Math.max(0, Math.min(100, (progress || 0) * 100))}%`,
                }}
              />
            </div>
            <div className="calibration-card__status">
              {message || "Collecting samples..."}
            </div>
          </>
        ) : null}

        <div className="calibration-card__actions">
          <button className="btn btn--ghost" onClick={onSkip}>
            Use Defaults
          </button>
          {isIdle ? (
            <button className="btn btn--primary" onClick={onStart}>
              Start Calibration
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
