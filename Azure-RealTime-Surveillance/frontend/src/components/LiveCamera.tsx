import { useCamera } from "../hooks/useCamera";
import { useCaptureLoop } from "../hooks/useCaptureLoop";
import { formatCameraLabel } from "../utils/format";

const CLIP_INTERVAL_SECONDS = 20;
const CLIP_DURATION_MS = 4000;

interface LiveCameraProps {
  cameraId: string;
  intervalSeconds: number;
  onFrame: (blob: Blob) => void;
  onClip: (blob: Blob, contentType: string) => void;
}

export function LiveCamera({ cameraId, intervalSeconds, onFrame, onClip }: LiveCameraProps) {
  const { videoRef, canvasRef, isActive, error, start, stop, captureFrame, recordClip } = useCamera();

  useCaptureLoop(isActive, intervalSeconds, async () => {
    const blob = await captureFrame();
    if (blob) onFrame(blob);
  });

  useCaptureLoop(isActive, CLIP_INTERVAL_SECONDS, async () => {
    const result = await recordClip(CLIP_DURATION_MS);
    if (result) onClip(result.blob, result.contentType);
  });

  return (
    <div className="camera-panel">
      <div className="camera-header">
        <div className="camera-title-row">
          <h3>Live Camera: {formatCameraLabel(cameraId)}</h3>
          <span className="badge">🎥 Frames + Clips</span>
        </div>
        <div className="camera-controls">
          {!isActive ? (
            <button onClick={start}>Start Capture</button>
          ) : (
            <button onClick={stop}>Stop Capture</button>
          )}
        </div>
      </div>
      {error && <p className="error-text">{error}</p>}
      <video ref={videoRef} className="camera-video" muted playsInline />
      <canvas ref={canvasRef} className="camera-canvas-hidden" />
      <p className="capture-hint">
        {isActive ? "Capturing: " : "Will capture (once started): "}
        frames every {intervalSeconds}s, a {CLIP_DURATION_MS / 1000}s clip every {CLIP_INTERVAL_SECONDS}s
      </p>
      <div className="panel-spacer" />
    </div>
  );
}
