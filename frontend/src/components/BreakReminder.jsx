import { useCallback, useEffect, useState } from "react";
import { Coffee, X, Dumbbell, Timer } from "lucide-react";

export default function BreakReminder({ visible, onDismiss, onAcknowledge, stretch, pomodoroPhase, breakMode }) {
  const [countdown, setCountdown] = useState(20);

  useEffect(() => {
    if (!visible) {
      setCountdown(20);
      return;
    }
    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [visible]);

  const handleAcknowledge = useCallback(() => {
    onAcknowledge?.();
    onDismiss?.();
  }, [onAcknowledge, onDismiss]);

  if (!visible) return null;

  const isPomodoro = breakMode === "pomodoro";
  const title = isPomodoro
    ? (pomodoroPhase === "long_break" ? "Long Break Time! 🎉" : "Pomodoro Break!")
    : "Time for a Break";

  return (
    <div className="break-overlay" onClick={onDismiss}>
      <div className="break-card" onClick={(e) => e.stopPropagation()}>
        <div className="break-card__icon">
          {isPomodoro ? <Timer size={28} /> : <Coffee size={28} />}
        </div>
        <h2 className="break-card__title">{title}</h2>
        <p className="break-card__text">
          {isPomodoro
            ? `Great focus session! ${pomodoroPhase === "long_break" ? "Take a longer break — you've earned it." : "Rest your eyes and stretch."}`
            : "Look at something 20 feet away for 20 seconds to reduce eye strain."
          }
        </p>

        {/* Stretch Suggestion */}
        {stretch && (
          <div className="break-card__stretch">
            <div className="break-card__stretch-header">
              <Dumbbell size={14} />
              <span>Suggested Stretch</span>
            </div>
            <div className="break-card__stretch-name">{stretch.name}</div>
            <div className="break-card__stretch-desc">{stretch.desc}</div>
            <div className="break-card__stretch-time">~{stretch.duration}s</div>
          </div>
        )}

        <div className="break-card__timer">
          {countdown > 0 ? `${countdown}s` : "Done! ✓"}
        </div>
        <div className="break-card__actions">
          <button className="btn btn--ghost" onClick={onDismiss}>
            <X size={14} /> Skip
          </button>
          <button className="btn btn--primary" onClick={handleAcknowledge}>
            <Coffee size={14} /> I Took a Break
          </button>
        </div>
      </div>
    </div>
  );
}
