import { useRef, useState } from "react";
import { useCaptureLoop } from "../hooks/useCaptureLoop";
import { formatCameraLabel } from "../utils/format";

const SAMPLE_VIDEOS = [
  { label: "SWAT soldier (weapon)", src: "/sample_videos/swat-soldier-with-weapon-13884574-720p.mp4" },
  { label: "Paintball shooting", src: "/sample_videos/paintball-player-shooting-13242200-720p.mp4" },
];

interface VideoFileModeProps {
  cameraId: string;
  intervalSeconds: number;
  onFrame: (blob: Blob) => void;
}

/** Demo capture mode using a looping sample video instead of a live webcam —
 * ported from Ai-Detect-Video-Alert's VideoStream.razor sample-video selector.
 */
export function VideoFileMode({ cameraId, intervalSeconds, onFrame }: VideoFileModeProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [selectedSrc, setSelectedSrc] = useState(SAMPLE_VIDEOS[0].src);
  const [isCapturing, setIsCapturing] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  const captureFrame = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.videoWidth === 0) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => {
      if (blob) onFrame(blob);
    }, "image/jpeg", 0.85);
  };

  useCaptureLoop(isCapturing && isPlaying, intervalSeconds, captureFrame);

  return (
    <div className="camera-panel">
      <div className="camera-header">
        <h3>Demo Video: {formatCameraLabel(cameraId)}</h3>
        <select
          value={selectedSrc}
          onChange={(e) => setSelectedSrc(e.target.value)}
          disabled={isPlaying}
        >
          {SAMPLE_VIDEOS.map((v) => (
            <option key={v.src} value={v.src}>{v.label}</option>
          ))}
        </select>
      </div>
      <video
        ref={videoRef}
        className="camera-video"
        src={selectedSrc}
        loop
        muted
        playsInline
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
      />
      <canvas ref={canvasRef} className="camera-canvas-hidden" />
      <div className="camera-controls">
        <button onClick={() => videoRef.current?.play()}>Play</button>
        <button onClick={() => videoRef.current?.pause()}>Pause</button>
        <button onClick={() => setIsCapturing((c) => !c)}>
          {isCapturing ? "Stop Capture" : "Start Capture"}
        </button>
      </div>
      <p className="capture-hint">
        {isCapturing && isPlaying ? `Capturing every ${intervalSeconds}s` : "Capture paused"}
      </p>
      <div className="panel-spacer" />
    </div>
  );
}
