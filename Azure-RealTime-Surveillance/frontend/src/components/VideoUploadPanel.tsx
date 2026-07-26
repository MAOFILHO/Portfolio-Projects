import { useRef, useState } from "react";
import { uploadFrame } from "../api/client";
import { InfoTooltip } from "./InfoTooltip";

const DEFAULT_CAMERA_ID = "uploaded-video";
const DEFAULT_INTERVAL_SECONDS = 3;
// Caps the number of Vision API calls a single upload can trigger -- each
// extracted frame is one billed analysis call downstream, so an unbounded
// long video at a tight interval could otherwise fire hundreds of them.
const MAX_FRAMES = 100;

/** A standalone batch analysis feature, deliberately separate from the Live
 * Capture panel (Webcam/Demo Video): those are continuous, ongoing capture
 * loops sharing one Camera ID; this is a one-shot "analyze this file I
 * already have" action with its own identity (fixed Camera ID
 * `DEFAULT_CAMERA_ID`, not user-editable -- every upload lands under the
 * same "uploaded-video" bucket in Event History, so there's nothing for the
 * user to meaningfully choose here).
 *
 * Extracts frames by seeking the video element to a series of timestamps
 * (not by playing it back in real time) -- a 10-minute upload doesn't take
 * 10 minutes to process, just however long the browser takes to seek,
 * decode, and draw each frame. Every extracted frame goes through the exact
 * same POST /api/v1/frames path as live capture, so no backend changes were
 * needed for this feature at all.
 *
 * File selection is a two-step Choose -> Upload flow: choosing a file only
 * stages it (`pendingFile`); clicking Upload loads it into the hidden video
 * element and validates its duration, only then enabling Start Analysis
 * (`file`). This gives the user a confirmation point (filename chip + remove
 * button) before committing to analysis, and lets us surface "this isn't a
 * readable video" errors before the user hits Start rather than mid-run.
 */
export function VideoUploadPanel() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const cancelRef = useRef(false);
  const objectUrlRef = useRef<string | null>(null);

  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [staging, setStaging] = useState(false);
  const [stageError, setStageError] = useState<string | null>(null);
  const [intervalSeconds, setIntervalSeconds] = useState(DEFAULT_INTERVAL_SECONDS);
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPendingFile(e.target.files?.[0] ?? null);
    setStageError(null);
  };

  const handleUpload = async () => {
    const video = videoRef.current;
    if (!video || !pendingFile) return;

    setStaging(true);
    setStageError(null);

    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    const url = URL.createObjectURL(pendingFile);
    objectUrlRef.current = url;
    video.src = url;
    await waitForMetadata(video);

    if (!isFinite(video.duration) || video.duration <= 0) {
      setStageError("Could not read this video's duration -- try a different file.");
      URL.revokeObjectURL(url);
      objectUrlRef.current = null;
      video.removeAttribute("src");
      video.load();
      setStaging(false);
      return;
    }

    setFile(pendingFile);
    setPendingFile(null);
    setStaging(false);
  };

  const handleRemoveFile = () => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    setFile(null);
    setPendingFile(null);
    setStatus(null);
    setProgress(null);
    setUploadError(null);
    setStageError(null);
    if (videoRef.current) {
      videoRef.current.removeAttribute("src");
      videoRef.current.load();
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const waitForMetadata = (video: HTMLVideoElement): Promise<void> =>
    new Promise((resolve) => {
      if (video.readyState >= 1) {
        resolve();
        return;
      }
      video.addEventListener("loadedmetadata", () => resolve(), { once: true });
    });

  const seekTo = (video: HTMLVideoElement, time: number): Promise<void> =>
    new Promise((resolve) => {
      video.addEventListener("seeked", () => resolve(), { once: true });
      video.currentTime = time;
    });

  const captureCurrentFrame = (video: HTMLVideoElement): Promise<Blob | null> =>
    new Promise((resolve) => {
      const canvas = canvasRef.current;
      if (!canvas || video.videoWidth === 0) {
        resolve(null);
        return;
      }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(null);
        return;
      }
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.85);
    });

  const startAnalysis = async () => {
    const video = videoRef.current;
    if (!video || !file) return;

    cancelRef.current = false;
    setProcessing(true);
    setUploadError(null);
    setStatus(null);
    setProgress(null);

    const duration = video.duration;
    let effectiveInterval = intervalSeconds;
    const requestedFrameCount = Math.ceil(duration / effectiveInterval);
    if (requestedFrameCount > MAX_FRAMES) {
      effectiveInterval = duration / MAX_FRAMES;
      setStatus(
        `This video would produce more than ${MAX_FRAMES} frames at a ${intervalSeconds}s interval -- ` +
          `using ~${effectiveInterval.toFixed(1)}s instead to keep the number of Vision API calls reasonable.`
      );
    }

    const timestamps: number[] = [];
    for (let t = 0; t < duration; t += effectiveInterval) timestamps.push(t);

    for (let i = 0; i < timestamps.length; i++) {
      if (cancelRef.current) break;
      setProgress({ current: i + 1, total: timestamps.length });
      await seekTo(video, timestamps[i]);
      const blob = await captureCurrentFrame(video);
      if (blob) {
        try {
          await uploadFrame(DEFAULT_CAMERA_ID, blob);
        } catch (err) {
          setUploadError(err instanceof Error ? err.message : "Upload failed");
        }
      }
    }

    setProgress(null);
    setProcessing(false);
  };

  const cancelAnalysis = () => {
    cancelRef.current = true;
  };

  return (
    <div className="panel stretch-panel">
      <div className="panel-header">
        <h3>Video Upload &amp; Analysis</h3>
      </div>

      <div className="capture-settings">
        <label>
          <span className="label-with-info">
            Extraction interval (seconds)
            <InfoTooltip
              text={
                "How far apart, in the video's own timeline, each analyzed frame is taken from -- not a live " +
                "capture rate. E.g. a 60s video at a 3s interval extracts ~20 frames total, all at once (not " +
                "spread out in real time)."
              }
            />
          </span>
          <input
            type="number"
            min={1}
            max={60}
            value={intervalSeconds}
            onChange={(e) => setIntervalSeconds(Number(e.target.value) || DEFAULT_INTERVAL_SECONDS)}
            disabled={processing}
          />
        </label>
      </div>

      <div className="camera-panel">
        <div className="camera-header">
          <div className="file-picker-buttons">
            <button
              type="button"
              className="choose-file-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={processing || staging || !!file}
            >
              Choose File
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              onChange={handleFileChange}
              disabled={processing || staging || !!file}
              hidden
            />
            <button type="button" onClick={handleUpload} disabled={!pendingFile || staging || processing}>
              {staging ? "Uploading…" : "Upload"}
            </button>
            {pendingFile && !file && (
              <div className="uploaded-file-chip">
                <span className="uploaded-file-name">{pendingFile.name}</span>
                <button
                  type="button"
                  className="remove-file-button"
                  onClick={handleRemoveFile}
                  aria-label="Remove file"
                  title="Remove file"
                >
                  ×
                </button>
              </div>
            )}
            {file && (
              <div className="uploaded-file-chip">
                <span className="uploaded-file-name">{file.name}</span>
                <button
                  type="button"
                  className="remove-file-button"
                  onClick={handleRemoveFile}
                  disabled={processing}
                  aria-label="Remove file"
                  title="Remove file"
                >
                  ×
                </button>
              </div>
            )}
          </div>
          {!processing ? (
            <button onClick={startAnalysis} disabled={!file}>
              Start Analysis
            </button>
          ) : (
            <button onClick={cancelAnalysis}>Cancel</button>
          )}
        </div>

        {stageError && <p className="error-text">{stageError}</p>}

        <video ref={videoRef} className="camera-video" muted playsInline />
        <canvas ref={canvasRef} className="camera-canvas-hidden" />

        {progress && (
          <div className="upload-progress">
            <div className="upload-progress-bar">
              <div className="upload-progress-fill" style={{ width: `${(progress.current / progress.total) * 100}%` }} />
            </div>
            <p className="capture-hint">
              Extracting frame {progress.current} of {progress.total}…
            </p>
          </div>
        )}
        {uploadError && <p className="error-text">Upload error: {uploadError}</p>}
        {status && !progress && <p className="capture-hint">{status}</p>}
        <p className="capture-hint">
          Upload &amp; Analyze your video files — results land in Event History as each frame is processed
        </p>
        <div className="panel-spacer" />
      </div>
    </div>
  );
}
