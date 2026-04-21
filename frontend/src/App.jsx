import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  Eye,
  RefreshCw,
  Ruler,
  Settings,
  Volume2,
  VolumeX,
} from "lucide-react";

import "./App.css";
import AnalyticsModal from "./components/AnalyticsModal";
import CalibrationOverlay from "./components/CalibrationOverlay";
import ConnectionState from "./components/ConnectionState";
import MetricCard from "./components/MetricCard";
import SettingsDrawer from "./components/SettingsDrawer";
import SparklineChart from "./components/SparklineChart";
import { DEFAULT_SETTINGS } from "./constants/alerts";
import { useErgoVisionSocket } from "./hooks/useErgoVisionSocket";

function resolveWebSocketUrl() {
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const hostname = window.location.hostname || "localhost";
  const localHosts = new Set(["localhost", "127.0.0.1"]);
  const backendPort = import.meta.env.VITE_BACKEND_PORT || "8000";
  const host = localHosts.has(hostname)
    ? `${hostname}:${backendPort}`
    : window.location.host;

  return `${protocol}://${host}/ws`;
}

const WS_URL = resolveWebSocketUrl();

function formatSessionDuration(sessionStart) {
  if (!sessionStart) {
    return "00:00";
  }

  const elapsedSeconds = Math.floor(
    (Date.now() - sessionStart.getTime()) / 1000,
  );
  const minutes = Math.floor(elapsedSeconds / 60)
    .toString()
    .padStart(2, "0");
  const seconds = (elapsedSeconds % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function metricStatus({ alert, warning = false }) {
  if (alert) {
    return "alert";
  }
  if (warning) {
    return "warning";
  }
  return "good";
}

export default function App() {
  const {
    connected,
    connecting,
    error,
    frame,
    data,
    alerts,
    toasts,
    history,
    sessionStart,
    connect,
    sendCommand,
  } = useErgoVisionSocket(WS_URL);

  const [showSettings, setShowSettings] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [sessionTime, setSessionTime] = useState("00:00");

  useEffect(() => {
    const timer = setInterval(() => {
      setSessionTime(formatSessionDuration(sessionStart));
    }, 1000);

    return () => clearInterval(timer);
  }, [sessionStart]);

  const eyeData = data?.eye ?? {};
  const postureData = data?.posture ?? {};
  const distanceData = data?.distance ?? {};
  const fatigueData = data?.fatigue ?? {};

  const fps = data?.fps ?? 0;
  const faceDetected = data?.face_detected ?? false;

  const isCalibrationMode = data?.type === "calibration";
  const shouldShowCalibration = isCalibrationMode && data?.phase !== "complete";

  const recentSamples = useMemo(() => history.slice(-80), [history]);

  const handleStartCalibration = () => sendCommand("start_calibration");
  const handleSkipCalibration = () => sendCommand("skip_calibration");
  const handleRecalibrate = () => sendCommand("recalibrate");

  const handleToggleVoice = () => {
    setVoiceEnabled((previous) => !previous);
    sendCommand("toggle_voice");
  };

  const handleSaveSettings = () => {
    sendCommand("update_settings", {
      settings: {
        ...settings,
        voice_enabled: voiceEnabled,
      },
    });
    setShowSettings(false);
  };

  if (!connected) {
    return (
      <ConnectionState
        connecting={connecting}
        error={error}
        onConnect={connect}
      />
    );
  }

  if (shouldShowCalibration) {
    return (
      <CalibrationOverlay
        phase={data.phase}
        progress={data.progress}
        message={data.message}
        onStart={handleStartCalibration}
        onSkip={handleSkipCalibration}
      />
    );
  }

  return (
    <div className="app-container">
      <div className="toast" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast__item toast__item--${toast.color}`}
          >
            <div className="toast__label">{toast.label}</div>
            <div className="toast__text">{toast.message}</div>
          </div>
        ))}
      </div>

      <header className="app-header">
        <div className="app-header__brand">
          <div className="app-header__logo">EV</div>
          <div>
            <h1 className="app-header__title">ErgoVision</h1>
            <p className="app-header__subtitle">
              Occupational Health Monitoring
            </p>
          </div>
        </div>

        <div className="app-header__actions">
          <div
            className={`app-header__status ${connected ? "app-header__status--active" : "app-header__status--inactive"}`}
          >
            <span className="app-header__status-dot" />
            {connected ? "Live Monitoring" : "Offline"}
          </div>

          <button
            className="btn btn--icon btn--ghost"
            title="Toggle voice alerts"
            onClick={handleToggleVoice}
          >
            {voiceEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
          </button>
          <button
            className="btn btn--icon btn--ghost"
            title="Open analytics"
            onClick={() => setShowAnalytics(true)}
          >
            <BarChart3 size={16} />
          </button>
          <button
            className="btn btn--icon btn--ghost"
            title="Open settings"
            onClick={() => setShowSettings(true)}
          >
            <Settings size={16} />
          </button>
        </div>
      </header>

      <main className="app-main">
        <section className="webcam-panel">
          <div className="webcam-frame">
            {frame ? (
              <img
                src={`data:image/jpeg;base64,${frame}`}
                alt="Realtime webcam stream"
              />
            ) : (
              <div className="webcam-frame__placeholder">
                <div className="webcam-frame__placeholder-icon">Camera</div>
                <span>Waiting for camera feed</span>
              </div>
            )}

            {frame ? (
              <>
                <div className="webcam-frame__badge webcam-frame__badge--live">
                  Live
                </div>
                <div className="webcam-frame__badge webcam-frame__badge--fps">
                  {fps.toFixed(1)} FPS
                </div>
              </>
            ) : null}
          </div>

          <div className="metrics-grid">
            <MetricCard
              title="Eye Status"
              icon={<Eye size={14} />}
              value={eyeData.blink_rate ?? 0}
              unit="/min"
              detail={`EAR ${(eyeData.ear ?? 0).toFixed(3)}`}
              accent="#0f766e"
              status={metricStatus({ alert: eyeData.alert })}
            />

            <MetricCard
              title="Posture"
              icon={<Activity size={14} />}
              value={postureData.status ?? "N/A"}
              detail={`Deviation ${(postureData.deviation ?? 0).toFixed(0)} px`}
              accent="#0369a1"
              status={metricStatus({
                alert: postureData.alert,
                warning: postureData.status === "WARNING",
              })}
            />

            <MetricCard
              title="Distance"
              icon={<Ruler size={14} />}
              value={(distanceData.distance_cm ?? 0).toFixed(0)}
              unit="cm"
              detail={
                distanceData.alert
                  ? "Below safety threshold"
                  : "Within target range"
              }
              accent="#c2410c"
              status={metricStatus({ alert: distanceData.alert })}
            />

            <MetricCard
              title="Fatigue"
              icon={<Brain size={14} />}
              value={(fatigueData.fatigue_score ?? 0).toFixed(0)}
              unit="/100"
              detail={`Yawns ${fatigueData.yawn_count ?? 0} per hour`}
              accent="#b91c1c"
              status={metricStatus({
                alert: fatigueData.alert,
                warning: (fatigueData.fatigue_score ?? 0) > 35,
              })}
            />
          </div>

          {history.length > 5 ? (
            <article
              className="metric-card metric-card--wide"
              style={{ "--card-accent": "#0f766e" }}
            >
              <div className="metric-card__label">Blink Rate Trend</div>
              <SparklineChart
                data={recentSamples}
                dataKey="blinkRate"
                color="#0f766e"
                gradientId="blinkTrend"
              />
            </article>
          ) : null}
        </section>

        <aside className="side-panel">
          <section className="session-info">
            <h2 className="session-info__title">Current Session</h2>
            <div className="session-info__row">
              <span className="session-info__label">Duration</span>
              <span className="session-info__value">{sessionTime}</span>
            </div>
            <div className="session-info__row">
              <span className="session-info__label">Face visibility</span>
              <span className="session-info__value">
                {faceDetected ? "Detected" : "Not detected"}
              </span>
            </div>
            <div className="session-info__row">
              <span className="session-info__label">Runtime FPS</span>
              <span className="session-info__value">{fps.toFixed(1)}</span>
            </div>
            <div className="session-info__row">
              <span className="session-info__label">Voice alerts</span>
              <span className="session-info__value">
                {voiceEnabled ? "Enabled" : "Muted"}
              </span>
            </div>
            <button
              className="btn btn--ghost btn--sm session-info__action"
              onClick={handleRecalibrate}
            >
              <RefreshCw size={14} /> Recalibrate
            </button>
          </section>

          {history.length > 5 ? (
            <>
              <article
                className="metric-card metric-card--compact"
                style={{ "--card-accent": "#c2410c" }}
              >
                <div className="metric-card__label">Distance Trend</div>
                <SparklineChart
                  data={recentSamples}
                  dataKey="distance"
                  color="#c2410c"
                  gradientId="distanceTrend"
                  height={76}
                />
              </article>
              <article
                className="metric-card metric-card--compact"
                style={{ "--card-accent": "#b91c1c" }}
              >
                <div className="metric-card__label">Fatigue Trend</div>
                <SparklineChart
                  data={recentSamples}
                  dataKey="fatigue"
                  color="#b91c1c"
                  gradientId="fatigueTrend"
                  height={76}
                  yDomain={[0, 100]}
                />
              </article>
            </>
          ) : null}

          <section className="alert-feed">
            <h2 className="alert-feed__title">
              <AlertTriangle size={14} /> Alert Timeline
            </h2>

            {alerts.length === 0 ? (
              <div className="alert-feed__empty">
                No alerts triggered in this session.
              </div>
            ) : (
              alerts.slice(0, 20).map((alert) => (
                <article key={alert.id} className="alert-feed__item">
                  <span
                    className={`alert-feed__dot alert-feed__dot--${alert.color}`}
                  />
                  <div>
                    <div className="alert-feed__text">
                      {alert.label}: {alert.message}
                    </div>
                    <div className="alert-feed__time">{alert.time}</div>
                  </div>
                </article>
              ))
            )}
          </section>
        </aside>
      </main>

      <SettingsDrawer
        open={showSettings}
        onClose={() => setShowSettings(false)}
        settings={settings}
        setSettings={setSettings}
        voiceEnabled={voiceEnabled}
        onToggleVoice={handleToggleVoice}
        onSave={handleSaveSettings}
      />

      <AnalyticsModal
        open={showAnalytics}
        onClose={() => setShowAnalytics(false)}
        history={history}
      />
    </div>
  );
}
