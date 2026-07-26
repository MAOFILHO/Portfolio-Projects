import { useCallback, useEffect, useState } from "react";
import { clipVideoUrl, fetchClips, fetchEvents, frameImageUrl } from "../api/client";
import type { ClipInfo, SurveillanceEvent } from "../types";
import { formatCameraLabel } from "../utils/format";
import { FrameDetailModal } from "./FrameDetailModal";
import { SeverityBadge } from "./SeverityBadge";

const REFRESH_INTERVAL_MS = 10_000;

type ViewMode = "thumbnails" | "video";

export function EventHistory() {
  const [viewMode, setViewMode] = useState<ViewMode>("thumbnails");
  const [events, setEvents] = useState<SurveillanceEvent[]>([]);
  const [clips, setClips] = useState<ClipInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<SurveillanceEvent | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  const load = useCallback(async () => {
    try {
      if (viewMode === "thumbnails") {
        setEvents(await fetchEvents(30));
      } else {
        setClips(await fetchClips(30));
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setHasLoadedOnce(true);
    }
  }, [viewMode]);

  useEffect(() => {
    setHasLoadedOnce(false);
    load();
    const id = setInterval(load, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [load]);

  const handleRefreshClick = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <h3>Event History</h3>
        <div className="event-history-controls">
          <button
            className="refresh-button"
            onClick={handleRefreshClick}
            disabled={refreshing}
            title="Refresh now"
            aria-label="Refresh now"
          >
            <span className={refreshing ? "refresh-icon spinning" : "refresh-icon"}>↻</span>
          </button>
          <div className="mode-toggle">
            <button className={viewMode === "thumbnails" ? "active" : ""} onClick={() => setViewMode("thumbnails")}>
              Thumbnails
            </button>
            <button className={viewMode === "video" ? "active" : ""} onClick={() => setViewMode("video")}>
              Video
            </button>
          </div>
        </div>
      </div>
      {error && <p className="error-text">{error}</p>}

      {viewMode === "thumbnails" ? (
        !hasLoadedOnce ? (
          <p className="empty-state">Loading events…</p>
        ) : events.length === 0 ? (
          <p className="empty-state">No events recorded yet.</p>
        ) : (
          <table className="event-table">
            <thead>
              <tr>
                <th>Frame</th>
                <th>Camera</th>
                <th>Time</th>
                <th>Severity</th>
                <th>Caption</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.RowKey} className={event.IsAlert ? "row-alert" : ""}>
                  <td>
                    <button className="thumbnail-button" onClick={() => setSelectedEvent(event)}>
                      <img
                        className="event-thumbnail"
                        src={frameImageUrl(event.FrameBlobName)}
                        alt={`Captured frame from ${event.PartitionKey}`}
                        loading="lazy"
                      />
                    </button>
                  </td>
                  <td>{formatCameraLabel(event.PartitionKey)}</td>
                  <td>{new Date(event.AnalyzedAt).toLocaleTimeString()}</td>
                  <td>{event.IsAlert ? <SeverityBadge severity={event.Severity} /> : "-"}</td>
                  <td>{event.Caption || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : !hasLoadedOnce ? (
        <p className="empty-state">Loading clips…</p>
      ) : clips.length === 0 ? (
        <p className="empty-state">No clips recorded yet — clips are captured periodically from the live webcam.</p>
      ) : (
        <table className="event-table">
          <thead>
            <tr>
              <th>Camera</th>
              <th>Time</th>
              <th>Clip</th>
            </tr>
          </thead>
          <tbody>
            {clips.map((clip) => (
              <tr key={clip.blob_name}>
                <td>{formatCameraLabel(clip.camera_id)}</td>
                <td>{new Date(clip.last_modified).toLocaleString()}</td>
                <td>
                  <a href={clipVideoUrl(clip.blob_name)} target="_blank" rel="noreferrer">
                    ▶ Play
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selectedEvent && <FrameDetailModal event={selectedEvent} onClose={() => setSelectedEvent(null)} />}
    </div>
  );
}
