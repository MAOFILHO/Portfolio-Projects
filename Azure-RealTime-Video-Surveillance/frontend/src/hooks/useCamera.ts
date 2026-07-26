import { useCallback, useRef, useState } from "react";

/**
 * Browser camera capture, ported from Ai-Detect-Video-Alert/wwwroot/webcam.js
 * (getUserMedia -> <video> -> <canvas> drawImage -> JPEG blob). The original
 * used `canvas.toDataURL("image/jpeg")` then saved the result with a `.png`
 * blob name; this port uses `canvas.toBlob` with an explicit "image/jpeg"
 * MIME type end-to-end so the extension/content-type is never wrong (see
 * docs/architecture.md "Improvements over the originals").
 */
export function useCamera() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [isActive, setIsActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsActive(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to access camera");
      setIsActive(false);
    }
  }, []);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setIsActive(false);
  }, []);

  const captureFrame = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.videoWidth === 0) {
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
  }, []);

  const CLIP_MIME_TYPE = "video/webm;codecs=vp8";

  /** Records a short clip from the live stream via MediaRecorder. Resolves
   * null if there's no active stream or the browser doesn't support the
   * chosen codec (broad support: every current major browser except Safari,
   * which lacks VP8 MediaRecorder support as of this writing).
   */
  const recordClip = useCallback((durationMs: number): Promise<{ blob: Blob; contentType: string } | null> => {
    return new Promise((resolve) => {
      const stream = streamRef.current;
      if (!stream || !MediaRecorder.isTypeSupported(CLIP_MIME_TYPE)) {
        resolve(null);
        return;
      }
      const recorder = new MediaRecorder(stream, { mimeType: CLIP_MIME_TYPE });
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };
      recorder.onstop = () => {
        if (chunks.length === 0) {
          resolve(null);
          return;
        }
        resolve({ blob: new Blob(chunks, { type: "video/webm" }), contentType: "video/webm" });
      };
      recorder.onerror = () => resolve(null);
      recorder.start();
      setTimeout(() => recorder.stop(), durationMs);
    });
  }, []);

  return { videoRef, canvasRef, isActive, error, start, stop, captureFrame, recordClip };
}
