import { useEffect, useState } from "react";
import { analyzeFrame, frameImageUrl, logAuditEvent } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import type { Detection, OnDemandAnalysisResult, OnDemandFeature, SurveillanceEvent } from "../types";
import { formatCameraLabel } from "../utils/format";

interface FrameDetailModalProps {
  event: SurveillanceEvent;
  onClose: () => void;
}

function parseDetections(raw: string): Detection[] {
  try {
    const parsed = JSON.parse(raw) as { detections?: Detection[] };
    return parsed.detections ?? [];
  } catch {
    return [];
  }
}

const ON_DEMAND_BUTTONS: { feature: OnDemandFeature; label: string }[] = [
  { feature: "tags", label: "Tags" },
  { feature: "read", label: "Read Text" },
  { feature: "smartcrops", label: "Smart Crop" },
];

/** Renders detection boxes as percentage-positioned overlays on top of the
 * frame image, keyed off the image's natural (original) pixel size rather
 * than its rendered size -- works at any zoom/viewport without recomputing
 * on resize.
 */
export function FrameDetailModal({ event, onClose }: FrameDetailModalProps) {
  const { user } = useAuth();
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null);
  const [onDemandResult, setOnDemandResult] = useState<OnDemandAnalysisResult | null>(null);
  const [pendingFeature, setPendingFeature] = useState<OnDemandFeature | null>(null);
  const [onDemandError, setOnDemandError] = useState<string | null>(null);
  const detections = parseDetections(event.Detections);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const runOnDemand = async (feature: OnDemandFeature) => {
    setPendingFeature(feature);
    setOnDemandError(null);
    try {
      const result = await analyzeFrame(event.FrameBlobName, [feature]);
      setOnDemandResult(result);
      void logAuditEvent(user?.userDetails ?? "anonymous", "on_demand_analysis", `${feature} on ${event.FrameBlobName}`);
    } catch (err) {
      setOnDemandError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setPendingFeature(null);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>
            {formatCameraLabel(event.PartitionKey)} — {new Date(event.AnalyzedAt).toLocaleString()}
          </h3>
          <button onClick={onClose}>Close</button>
        </div>
        <div className="modal-image-wrap">
          <img
            src={frameImageUrl(event.FrameBlobName)}
            alt={`Full captured frame from ${event.PartitionKey}`}
            onLoad={(e) => {
              const img = e.currentTarget;
              setNaturalSize({ width: img.naturalWidth, height: img.naturalHeight });
            }}
          />
          {naturalSize &&
            detections.map((d, i) =>
              d.bounding_box ? (
                <div
                  key={i}
                  className={`detection-box${d.tag === "person" ? " detection-box-person" : ""}`}
                  style={{
                    left: `${(d.bounding_box[0] / naturalSize.width) * 100}%`,
                    top: `${(d.bounding_box[1] / naturalSize.height) * 100}%`,
                    width: `${(d.bounding_box[2] / naturalSize.width) * 100}%`,
                    height: `${(d.bounding_box[3] / naturalSize.height) * 100}%`,
                  }}
                >
                  <span className="detection-label">
                    {d.tag} {(d.confidence * 100).toFixed(0)}%
                  </span>
                </div>
              ) : null
            )}
        </div>
        <ul className="detection-list">
          {detections.length === 0 ? (
            <li className="empty-state">No objects detected in this frame.</li>
          ) : (
            detections.map((d, i) => (
              <li key={i}>
                {d.tag} — {(d.confidence * 100).toFixed(0)}%
                {d.bounding_box && ` — [x:${d.bounding_box[0]}, y:${d.bounding_box[1]}, w:${d.bounding_box[2]}, h:${d.bounding_box[3]}]`}
              </li>
            ))
          )}
        </ul>

        <div className="on-demand-panel">
          <div className="on-demand-buttons">
            {ON_DEMAND_BUTTONS.map(({ feature, label }) => (
              <button key={feature} disabled={pendingFeature !== null} onClick={() => runOnDemand(feature)}>
                {pendingFeature === feature ? "Analyzing…" : label}
              </button>
            ))}
          </div>
          {onDemandError && <p className="error-text">{onDemandError}</p>}
          {onDemandResult && (
            <div className="on-demand-results">
              {onDemandResult.tags && (
                <ul className="detection-list">
                  {onDemandResult.tags.map((t, i) => (
                    <li key={i}>
                      {t.name} — {(t.confidence * 100).toFixed(0)}%
                    </li>
                  ))}
                </ul>
              )}
              {onDemandResult.read_lines && (
                <ul className="detection-list">
                  {onDemandResult.read_lines.length === 0 ? (
                    <li className="empty-state">No text found in this frame.</li>
                  ) : (
                    onDemandResult.read_lines.map((line, i) => <li key={i}>{line}</li>)
                  )}
                </ul>
              )}
              {onDemandResult.smart_crops && (
                <ul className="detection-list">
                  {onDemandResult.smart_crops.map((c, i) => (
                    <li key={i}>
                      Crop @ {c.aspect_ratio.toFixed(2)}:1 — [{c.bounding_box.join(", ")}]
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
