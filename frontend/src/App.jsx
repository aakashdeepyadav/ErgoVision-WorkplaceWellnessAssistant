import { lazy, Suspense, useCallback, useMemo, useState, useEffect } from "react";
import {
  Eye, Ruler, Activity, Gauge, Brain,
  Settings, BarChart3, Maximize2, Minimize2,
  Clock, Bell, Sun, Moon, AlertTriangle,
  Droplets, Timer, Trophy, Dumbbell,
} from "lucide-react";
import { useErgoVisionSocket } from "./hooks/useErgoVisionSocket";
import { DEFAULT_SETTINGS } from "./constants/alerts";
import ConnectionState from "./components/ConnectionState";
import CalibrationOverlay from "./components/CalibrationOverlay";
import MetricCard from "./components/MetricCard";
import SparklineChart from "./components/SparklineChart";
import WellnessRing from "./components/WellnessRing";
import GazeIndicator from "./components/GazeIndicator";
import BreakReminder from "./components/BreakReminder";
import SettingsDrawer from "./components/SettingsDrawer";

const AnalyticsModal = lazy(() => import("./components/AnalyticsModal"));

const WS_URL =
  import.meta.env.VITE_WS_URL ||
  `ws://${import.meta.env.VITE_BACKEND_HOST || location.hostname}:${import.meta.env.VITE_BACKEND_PORT || "8000"}/ws`;

function formatDuration(start) {
  if (!start) return "--:--";
  const s = Math.floor((Date.now() - start.getTime()) / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return h > 0
    ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
    : `${m}:${String(sec).padStart(2, "0")}`;
}

function formatBreakTime(seconds) {
  if (!seconds || seconds < 60) return "< 1 min";
  const m = Math.floor(seconds / 60);
  return `${m} min`;
}

function computeTrend(history, key) {
  if (history.length < 10) return { direction: "steady", label: "Collecting" };
  const recent = history.slice(-20);
  const first = recent.slice(0, 10).reduce((s, h) => s + (h[key] || 0), 0) / 10;
  const last = recent.slice(-10).reduce((s, h) => s + (h[key] || 0), 0) / 10;
  const d = last - first;
  if (Math.abs(d) < 0.5) return { direction: "steady", label: "Stable" };
  return d > 0
    ? { direction: "up", label: "Rising" }
    : { direction: "down", label: "Falling" };
}

function wellnessScore(data) {
  if (!data || data.type !== "detection") return 0;
  let score = 100;
  if (data.eye?.alert) score -= 20;
  if (data.posture?.alert) score -= 20;
  if (data.distance?.alert) score -= 15;
  if (data.fatigue?.alert) score -= 15;
  if (data.head_tilt?.alert) score -= 15;
  if (data.eye?.stare_alert) score -= 10;
  return Math.max(0, Math.min(100, score));
}

function wellnessLabel(score) {
  if (score >= 80) return { text: "Excellent", tier: "excellent" };
  if (score >= 60) return { text: "Balanced", tier: "balanced" };
  if (score >= 35) return { text: "At Risk", tier: "risk" };
  return { text: "Critical", tier: "critical" };
}

export default function App() {
  const {
    connected, connecting, error, frame, data,
    alerts, toasts, history, sessionStart, breakDue,
    connect, sendCommand,
  } = useErgoVisionSocket(WS_URL, { autoConnect: false });

  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [alertFilter, setAlertFilter] = useState("all");
  const [showBreakReminder, setShowBreakReminder] = useState(false);
  const [breakDismissed, setBreakDismissed] = useState(false);
  const [theme, setTheme] = useState(() =>
    localStorage.getItem("ergovision-theme") || "light"
  );

  // Apply theme
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("ergovision-theme", theme);
  }, [theme]);

  // Show break reminder when break is due
  useEffect(() => {
    if (breakDue && !breakDismissed) {
      setShowBreakReminder(true);
    }
    if (!breakDue) {
      setBreakDismissed(false);
    }
  }, [breakDue, breakDismissed]);

  const score = useMemo(() => wellnessScore(data), [data]);
  const wLabel = useMemo(() => wellnessLabel(score), [score]);

  const isDetecting = data?.type === "detection";
  const isCalibrating = data?.type === "calibration";

  const handleSaveSettings = useCallback(() => {
    sendCommand("update_settings", { settings });
    setShowSettings(false);
  }, [sendCommand, settings]);

  const handleToggleVoice = useCallback(() => {
    setVoiceEnabled((v) => !v);
    sendCommand("toggle_voice");
  }, [sendCommand]);

  const handleAcknowledgeBreak = useCallback(() => {
    sendCommand("acknowledge_break");
    setShowBreakReminder(false);
    setBreakDismissed(true);
  }, [sendCommand]);

  const handleDismissBreak = useCallback(() => {
    setShowBreakReminder(false);
    setBreakDismissed(true);
  }, []);

  const handleDrinkWater = useCallback(() => {
    sendCommand("drink_water");
  }, [sendCommand]);

  const handleSetBreakMode = useCallback((mode) => {
    sendCommand("set_break_mode", { mode });
  }, [sendCommand]);

  const filteredAlerts = useMemo(() => {
    if (alertFilter === "all") return alerts;
    return alerts.filter((a) => a.color === alertFilter);
  }, [alerts, alertFilter]);

  const alertCounts = useMemo(() => {
    const counts = {};
    for (const a of alerts) {
      counts[a.color] = (counts[a.color] || 0) + 1;
    }
    return counts;
  }, [alerts]);

  const sparkData = useMemo(() => history.slice(-30), [history]);

  // ── Not connected ────────────────────────────
  if (!connected && !connecting) {
    return <ConnectionState connecting={connecting} error={error} onConnect={connect} />;
  }

  if (connecting) {
    return <ConnectionState connecting error={error} onConnect={connect} />;
  }

  // ── Calibration ──────────────────────────────
  if (isCalibrating) {
    return (
      <div className="app-container">
        <CalibrationOverlay
          phase={data?.phase || "idle"}
          progress={data?.progress}
          message={data?.message}
          onStart={() => sendCommand("start_calibration")}
          onSkip={() => sendCommand("skip_calibration")}
        />
      </div>
    );
  }

  const breakStatus = data?.break_status || {};
  const productivity = data?.productivity || {};

  // Break pill class
  const breakPillClass = breakStatus.break_overdue
    ? "break-pill break-pill--overdue"
    : breakStatus.break_due
      ? "break-pill break-pill--due"
      : "break-pill break-pill--ok";

  return (
    <div className={`app-container ${focusMode ? "app-container--focus" : ""}`}>
      {/* ── Header ──────────────────────────── */}
      <header className="app-header">
        <div className="app-header__brand">
          <div className="app-header__logo">EV</div>
          <div>
            <div className="app-header__title">ErgoVision</div>
            <div className="app-header__subtitle">Workplace Wellness</div>
          </div>
        </div>
        <div className="app-header__actions">
          {/* Hydration Pill */}
          <button
            className={`hydration-pill ${breakStatus.hydration_due ? "hydration-pill--due" : ""}`}
            onClick={handleDrinkWater}
            title={`${breakStatus.hydration_glasses || 0}/${breakStatus.hydration_goal || 8} glasses — Click to log water`}
          >
            <Droplets size={12} />
            {breakStatus.hydration_glasses || 0}/{breakStatus.hydration_goal || 8}
          </button>
          {/* Pomodoro/Break Pill */}
          <span className={breakPillClass}>
            {breakStatus.mode === "pomodoro" ? <Timer size={12} /> : <Clock size={12} />}
            {breakStatus.mode === "pomodoro"
              ? `${breakStatus.pomodoro_phase || "work"} · ${Math.ceil((breakStatus.pomodoro_remaining || 0) / 60)}m`
              : formatBreakTime(breakStatus.time_since_break)
            }
          </span>
          <span className={`app-header__status ${connected ? "app-header__status--active" : "app-header__status--inactive"}`}>
            <span className="app-header__status-dot" />
            {connected ? "Live" : "Idle"}
          </span>
          <button
            className="theme-toggle"
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            title="Toggle theme"
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>
          <button
            className={`btn btn--ghost btn--icon ${focusMode ? "btn--active" : ""}`}
            onClick={() => setFocusMode((f) => !f)}
            title="Focus mode"
          >
            {focusMode ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
          <button
            className="btn btn--ghost btn--icon"
            onClick={() => setShowAnalytics(true)}
            title="Analytics"
          >
            <BarChart3 size={16} />
          </button>
          <button
            className="btn btn--ghost btn--icon"
            onClick={() => setShowSettings(true)}
            title="Settings"
          >
            <Settings size={16} />
          </button>
        </div>
      </header>

      {/* ── Toasts ──────────────────────────── */}
      {toasts.length > 0 && (
        <div className="toast">
          {toasts.map((t) => (
            <div key={t.id} className={`toast__item toast__item--${t.color}`}>
              <div className="toast__label">{t.label}</div>
              <div className="toast__text">{t.message}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Main ────────────────────────────── */}
      <main className="app-main">
        <section className="webcam-panel">
          {/* Insight Strip */}
          <div className="insight-strip">
            <article className={`insight-card insight-card--${wLabel.tier}`}>
              <div className="insight-card__eyebrow">Wellness Score</div>
              <WellnessRing score={score} size={110} />
              <div className={`risk-pill risk-pill--${wLabel.tier}`}>
                {wLabel.text}
              </div>
            </article>

            <article className="insight-card">
              <div className="insight-card__eyebrow">Session Stats</div>
              <div className="insight-card__stat">
                <span>Duration</span>
                <strong>{formatDuration(sessionStart)}</strong>
              </div>
              <div className="insight-card__stat">
                <span>Healthy</span>
                <strong>{formatBreakTime(productivity.healthy_time)}</strong>
              </div>
              <div className="insight-card__stat">
                <span>Score</span>
                <strong>{productivity.session_score || 0}%</strong>
              </div>
              <div className="insight-card__stat">
                <span>Breaks</span>
                <strong>{breakStatus.breaks_taken || 0}</strong>
              </div>
            </article>

            <article className="insight-card insight-card--action">
              <div className="insight-card__eyebrow">Quick Actions</div>
              <div className="insight-card__text">
                {score >= 80 ? "Your workspace setup looks great. Keep it up!" :
                 score >= 60 ? "Minor adjustments needed. Check the metric cards below." :
                 "Multiple issues detected. Review your posture and take a break."}
              </div>
              {focusMode ? (
                <div className="focus-hint">Focus Mode Active</div>
              ) : null}
              <button
                className="btn btn--ghost btn--sm"
                onClick={() => sendCommand("recalibrate")}
              >
                Recalibrate
              </button>
            </article>
          </div>



          {/* Metrics Grid */}
          <div className="metrics-grid">
            <MetricCard
              className="animate-fade-in-up delay-100"
              title="Eye Strain"
              icon={<Eye size={14} />}
              value={isDetecting ? data.eye?.blink_rate ?? "--" : "--"}
              unit="blinks/min"
              detail={`EAR: ${isDetecting ? (data.eye?.ear ?? 0).toFixed(2) : "--"}`}
              accent="var(--accent-teal)"
              status={data?.eye?.alert ? "alert" : "good"}
              trend={computeTrend(history, "blinkRate")}
            />
            <MetricCard
              className="animate-fade-in-up delay-200"
              title="Posture"
              icon={<Activity size={14} />}
              value={isDetecting ? Math.round(data.posture?.deviation ?? 0) : "--"}
              unit="px"
              detail={`Status: ${data?.posture?.status || "—"}`}
              accent="var(--accent-blue)"
              status={data?.posture?.alert ? "alert" : data?.posture?.status === "WARNING" ? "warning" : "good"}
              trend={computeTrend(history, "posture")}
            />
            <MetricCard
              className="animate-fade-in-up delay-300"
              title="Distance"
              icon={<Ruler size={14} />}
              value={isDetecting ? Math.round(data.distance?.distance_cm ?? 0) : "--"}
              unit="cm"
              detail={data?.distance?.alert ? "Too close!" : "Within range"}
              accent="var(--accent-amber)"
              status={data?.distance?.alert ? "alert" : "good"}
              trend={computeTrend(history, "distance")}
            />
            <MetricCard
              className="animate-fade-in-up delay-400"
              title="Fatigue"
              icon={<Gauge size={14} />}
              value={isDetecting ? Math.round(data.fatigue?.fatigue_score ?? 0) : "--"}
              unit="/100"
              detail={`Trend: ${data?.fatigue?.fatigue_trend || "—"}`}
              accent="var(--accent-red)"
              status={data?.fatigue?.alert ? "alert" : data?.fatigue?.fatigue_score > 50 ? "warning" : "good"}
              trend={computeTrend(history, "fatigue")}
            />
            <MetricCard
              className="animate-fade-in-up delay-500"
              title="Head Tilt"
              icon={<Brain size={14} />}
              value={isDetecting ? Math.round(Math.abs(data.head_tilt?.angle ?? 0)) : "--"}
              unit="°"
              detail={`Dir: ${data?.head_tilt?.direction || "—"}`}
              accent="var(--accent-purple)"
              status={data?.head_tilt?.alert ? "alert" : "good"}
              trend={computeTrend(history, "headTilt")}
            />
          </div>

          {/* Sparklines */}
          {sparkData.length > 5 && (
            <div className="metrics-grid">
              <div className="metric-card metric-card--compact">
                <div className="metric-card__label">Blink Rate</div>
                <SparklineChart data={sparkData} dataKey="blinkRate" color="#0f766e" gradientId="sparkBlink" height={60} />
              </div>
              <div className="metric-card metric-card--compact">
                <div className="metric-card__label">Posture</div>
                <SparklineChart data={sparkData} dataKey="posture" color="#0369a1" gradientId="sparkPosture" height={60} />
              </div>
              <div className="metric-card metric-card--compact">
                <div className="metric-card__label">Distance</div>
                <SparklineChart data={sparkData} dataKey="distance" color="#c2410c" gradientId="sparkDistance" height={60} />
              </div>
              <div className="metric-card metric-card--compact">
                <div className="metric-card__label">Fatigue</div>
                <SparklineChart data={sparkData} dataKey="fatigue" color="#b91c1c" gradientId="sparkFatigue" height={60} yDomain={[0, 100]} />
              </div>
              <div className="metric-card metric-card--compact">
                <div className="metric-card__label">Head Tilt</div>
                <SparklineChart data={sparkData} dataKey="headTilt" color="#7c3aed" gradientId="sparkTilt" height={60} />
              </div>
            </div>
          )}
        </section>

        {/* ── Side Panel ────────────────────── */}
        <aside className="side-panel">
          {/* Webcam */}
          <div className="webcam-frame">
            <div className="scanline" />
            {frame ? (
              <img src={`data:image/jpeg;base64,${frame}`} alt="Webcam" />
            ) : (
              <div className="webcam-frame__placeholder">
                <div className="webcam-frame__placeholder-icon">Camera</div>
                <span className="text-muted">Waiting for frame data…</span>
              </div>
            )}
            {frame && (
              <>
                <span className="webcam-frame__badge webcam-frame__badge--live">● Live</span>
                <span className="webcam-frame__badge webcam-frame__badge--fps">
                  {data?.fps || 0} FPS
                </span>
                {isDetecting && data?.eye && (
                  <GazeIndicator gazeX={data.eye.gaze_x || 0} gazeY={data.eye.gaze_y || 0} />
                )}
              </>
            )}
          </div>

          <div className="session-info">
            <div className="session-info__title"><Clock size={13} /> Session</div>
            <div className="session-info__row">
              <span className="session-info__label">Elapsed</span>
              <span className="session-info__value">{formatDuration(sessionStart)}</span>
            </div>
            <div className="session-info__row">
              <span className="session-info__label">Alerts</span>
              <span className="session-info__value">{alerts.length}</span>
            </div>
            <div className="session-info__row">
              <span className="session-info__label">Breaks</span>
              <span className="session-info__value">{breakStatus.breaks_taken || 0}</span>
            </div>
            <div className="session-info__row">
              <span className="session-info__label">Compliance</span>
              <span className="session-info__value">{breakStatus.compliance || 100}%</span>
            </div>
            <div className="session-info__row">
              <span className="session-info__label">Wellness</span>
              <span className="session-info__value">{score}/100</span>
            </div>
          </div>

          {/* Posture Streak */}
          <div className="posture-streak">
            <div className="posture-streak__title"><Trophy size={13} /> Posture Streak</div>
            <div className="posture-streak__value">
              {Math.floor((breakStatus.posture_streak || 0) / 60)}m {Math.floor((breakStatus.posture_streak || 0) % 60)}s
            </div>
            {breakStatus.best_posture_streak > 0 && (
              <div className="posture-streak__best">
                Best: {Math.floor(breakStatus.best_posture_streak / 60)}m
              </div>
            )}
            {breakStatus.posture_streak_milestone && (
              <div className="posture-streak__milestone">{breakStatus.posture_streak_milestone}</div>
            )}
          </div>

          {/* Hydration Tracker */}
          <div className="hydration-tracker">
            <div className="hydration-tracker__title"><Droplets size={13} /> Hydration</div>
            <div className="hydration-tracker__bar">
              <div
                className="hydration-tracker__fill"
                style={{ width: `${Math.min(100, ((breakStatus.hydration_glasses || 0) / (breakStatus.hydration_goal || 8)) * 100)}%` }}
              />
            </div>
            <div className="hydration-tracker__label">
              {breakStatus.hydration_glasses || 0} / {breakStatus.hydration_goal || 8} glasses
            </div>
            <button className="btn btn--sm btn--accent" onClick={handleDrinkWater}>
              <Droplets size={12} /> Drink Water
            </button>
          </div>

          <div className="alert-feed">
            <div className="alert-feed__title"><Bell size={13} /> Alerts</div>
            <div className="alert-feed__filters">
              {[
                { id: "all", label: "All", count: alerts.length },
                { id: "eye", label: "Eye", count: alertCounts.eye || 0 },
                { id: "posture", label: "Posture", count: alertCounts.posture || 0 },
                { id: "distance", label: "Distance", count: alertCounts.distance || 0 },
                { id: "fatigue", label: "Fatigue", count: alertCounts.fatigue || 0 },
                { id: "tilt", label: "Tilt", count: alertCounts.tilt || 0 },
                { id: "break", label: "Break", count: alertCounts.break || 0 },
              ].map((f) => (
                <button
                  key={f.id}
                  className={`chip ${alertFilter === f.id ? "chip--active" : ""}`}
                  onClick={() => setAlertFilter(f.id)}
                >
                  {f.label} <span>{f.count}</span>
                </button>
              ))}
            </div>
            {filteredAlerts.length === 0 ? (
              <div className="alert-feed__empty">
                {alerts.length === 0
                  ? "No alerts yet. Monitoring your wellness."
                  : "No alerts match this filter."}
              </div>
            ) : (
              filteredAlerts.slice(0, 20).map((a) => (
                <div key={a.id} className="alert-feed__item">
                  <div className={`alert-feed__dot alert-feed__dot--${a.color}`} />
                  <div>
                    <div className="alert-feed__text">
                      <strong>{a.label}</strong> — {a.message}
                    </div>
                    <div className="alert-feed__time">{a.time}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </aside>
      </main>

      {/* ── Break Reminder ──────────────────── */}
      <BreakReminder
        visible={showBreakReminder}
        onDismiss={handleDismissBreak}
        onAcknowledge={handleAcknowledgeBreak}
        stretch={breakStatus.current_stretch}
        pomodoroPhase={breakStatus.pomodoro_phase}
        breakMode={breakStatus.mode}
      />

      {/* ── Settings Drawer ─────────────────── */}
      <SettingsDrawer
        open={showSettings}
        onClose={() => setShowSettings(false)}
        settings={settings}
        setSettings={setSettings}
        voiceEnabled={voiceEnabled}
        onToggleVoice={handleToggleVoice}
        onSave={handleSaveSettings}
      />

      {/* ── Analytics Modal ─────────────────── */}
      {showAnalytics ? (
        <Suspense
          fallback={
            <div className="analytics-overlay" onClick={() => setShowAnalytics(false)}>
              <div className="analytics-panel" onClick={(e) => e.stopPropagation()}>
                <div className="analytics-panel__header">
                  <h2 className="analytics-panel__title">Session Analytics</h2>
                  <button className="btn btn--ghost btn--icon" onClick={() => setShowAnalytics(false)}>Close</button>
                </div>
                <div className="alert-feed__empty analytics-panel__empty">Loading analytics...</div>
              </div>
            </div>
          }
        >
          <AnalyticsModal
            open={showAnalytics}
            onClose={() => setShowAnalytics(false)}
            history={history}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
