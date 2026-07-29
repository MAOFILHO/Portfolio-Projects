import { useEffect, useState } from "react";
import { fetchSettings, type AppSettings } from "../api/client";
import { SeverityBadge } from "../components/SeverityBadge";

const SEVERITY_ORDER = ["critical", "high", "medium", "low"];

function sortedSeverityEntries(map: Record<string, string>): [string, string][] {
  return Object.entries(map).sort(([, a], [, b]) => SEVERITY_ORDER.indexOf(a) - SEVERITY_ORDER.indexOf(b));
}

export function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings()
      .then(setSettings)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load settings"));
  }, []);

  return (
    <div className="panel">
      <h3>Settings</h3>
      <p className="capture-hint">
        Read-only: reflects this deployment's live configuration. Change via root <code>.env</code> and
        redeploy to edit.
      </p>
      {error && <p className="error-text">{error}</p>}
      {settings && (
        <dl className="profile-fields">
          <dt>Alert watch tags</dt>
          <dd>{settings.alert_watch_tags.join(", ")}</dd>
          <dt>Alert min confidence</dt>
          <dd>{settings.alert_min_confidence}</dd>
          <dt>Alert min count</dt>
          <dd>{settings.alert_min_count}</dd>
          <dt>Capture interval (seconds)</dt>
          <dd>{settings.capture_interval_seconds}</dd>
          <dt>Detection backend</dt>
          <dd>{settings.analyzer_backend === "ssd_mobilenet" ? "SSD-MobileNet (self-hosted)" : "Azure AI Vision"}</dd>
          <dt>Crowd alert threshold</dt>
          <dd>{settings.alert_crowd_threshold > 0 ? `${settings.alert_crowd_threshold}+ people` : "Disabled"}</dd>
          <dt>Restricted zone (trespassing rule)</dt>
          <dd>{settings.alert_restricted_zone || "Disabled"}</dd>
          <dt>Alert severity levels</dt>
          <dd>
            <div className="severity-map-list">
              {sortedSeverityEntries(settings.alert_severity_map).map(([tag, severity]) => (
                <span className="severity-map-row" key={tag}>
                  <SeverityBadge severity={severity} />
                  {tag}
                </span>
              ))}
            </div>
          </dd>
        </dl>
      )}
    </div>
  );
}
