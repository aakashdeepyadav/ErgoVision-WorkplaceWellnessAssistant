import { useState } from "react";
import { Shield, Wifi } from "lucide-react";

export default function ConnectionState({ connecting, error, onConnect }) {
  const [consented, setConsented] = useState(false);
  const [permissionRequesting, setPermissionRequesting] = useState(false);
  const [permissionError, setPermissionError] = useState(null);

  const effectiveError = permissionError || error;

  const requestBrowserCameraPermission = async () => {
    if (!navigator?.mediaDevices?.getUserMedia) {
      const nextError = new Error(
        "Browser camera permission is unavailable. Use HTTPS or localhost.",
      );
      nextError.name = "UnsupportedError";
      throw nextError;
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: false,
    });

    stream.getTracks().forEach((track) => track.stop());
  };

  const formatPermissionError = (cause) => {
    const name = cause?.name;

    if (name === "NotAllowedError" || name === "PermissionDeniedError") {
      return "Camera permission was blocked. Allow camera access in your browser and try again.";
    }

    if (name === "NotFoundError" || name === "DevicesNotFoundError") {
      return "No camera device was found on this machine.";
    }

    if (name === "NotReadableError" || name === "TrackStartError") {
      return "Camera is already in use by another app. Close other apps and try again.";
    }

    if (name === "SecurityError" || name === "UnsupportedError") {
      return "Camera permission requires HTTPS or localhost.";
    }

    return "Unable to request browser camera permission. Check site permissions and try again.";
  };

  const handleConnect = async () => {
    if (!consented || connecting || permissionRequesting) {
      return;
    }

    setPermissionError(null);
    setPermissionRequesting(true);

    try {
      await requestBrowserCameraPermission();
      onConnect();
    } catch (cause) {
      setPermissionError(formatPermissionError(cause));
    } finally {
      setPermissionRequesting(false);
    }
  };

  if (connecting || permissionRequesting) {
    return (
      <div className="connect-screen">
        <div className="connect-screen__loader" />
        <h2 className="connect-screen__title">
          {connecting ? "Connecting" : "Camera permission"}
        </h2>
        <p className="connect-screen__subtitle">
          {connecting
            ? "Establishing a secure realtime link to the monitoring backend."
            : "Approve the browser camera prompt to continue."}
        </p>
      </div>
    );
  }

  return (
    <div className="connect-screen">
      <div className="connect-screen__icon">EV</div>
      <h1 className="connect-screen__title">ErgoVision</h1>
      <p className="connect-screen__subtitle">
        Real-time workstation wellness monitoring for eye strain, posture, and
        viewing distance.
      </p>

      <div className="consent-card" role="note" aria-label="Privacy notice">
        <div className="consent-card__title">
          <Shield size={14} /> Privacy & camera access
        </div>
        <p className="consent-card__text">
          This dashboard receives a video stream from the local Python backend.
          When you click Connect, we also request browser camera permission as
          an explicit consent step.
        </p>
        <p className="consent-card__text">
          If the camera won&apos;t start, enable Windows camera access for
          desktop apps (Settings → Privacy & security → Camera).
        </p>
        <label className="consent-check">
          <input
            type="checkbox"
            checked={consented}
            onChange={(event) => {
              setConsented(event.target.checked);
              setPermissionError(null);
            }}
          />
          <span>
            I understand and consent to webcam monitoring on this device.
          </span>
        </label>
      </div>

      {effectiveError ? (
        <div className="connect-screen__error">{effectiveError}</div>
      ) : null}
      <button
        className="btn btn--primary"
        onClick={handleConnect}
        disabled={!consented || permissionRequesting}
      >
        <Wifi size={16} /> Connect
      </button>
      <p className="text-muted">
        Run python server.py to start the backend service.
      </p>
    </div>
  );
}
