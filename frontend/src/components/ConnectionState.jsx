import { Wifi } from "lucide-react";

export default function ConnectionState({ connecting, error, onConnect }) {
  if (connecting) {
    return (
      <div className="connect-screen">
        <div className="connect-screen__loader" />
        <h2 className="connect-screen__title">Connecting</h2>
        <p className="connect-screen__subtitle">
          Establishing a secure realtime link to the monitoring backend.
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
      {error ? <div className="connect-screen__error">{error}</div> : null}
      <button className="btn btn--primary" onClick={onConnect}>
        <Wifi size={16} /> Connect
      </button>
      <p className="text-muted">
        Run python server.py to start the backend service.
      </p>
    </div>
  );
}
