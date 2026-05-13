import { useCallback, useEffect, useState } from "react";
import { Coffee, X } from "lucide-react";

export default function BreakReminder({ visible, onDismiss, onAcknowledge }) {
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

  return (
    <div className="break-overlay" onClick={onDismiss}>
      <div className="break-card" onClick={(e) => e.stopPropagation()}>
        <div className="break-card__icon">
          <Coffee size={28} />
        </div>
        <h2 className="break-card__title">Time for a Break</h2>
        <p className="break-card__text">
          Look at something 20 feet away for 20 seconds to reduce eye strain.
        </p>
        <div className="break-card__timer">
          {countdown > 0 ? `${countdown}s` : "Done!"}
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
