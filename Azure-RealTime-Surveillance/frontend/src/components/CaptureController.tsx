import { useState } from "react";
import { uploadClip, uploadFrame } from "../api/client";
import type { CaptureSource } from "../types";
import { InfoTooltip } from "./InfoTooltip";
import { LiveCamera } from "./LiveCamera";
import { VideoFileMode } from "./VideoFileMode";

const DEFAULT_INTERVAL_SECONDS = 3;

// Camera ID is fixed per capture source, not user-editable -- every webcam
// capture lands under "laptop-webcam" and every demo-video capture under
// "demo-video" in Event History, so there's nothing for the user to
// meaningfully choose here.
const CAMERA_ID_BY_SOURCE: Record<CaptureSource, string> = {
  webcam: "laptop-webcam",
  "sample-video": "demo-video",
};

export function CaptureController() {
  const [source, setSource] = useState<CaptureSource>("webcam");
  const [intervalSeconds, setIntervalSeconds] = useState(DEFAULT_INTERVAL_SECONDS);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const cameraId = CAMERA_ID_BY_SOURCE[source];

  const handleFrame = async (blob: Blob) => {
    try {
      await uploadFrame(cameraId, blob);
      setUploadError(null);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const handleClip = async (blob: Blob, contentType: string) => {
    try {
      await uploadClip(cameraId, blob, contentType);
    } catch {
      // Clips are a best-effort companion to the frame path -- a failed
      // clip upload shouldn't interrupt or error out the capture session.
    }
  };

  return (
    <div className="panel stretch-panel">
      <div className="panel-header">
        <h3>Live Capture</h3>
        <div className="mode-toggle">
          <button className={source === "webcam" ? "active" : ""} onClick={() => setSource("webcam")}>
            Webcam
          </button>
          <button className={source === "sample-video" ? "active" : ""} onClick={() => setSource("sample-video")}>
            Demo Video
          </button>
        </div>
      </div>

      <div className="capture-settings">
        <label>
          <span className="label-with-info">
            Frame Interval (seconds)
            <InfoTooltip
              text={
                "How often, in real time, a frame is captured from the live feed and sent for analysis -- " +
                "e.g. a 3s interval uploads a new frame roughly every 3 seconds while capture is running."
              }
            />
          </span>
          <input
            type="number"
            min={1}
            max={60}
            value={intervalSeconds}
            onChange={(e) => setIntervalSeconds(Number(e.target.value) || DEFAULT_INTERVAL_SECONDS)}
          />
        </label>
      </div>

      {source === "webcam" ? (
        <LiveCamera cameraId={cameraId} intervalSeconds={intervalSeconds} onFrame={handleFrame} onClip={handleClip} />
      ) : (
        <VideoFileMode cameraId={cameraId} intervalSeconds={intervalSeconds} onFrame={handleFrame} />
      )}

      {uploadError && <p className="error-text">Upload error: {uploadError}</p>}
    </div>
  );
}
