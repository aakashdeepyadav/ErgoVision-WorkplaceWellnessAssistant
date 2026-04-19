export default function SettingsDrawer({
  open,
  onClose,
  settings,
  setSettings,
  voiceEnabled,
  onToggleVoice,
  onSave,
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div
        className="settings-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="settings-panel__header">
          <h2 className="settings-panel__title">Monitoring Settings</h2>
          <button className="btn btn--ghost btn--icon" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="settings-group">
          <div className="settings-group__title">Eye Fatigue</div>
          <div className="settings-row">
            <span className="settings-row__label">EAR threshold</span>
            <input
              className="settings-row__input"
              type="number"
              step="0.01"
              min="0.15"
              max="0.35"
              value={settings.ear_threshold}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  ear_threshold: parseFloat(event.target.value) || 0.25,
                }))
              }
            />
          </div>
          <div className="settings-row">
            <span className="settings-row__label">Minimum blinks / min</span>
            <input
              className="settings-row__input"
              type="number"
              min="1"
              max="20"
              value={settings.min_blink_rate}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  min_blink_rate: parseInt(event.target.value, 10) || 5,
                }))
              }
            />
          </div>
        </div>

        <div className="settings-group">
          <div className="settings-group__title">Posture</div>
          <div className="settings-row">
            <span className="settings-row__label">
              Deviation threshold (px)
            </span>
            <input
              className="settings-row__input"
              type="number"
              min="10"
              max="80"
              value={settings.posture_threshold}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  posture_threshold: parseInt(event.target.value, 10) || 40,
                }))
              }
            />
          </div>
        </div>

        <div className="settings-group">
          <div className="settings-group__title">Distance</div>
          <div className="settings-row">
            <span className="settings-row__label">Minimum distance (cm)</span>
            <input
              className="settings-row__input"
              type="number"
              min="30"
              max="90"
              value={settings.min_distance}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  min_distance: parseInt(event.target.value, 10) || 50,
                }))
              }
            />
          </div>
        </div>

        <div className="settings-group">
          <div className="settings-group__title">Alerting</div>
          <div className="settings-row">
            <span className="settings-row__label">Voice alerts</span>
            <label className="toggle">
              <input
                type="checkbox"
                checked={voiceEnabled}
                onChange={onToggleVoice}
              />
              <span className="toggle__slider" />
            </label>
          </div>
          <div className="settings-row">
            <span className="settings-row__label">Cooldown (minutes)</span>
            <input
              className="settings-row__input"
              type="number"
              min="1"
              max="30"
              value={settings.cooldown_minutes}
              onChange={(event) =>
                setSettings((prev) => ({
                  ...prev,
                  cooldown_minutes: parseInt(event.target.value, 10) || 5,
                }))
              }
            />
          </div>
        </div>

        <button
          className="btn btn--primary settings-panel__save"
          onClick={onSave}
        >
          Save Configuration
        </button>
      </div>
    </div>
  );
}
