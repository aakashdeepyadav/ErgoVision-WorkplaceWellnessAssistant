export default function GazeIndicator({ gazeX = 0, gazeY = 0 }) {
  const translateX = gazeX * 14;
  const translateY = gazeY * 14;

  return (
    <div className="gaze-indicator" title="Gaze direction">
      <div className="gaze-indicator__ring" />
      <div
        className="gaze-indicator__dot"
        style={{ transform: `translate(${translateX}px, ${translateY}px)` }}
      />
    </div>
  );
}
