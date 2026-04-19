export const ALERT_CONFIG = {
  EYE_STRAIN: {
    label: 'Eye Strain',
    color: 'eye',
    message: 'Blink rate is below the healthy target.',
  },
  POOR_POSTURE: {
    label: 'Posture Drift',
    color: 'posture',
    message: 'Posture has drifted from your calibrated baseline.',
  },
  TOO_CLOSE: {
    label: 'Screen Distance',
    color: 'distance',
    message: 'You are sitting too close to the display.',
  },
  FATIGUE: {
    label: 'Fatigue',
    color: 'fatigue',
    message: 'Fatigue pattern detected. Consider a short break.',
  },
}

export const DEFAULT_SETTINGS = {
  ear_threshold: 0.25,
  min_blink_rate: 5,
  posture_threshold: 40,
  min_distance: 50,
  cooldown_minutes: 5,
}

export const ALERT_FEED_LIMIT = 50
export const HISTORY_LIMIT = 240
export const TOAST_DURATION_MS = 5000
